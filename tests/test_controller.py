"""Тести контролера модуля 13 — піни, напруги, струм на виході.

Ключове число з завдання — "перевірка струму на виході контролера" —
перевірене вручну в `test_check_flags_output_overcurrent_hand_verified`.
"""

import pytest

from kovadlo.actuators import Actuator, ActuatorKind
from kovadlo.controller import Controller, ControllerSpec, PinIssue
from kovadlo.motor import Motor, MotorKind
from kovadlo.sensors import OutputType, Sensor, SensorKind


def _spec(**overrides) -> ControllerSpec:
    params = dict(name="Контролер", digital_inputs=2, analog_inputs=1, digital_outputs=2, pwm_outputs=1, max_current_per_output_a=0.5)
    params.update(overrides)
    return ControllerSpec(**params)


def _button(voltage_v=5.0) -> Sensor:
    return Sensor(name="Кнопка", kind=SensorKind.BUTTON, output_type=OutputType.DIGITAL, voltage_v=voltage_v, current_a=0.002)


def test_controller_spec_rejects_negative_pin_counts():
    with pytest.raises(ValueError):
        _spec(digital_inputs=-1)
    with pytest.raises(ValueError):
        _spec(analog_inputs=-1)
    with pytest.raises(ValueError):
        _spec(digital_outputs=-1)
    with pytest.raises(ValueError):
        _spec(pwm_outputs=-1)


def test_controller_spec_rejects_non_positive_max_current():
    with pytest.raises(ValueError):
        _spec(max_current_per_output_a=0.0)


def test_bind_input_rejects_duplicate_pin():
    ctrl = Controller(spec=_spec())
    ctrl.bind_input("D2", _button())
    with pytest.raises(ValueError):
        ctrl.bind_input("D2", _button())


def test_bind_output_rejects_duplicate_pin():
    ctrl = Controller(spec=_spec())
    relay = Actuator(name="Реле", kind=ActuatorKind.RELAY, voltage_v=5.0, current_a=0.05, actuation_time_s=0.02)
    ctrl.bind_output("D5", relay)
    with pytest.raises(ValueError):
        ctrl.bind_output("D5", relay)


def test_check_pin_counts_hand_verified():
    ctrl = Controller(spec=_spec(digital_inputs=2, analog_inputs=1, digital_outputs=2, pwm_outputs=1))
    ctrl.bind_input("D2", _button())
    ctrl.bind_input("D3", Sensor(name="Кінцевик", kind=SensorKind.LIMIT_SWITCH, output_type=OutputType.DIGITAL, voltage_v=5.0, current_a=0.002))
    ctrl.bind_input("A0", Sensor(name="Дальномір", kind=SensorKind.DISTANCE, output_type=OutputType.ANALOG, voltage_v=5.0, current_a=0.015))
    ctrl.bind_output("D5", Actuator(name="Реле", kind=ActuatorKind.RELAY, voltage_v=5.0, current_a=0.05, actuation_time_s=0.02))

    result = ctrl.check()
    assert result.digital_inputs_used == 2
    assert result.analog_inputs_used == 1
    assert result.digital_outputs_used == 1
    assert result.pwm_outputs_used == 0
    assert result.enough_pins is True
    assert result.voltage_issues == []
    assert result.current_issues == []
    assert result.passes is True


def test_check_flags_not_enough_digital_inputs():
    ctrl = Controller(spec=_spec(digital_inputs=1))
    ctrl.bind_input("D0", _button())
    ctrl.bind_input("D1", Sensor(name="Кінцевик", kind=SensorKind.LIMIT_SWITCH, output_type=OutputType.DIGITAL, voltage_v=5.0, current_a=0.002))
    result = ctrl.check()
    assert result.digital_inputs_used == 2
    assert result.digital_inputs_available == 1
    assert result.enough_digital_inputs is False
    assert result.passes is False


def test_check_flags_voltage_incompatibility_hand_verified():
    # Датчик на 24В, доступні рейки за замовчуванням 3.3/5/12 В —
    # 24 не збігається з жодною (навіть з допуском 0.3В) -> проблема.
    ctrl = Controller(spec=_spec(digital_inputs=5))
    ctrl.bind_input("D0", Sensor(name="Датчик руху", kind=SensorKind.MOTION, output_type=OutputType.DIGITAL, voltage_v=24.0, current_a=0.02))
    result = ctrl.check()
    assert len(result.voltage_issues) == 1
    assert isinstance(result.voltage_issues[0], PinIssue)
    assert "24.0" in result.voltage_issues[0].message
    assert result.passes is False


def test_check_voltage_compatible_when_matching_rail_provided():
    ctrl = Controller(spec=_spec(digital_inputs=5))
    ctrl.bind_input("D0", Sensor(name="Датчик руху", kind=SensorKind.MOTION, output_type=OutputType.DIGITAL, voltage_v=24.0, current_a=0.02))
    result = ctrl.check(available_voltages_v=(24.0,))
    assert result.voltage_issues == []


def test_check_flags_output_overcurrent_hand_verified():
    # Двигун 3А номінально, дозволено лише 0.5А на вихід контролера —
    # 3.0 > 0.5, отже потрібне проміжне реле.
    ctrl = Controller(spec=_spec(digital_outputs=5, max_current_per_output_a=0.5))
    motor = Motor(name="Двигун брами", kind=MotorKind.DC_BRUSHED, voltage_v=12.0, nominal_current_a=3.0, max_torque_nm=2.0)
    ctrl.bind_output("D6", motor)
    result = ctrl.check()
    assert len(result.current_issues) == 1
    assert "3.000" in result.current_issues[0].message
    assert "0.500" in result.current_issues[0].message
    assert result.passes is False


def test_check_current_ok_within_limit():
    ctrl = Controller(spec=_spec(digital_outputs=5, max_current_per_output_a=0.5))
    relay = Actuator(name="Реле", kind=ActuatorKind.RELAY, voltage_v=5.0, current_a=0.05, actuation_time_s=0.02)
    ctrl.bind_output("D5", relay)
    result = ctrl.check()
    assert result.current_issues == []
    assert result.passes is True
