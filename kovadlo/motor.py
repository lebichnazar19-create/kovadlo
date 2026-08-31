"""
Електродвигуни (модуль 12): колекторний DC, безколекторний BLDC,
кроковий — параметри, струм під навантаженням, потужність,
тепловиділення, і зв'язок з електропроводкою (модуль 4) та платами
(модуль 6): двигун стає точкою споживання з відомим струмом, а той
самий струм визначає потрібну ширину доріжки живлення на платі.

Момент двигуна й обороти на вольт пов'язані через сталу двигуна
(теорія електричних машин):

    Kt [Н·м/А] = 60 / (2π · Kv [об/хв/В])

(Kt чисельно дорівнює сталій зворотної ЕРС Ke у системі СІ.) Тоді струм,
потрібний для розвитку моменту M (без урахування струму холостого
ходу): I = M / Kt.

Для крокового двигуна (`STEPPER`) ця залежність не застосовна — драйвер
зазвичай тримає обмотковий струм майже сталим (`nominal_current_a`)
незалежно від навантаження, аж до моменту втрати кроку при перевищенні
`max_torque_nm`.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .electrical_point import ConsumptionPoint, PointKind
from .geometry import Point
from .pcb_norms import DEFAULT_COPPER_THICKNESS_UM, DEFAULT_TEMPERATURE_RISE_C, MIN_TRACK_WIDTH_MM, required_track_width_mm
from .transmission import power_w


class MotorKind(Enum):
    """Тип електродвигуна."""

    DC_BRUSHED = "колекторний DC"
    BLDC = "безколекторний BLDC"
    STEPPER = "кроковий"


@dataclass(kw_only=True)
class Motor:
    """Електродвигун: номінальні параметри для розрахунку струму,
    потужності й тепловиділення під навантаженням."""

    name: str
    kind: MotorKind
    voltage_v: float
    nominal_current_a: float
    max_torque_nm: float
    kv_rpm_per_v: float | None = None
    efficiency: float = 0.8
    winding_resistance_ohm: float | None = None
    no_load_current_a: float = 0.0

    def __post_init__(self) -> None:
        if self.voltage_v <= 0:
            raise ValueError("Напруга двигуна має бути додатною")
        if self.nominal_current_a <= 0:
            raise ValueError("Номінальний струм має бути додатним")
        if self.max_torque_nm <= 0:
            raise ValueError("Максимальний момент має бути додатним")
        if not (0 < self.efficiency <= 1):
            raise ValueError("ККД має бути в діапазоні (0, 1]")
        if self.kv_rpm_per_v is not None and self.kv_rpm_per_v <= 0:
            raise ValueError("Kv має бути додатним")
        if self.winding_resistance_ohm is not None and self.winding_resistance_ohm <= 0:
            raise ValueError("Опір обмотки має бути додатним")
        if self.no_load_current_a < 0:
            raise ValueError("Струм холостого ходу не може бути від'ємним")


def torque_constant_nm_per_a(motor: Motor) -> float:
    """Стала моменту Kt, Н·м/А: Kt = 60 / (2π·Kv)."""
    if motor.kv_rpm_per_v is None:
        raise ValueError(f"У двигуна «{motor.name}» не задано Kv (обороти на вольт)")
    return 60.0 / (2 * 3.141592653589793 * motor.kv_rpm_per_v)


def current_under_load_a(motor: Motor, torque_nm: float) -> float:
    """Споживаний струм при заданому крутному моменті навантаження, А."""
    if torque_nm < 0:
        raise ValueError("Момент навантаження не може бути від'ємним")
    if torque_nm > motor.max_torque_nm:
        raise ValueError(
            f"Момент навантаження {torque_nm:.3f} Н·м перевищує максимальний момент двигуна «{motor.name}» "
            f"({motor.max_torque_nm:.3f} Н·м)"
        )
    if motor.kind is MotorKind.STEPPER:
        # Драйвер тримає обмотковий струм близьким до номінального
        # незалежно від навантаження (аж до max_torque_nm).
        return motor.nominal_current_a
    kt = torque_constant_nm_per_a(motor)
    return motor.no_load_current_a + torque_nm / kt


def power_input_w(motor: Motor, current_a: float) -> float:
    """Споживана електрична потужність, Вт: P = U·I."""
    return motor.voltage_v * current_a


def heat_dissipation_w(
    motor: Motor,
    current_a: float,
    *,
    torque_nm: float | None = None,
    angular_velocity_rad_s: float | None = None,
) -> float:
    """Теплові втрати двигуна, Вт.

    Пріоритет способу розрахунку:
    1. якщо відомі і момент, і кутова швидкість на валу — точний
       енергетичний баланс: втрати = споживана - корисна механічна
       потужність (P = M·ω, `transmission.power_w`);
    2. якщо відомий опір обмотки — омічні втрати I²R (актуально для
       колекторних DC, де основні втрати мідні);
    3. інакше — оцінка через номінальний ККД: втрати = P_вх·(1-η)
       (грубе наближення, коректне лише поблизу номінальної точки).
    """
    power_in = power_input_w(motor, current_a)
    if torque_nm is not None and angular_velocity_rad_s is not None:
        power_out = power_w(torque_nm, angular_velocity_rad_s)
        return max(0.0, power_in - power_out)
    if motor.winding_resistance_ohm is not None:
        return current_a**2 * motor.winding_resistance_ohm
    return power_in * (1 - motor.efficiency)


def to_consumption_point(motor: Motor, position: Point, current_a: float, name: str | None = None) -> ConsumptionPoint:
    """Місток до модуля 4: двигун — точка споживання з відомим струмом.

    У `PointKind` (модуль 4, ядро) немає окремого типу "двигун" — ядро
    незмінне, тож використовуємо найближчий за змістом наявний тип,
    `PointKind.SOCKET` (двигун під'єднаний як звичайний силовий
    споживач), з потужністю, порахованою з реального струму навантаження
    (`power_w=U·I`), а не типовим значенням розетки за замовчуванням.
    """
    return ConsumptionPoint(name=name or motor.name, kind=PointKind.SOCKET, position=position, power_w=power_input_w(motor, current_a))


def motor_pcb_track_width_mm(
    motor: Motor,
    torque_nm: float,
    *,
    temperature_rise_c: float = DEFAULT_TEMPERATURE_RISE_C,
    copper_thickness_um: float = DEFAULT_COPPER_THICKNESS_UM,
    min_width_mm: float = MIN_TRACK_WIDTH_MM,
) -> float:
    """Місток до модуля 6: мінімальна ширина доріжки живлення двигуна
    на платі (IPC-2221, `pcb_norms.required_track_width_mm`) за струмом,
    порахованим із заданого моменту навантаження."""
    current_a = current_under_load_a(motor, torque_nm)
    return required_track_width_mm(
        current_a,
        temperature_rise_c=temperature_rise_c,
        copper_thickness_um=copper_thickness_um,
        min_width_mm=min_width_mm,
    )
