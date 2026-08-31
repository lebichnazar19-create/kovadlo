"""
Вентиляція (8.2): повітропровід як полілінія, розрахунок повітрообміну,
швидкості й втрат тиску, підбір діаметра й вентилятора.

Повітропровід — та сама ідея, що й кабельна траса (модуль 4) чи доріжка
плати (модуль 6): полілінія з `kovadlo.geometry`, прив'язана до кута
через ту саму `snap_point`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .geometry import MM_PER_M, Point, snap_point
from .material_spec import MaterialSpec
from .ventilation_norms import (
    AIR_CHANGES_PER_HOUR,
    AIR_DENSITY_KG_M3,
    DEFAULT_FRICTION_FACTOR,
    MAX_RECOMMENDED_VELOCITY_M_S,
    MINIMUM_EXHAUST_M3_H,
    STANDARD_FANS,
    STANDARD_ROUND_DUCT_DIAMETERS_MM,
    VentilatedRoomKind,
)


class DuctShape(Enum):
    """Форма перерізу повітропроводу."""

    ROUND = "круглий"
    RECTANGULAR = "прямокутний"


@dataclass
class Duct:
    """Повітропровід: полілінія (мм), переріз, матеріал (посилання на
    базу модуля 7 — сам об'єкт `MaterialSpec`, за іменем якого можна
    знайти повний запис через `MaterialDatabase.find_by_name`)."""

    points: list[Point]
    shape: DuctShape
    diameter_mm: float | None = None  # для ROUND
    width_mm: float | None = None  # для RECTANGULAR
    height_mm: float | None = None  # для RECTANGULAR
    material: MaterialSpec | None = None

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("Повітропровід має містити щонайменше 2 точки")
        if self.shape is DuctShape.ROUND:
            if not self.diameter_mm or self.diameter_mm <= 0:
                raise ValueError("Для круглого повітропроводу потрібен додатний diameter_mm")
        else:
            if not self.width_mm or not self.height_mm or self.width_mm <= 0 or self.height_mm <= 0:
                raise ValueError("Для прямокутного повітропроводу потрібні додатні width_mm і height_mm")

    @property
    def length_mm(self) -> float:
        return sum(self.points[i].distance_to(self.points[i + 1]) for i in range(len(self.points) - 1))

    @property
    def length_m(self) -> float:
        return self.length_mm / MM_PER_M

    def cross_section_area_m2(self) -> float:
        """Площа перерізу каналу, м²."""
        if self.shape is DuctShape.ROUND:
            radius_m = (self.diameter_mm / MM_PER_M) / 2
            return math.pi * radius_m**2
        return (self.width_mm / MM_PER_M) * (self.height_mm / MM_PER_M)

    def hydraulic_diameter_m(self) -> float:
        """Гідравлічний діаметр D_h = 4·A/P (для круглого дорівнює діаметру)."""
        if self.shape is DuctShape.ROUND:
            return self.diameter_mm / MM_PER_M
        a_m, b_m = self.width_mm / MM_PER_M, self.height_mm / MM_PER_M
        return 4 * (a_m * b_m) / (2 * (a_m + b_m))


def build_duct(
    start: Point,
    waypoints: list[Point],
    shape: DuctShape,
    *,
    diameter_mm: float | None = None,
    width_mm: float | None = None,
    height_mm: float | None = None,
    material: MaterialSpec | None = None,
    snap: bool = True,
    snap_step: float = 90.0,
) -> Duct:
    """Будує повітропровід від `start` через `waypoints` із прив'язкою
    кута до `snap_step` (90° за замовчуванням — та сама `snap_point`,
    що й контур кімнати чи кабельна траса)."""
    if not waypoints:
        raise ValueError("Потрібна хоча б одна точка призначення")
    points = [start]
    for raw in waypoints:
        points.append(snap_point(points[-1], raw, snap_step) if snap else raw)
    return Duct(points=points, shape=shape, diameter_mm=diameter_mm, width_mm=width_mm, height_mm=height_mm, material=material)


def required_airflow_m3_h(room_kind: VentilatedRoomKind, volume_m3: float) -> float:
    """Потрібний повітрообмін, м³/год: фіксована мінімальна витяжка для
    "мокрих" приміщень або кратність повітрообміну × об'єм для решти."""
    if volume_m3 <= 0:
        raise ValueError("Об'єм приміщення має бути додатним")
    if room_kind in MINIMUM_EXHAUST_M3_H:
        return MINIMUM_EXHAUST_M3_H[room_kind]
    if room_kind in AIR_CHANGES_PER_HOUR:
        return AIR_CHANGES_PER_HOUR[room_kind] * volume_m3
    raise ValueError(f"Немає норми повітрообміну для {room_kind}")


def air_velocity_m_s(airflow_m3_h: float, area_m2: float) -> float:
    """Швидкість повітря в каналі, м/с."""
    if area_m2 <= 0:
        raise ValueError("Площа перерізу має бути додатною")
    return (airflow_m3_h / 3600.0) / area_m2


def pressure_loss_pa(duct: Duct, airflow_m3_h: float, *, friction_factor: float = DEFAULT_FRICTION_FACTOR) -> float:
    """Втрати тиску на тертя по довжині ділянки (формула Дарсі-Вейсбаха):

        Δp = λ · (L / D_h) · (ρ·v² / 2)
    """
    area = duct.cross_section_area_m2()
    velocity = air_velocity_m_s(airflow_m3_h, area)
    d_h = duct.hydraulic_diameter_m()
    return friction_factor * (duct.length_m / d_h) * (AIR_DENSITY_KG_M3 * velocity**2 / 2)


def select_round_duct_diameter_mm(airflow_m3_h: float, *, max_velocity_m_s: float = MAX_RECOMMENDED_VELOCITY_M_S) -> float:
    """Найменший стандартний діаметр круглого повітропроводу, за якого
    швидкість не перевищує `max_velocity_m_s`."""
    if airflow_m3_h <= 0:
        raise ValueError("Витрата повітря має бути додатною")
    flow_m3_s = airflow_m3_h / 3600.0
    for diameter_mm in STANDARD_ROUND_DUCT_DIAMETERS_MM:
        area = math.pi * (diameter_mm / MM_PER_M / 2) ** 2
        velocity = flow_m3_s / area
        if velocity <= max_velocity_m_s:
            return diameter_mm
    raise ValueError(
        f"Витрата {airflow_m3_h:.0f} м³/год завелика для стандартного ряду діаметрів "
        f"при швидкості ≤ {max_velocity_m_s:g} м/с — потрібен більший канал поза рядом"
    )


def select_fan(required_flow_m3_h: float, required_pressure_pa: float) -> tuple[str, float, float]:
    """Найменший вентилятор орієнтовного каталогу, що задовольняє і
    витрату, і тиск. Повертає (назва, макс_витрата, макс_тиск)."""
    for max_flow, max_pressure, name in STANDARD_FANS:
        if max_flow >= required_flow_m3_h and max_pressure >= required_pressure_pa:
            return name, max_flow, max_pressure
    raise ValueError(
        f"Немає вентилятора в орієнтовному каталозі на витрату {required_flow_m3_h:.0f} м³/год "
        f"і тиск {required_pressure_pa:.0f} Па"
    )
