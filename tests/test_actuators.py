"""Тести виконавчих механізмів модуля 13 — адаптери для Motor/Actuator."""

import pytest

from kovadlo.actuators import Actuator, ActuatorKind, actuator_current_a, actuator_kind_label, actuator_voltage_v
from kovadlo.motor import Motor, MotorKind


def test_actuator_power_hand_verified():
    relay = Actuator(name="Реле К1", kind=ActuatorKind.RELAY, voltage_v=12.0, current_a=0.05, actuation_time_s=0.02)
    assert relay.power_w == pytest.approx(0.6)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(name="x", kind=ActuatorKind.VALVE, voltage_v=0.0, current_a=0.1, actuation_time_s=1.0),
        dict(name="x", kind=ActuatorKind.VALVE, voltage_v=12.0, current_a=-0.1, actuation_time_s=1.0),
        dict(name="x", kind=ActuatorKind.VALVE, voltage_v=12.0, current_a=0.1, actuation_time_s=-1.0),
    ],
)
def test_actuator_rejects_bad_params(kwargs):
    with pytest.raises(ValueError):
        Actuator(**kwargs)


def test_adapters_work_for_plain_actuator():
    lock = Actuator(name="Замок", kind=ActuatorKind.LOCK, voltage_v=12.0, current_a=0.4, actuation_time_s=0.3)
    assert actuator_voltage_v(lock) == pytest.approx(12.0)
    assert actuator_current_a(lock) == pytest.approx(0.4)
    assert actuator_kind_label(lock) == "електромагнітний замок"


def test_adapters_work_for_motor_without_modifying_motor_class():
    motor = Motor(name="М1", kind=MotorKind.DC_BRUSHED, voltage_v=24.0, nominal_current_a=3.0, max_torque_nm=1.0)
    assert actuator_voltage_v(motor) == pytest.approx(24.0)
    assert actuator_current_a(motor) == pytest.approx(3.0)
    assert actuator_kind_label(motor) == "колекторний DC"


def test_actuator_kinds_have_expected_ukrainian_labels():
    expected = {
        ActuatorKind.RELAY: "реле",
        ActuatorKind.CONTACTOR: "контактор",
        ActuatorKind.LOCK: "електромагнітний замок",
        ActuatorKind.SOLENOID: "соленоїд",
        ActuatorKind.VALVE: "клапан",
    }
    for kind, label in expected.items():
        assert kind.value == label
