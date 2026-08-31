"""
Приклад для тестів (модуль 13): автоматична розсувна брама — два
кінцевики (відкрито/закрито), кнопка, фотобар'єр безпеки, двигун через
редуктор. Повний цикл: закрито -> відкривається -> відкрито ->
закривається -> закрито, з аварійним таймаутом і безпечним реверсом
при перекритті фотобар'єру під час закривання.

Двигун під'єднаний до контролера НЕ напряму, а через два контактори
(вперед/назад) — реальна практика для навантажень, чий струм перевищує
допустимий на вихід контролера (`controller.py`); сам двигун живиться
від окремого силового кола, яке контактор лише вмикає/вимикає.
"""

from __future__ import annotations

from dataclasses import dataclass

from .actuators import Actuator, ActuatorKind
from .automation_logic import Action, Condition, Rule, Scenario, TimerSpec
from .controller import Controller, ControllerSpec
from .kinematics import wheel_linear_speed_m_s
from .motor import Motor, MotorKind
from .sensors import OutputType, Sensor, SensorKind
from .transmission import GearboxTransmission, rpm_to_rad_s

GATE_STATES = {"ЗАКРИТО", "ВІДКРИВАЄТЬСЯ", "ВІДКРИТО", "ЗАКРИВАЄТЬСЯ", "АВАРІЯ"}


def gate_cycle_time_s(
    travel_distance_mm: float, motor_rpm: float, transmission: GearboxTransmission, drive_wheel_diameter_mm: float
) -> float:
    """Час повного ходу брами (відкриття чи закриття), с: довжина ходу
    поділена на лінійну швидкість приводного колеса/шестерні рейки
    (модуль 12: `GearboxTransmission.output_rpm`, `wheel_linear_speed_m_s`)."""
    if travel_distance_mm <= 0:
        raise ValueError("Довжина ходу брами має бути додатною")
    if motor_rpm <= 0:
        raise ValueError("Оберти двигуна мають бути додатними")
    output_rpm = transmission.output_rpm(motor_rpm)
    output_omega = rpm_to_rad_s(output_rpm)
    speed_m_s = wheel_linear_speed_m_s(drive_wheel_diameter_mm, output_omega)
    if speed_m_s <= 0:
        raise ValueError("Розрахована швидкість приводу має бути додатною")
    return (travel_distance_mm / 1000.0) / speed_m_s


def recommended_timeout_s(cycle_time_s: float, margin_s: float = 5.0) -> float:
    """Рекомендована тривалість аварійного таймауту: час циклу + запас
    (кінцевик міг забруднитись/не спрацювати, тертя вище розрахункового)."""
    if cycle_time_s <= 0:
        raise ValueError("Час циклу має бути додатним")
    if margin_s < 0:
        raise ValueError("Запас часу не може бути від'ємним")
    return cycle_time_s + margin_s


def _build_gate_rules(timer_name: str) -> list[Rule]:
    return [
        Rule(
            "Фотобар'єр під час закривання",
            Condition(state_in="ЗАКРИВАЄТЬСЯ", inputs={"фотобар'єр_перекрито": True}),
            Action(new_state="ВІДКРИВАЄТЬСЯ", outputs={"двигун_назад": False, "двигун_вперед": True}, start_timer=timer_name),
        ),
        Rule(
            "Кнопка із закрито",
            Condition(state_in="ЗАКРИТО", inputs={"кнопка": True}),
            Action(new_state="ВІДКРИВАЄТЬСЯ", outputs={"двигун_вперед": True}, start_timer=timer_name),
        ),
        Rule(
            "Кнопка з відкрито",
            Condition(state_in="ВІДКРИТО", inputs={"кнопка": True}),
            Action(new_state="ЗАКРИВАЄТЬСЯ", outputs={"двигун_назад": True}, start_timer=timer_name),
        ),
        Rule(
            "Кінець відкриття",
            Condition(state_in="ВІДКРИВАЄТЬСЯ", inputs={"кінцевик_відкрито": True}),
            Action(new_state="ВІДКРИТО", outputs={"двигун_вперед": False}, stop_timer=timer_name),
        ),
        Rule(
            "Кінець закриття",
            Condition(state_in="ЗАКРИВАЄТЬСЯ", inputs={"кінцевик_закрито": True}),
            Action(new_state="ЗАКРИТО", outputs={"двигун_назад": False}, stop_timer=timer_name),
        ),
        Rule(
            "Таймаут відкриття",
            Condition(state_in="ВІДКРИВАЄТЬСЯ", timer_expired=timer_name),
            Action(new_state="АВАРІЯ", outputs={"двигун_вперед": False}),
        ),
        Rule(
            "Таймаут закриття",
            Condition(state_in="ЗАКРИВАЄТЬСЯ", timer_expired=timer_name),
            Action(new_state="АВАРІЯ", outputs={"двигун_назад": False}),
        ),
        Rule(
            "Скидання аварії",
            Condition(state_in="АВАРІЯ", inputs={"скидання": True}),
            # Спрощення прикладу: скидання повертає систему в ЗАКРИТО без
            # перевірки реального положення полотна — на практиці оператор
            # перед скиданням має вручну переконатися в безпечному стані
            # (чи проїхати браму на кінцевик закриття в ручному режимі).
            Action(new_state="ЗАКРИТО"),
        ),
    ]


@dataclass
class GateSystem:
    """Повний зібраний приклад: сценарій, датчики, привід, контролер."""

    scenario: Scenario
    sensors: dict[str, Sensor]
    motor: Motor
    transmission: GearboxTransmission
    controller: Controller
    cycle_time_s: float
    timeout_s: float


def build_gate_scenario(
    *,
    travel_distance_mm: float = 3000.0,
    motor_rpm: float = 3000.0,
    gear_ratio: float = 30.0,
    drive_wheel_diameter_mm: float = 60.0,
    timeout_margin_s: float = 5.0,
) -> GateSystem:
    """Збирає повний приклад автоматичної брами: датчики + привід
    (двигун через редуктор) + контролер + сценарій із розрахованим
    аварійним таймаутом."""
    timer_name = "таймаут_ходу"

    sensors = {
        "кнопка": Sensor(name="Кнопка виклику", kind=SensorKind.BUTTON, output_type=OutputType.DIGITAL, voltage_v=12.0, current_a=0.002),
        "кінцевик_відкрито": Sensor(name="Кінцевик відкриття", kind=SensorKind.LIMIT_SWITCH, output_type=OutputType.DIGITAL, voltage_v=12.0, current_a=0.003),
        "кінцевик_закрито": Sensor(name="Кінцевик закриття", kind=SensorKind.LIMIT_SWITCH, output_type=OutputType.DIGITAL, voltage_v=12.0, current_a=0.003),
        "фотобар'єр_перекрито": Sensor(name="Фотобар'єр безпеки", kind=SensorKind.PHOTOCELL, output_type=OutputType.DIGITAL, voltage_v=12.0, current_a=0.03),
    }

    motor = Motor(
        name="Двигун приводу брами", kind=MotorKind.DC_BRUSHED, voltage_v=24.0, nominal_current_a=4.0,
        max_torque_nm=3.0, efficiency=0.8,
    )
    transmission = GearboxTransmission(gear_ratio=gear_ratio, efficiency=0.9)

    cycle_time_s = gate_cycle_time_s(travel_distance_mm, motor_rpm, transmission, drive_wheel_diameter_mm)
    timeout_s = recommended_timeout_s(cycle_time_s, timeout_margin_s)

    scenario = Scenario(
        name="Автоматична брама",
        states=GATE_STATES,
        initial_state="ЗАКРИТО",
        rules=_build_gate_rules(timer_name),
        timers={timer_name: TimerSpec(timer_name, duration_s=timeout_s)},
        forbidden_transitions={("АВАРІЯ", "ВІДКРИВАЄТЬСЯ"), ("АВАРІЯ", "ЗАКРИВАЄТЬСЯ")},
    )

    controller = Controller(
        spec=ControllerSpec(name="Контролер брами", digital_inputs=5, analog_inputs=0, digital_outputs=2, pwm_outputs=0, max_current_per_output_a=0.5)
    )
    for pin_id, key in zip(("D0", "D1", "D2", "D3"), sensors):
        controller.bind_input(pin_id, sensors[key])

    contactor_forward = Actuator(name="Контактор вперед", kind=ActuatorKind.CONTACTOR, voltage_v=12.0, current_a=0.08, actuation_time_s=0.02)
    contactor_backward = Actuator(name="Контактор назад", kind=ActuatorKind.CONTACTOR, voltage_v=12.0, current_a=0.08, actuation_time_s=0.02)
    controller.bind_output("D4", contactor_forward)
    controller.bind_output("D5", contactor_backward)

    return GateSystem(
        scenario=scenario, sensors=sensors, motor=motor, transmission=transmission, controller=controller,
        cycle_time_s=cycle_time_s, timeout_s=timeout_s,
    )
