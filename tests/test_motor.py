"""Тести двигунів модуля 12 — струм під навантаженням, потужність, тепло.

Ключове число з завдання — "струм двигуна під навантаженням" —
перевірене вручну в `test_current_under_load_hand_verified`.
"""

import math

import pytest

from kovadlo.electrical_point import PointKind
from kovadlo.geometry import Point
from kovadlo.motor import (
    Motor,
    MotorKind,
    current_under_load_a,
    heat_dissipation_w,
    motor_pcb_track_width_mm,
    power_input_w,
    to_consumption_point,
    torque_constant_nm_per_a,
)
from kovadlo.pcb_norms import required_track_width_mm
from kovadlo.transmission import power_w, rpm_to_rad_s


def _bldc(**overrides) -> Motor:
    params = dict(
        name="Мотор коліс",
        kind=MotorKind.BLDC,
        voltage_v=24.0,
        nominal_current_a=5.0,
        max_torque_nm=1.0,
        kv_rpm_per_v=200.0,
        efficiency=0.85,
    )
    params.update(overrides)
    return Motor(**params)


def test_motor_validates_params():
    with pytest.raises(ValueError):
        _bldc(voltage_v=0)
    with pytest.raises(ValueError):
        _bldc(nominal_current_a=-1)
    with pytest.raises(ValueError):
        _bldc(max_torque_nm=0)
    with pytest.raises(ValueError):
        _bldc(efficiency=0)
    with pytest.raises(ValueError):
        _bldc(efficiency=1.5)
    with pytest.raises(ValueError):
        _bldc(kv_rpm_per_v=-5)
    with pytest.raises(ValueError):
        _bldc(winding_resistance_ohm=-1)
    with pytest.raises(ValueError):
        _bldc(no_load_current_a=-1)


def test_torque_constant_hand_verified():
    # Kv=200 об/хв/В -> Kt = 60/(2π·200) = 0.047746... Н·м/А
    motor = _bldc()
    expected_kt = 60.0 / (2 * math.pi * 200.0)
    assert torque_constant_nm_per_a(motor) == pytest.approx(expected_kt)


def test_torque_constant_requires_kv():
    motor = _bldc(kv_rpm_per_v=None)
    with pytest.raises(ValueError):
        torque_constant_nm_per_a(motor)


def test_current_under_load_hand_verified():
    # Момент навантаження 0.3 Н·м, Kt = 0.047746 Н·м/А:
    # I = M / Kt = 0.3 / 0.047746 = 6.2832 А (без струму холостого ходу)
    motor = _bldc()
    kt = torque_constant_nm_per_a(motor)
    current = current_under_load_a(motor, 0.3)
    assert current == pytest.approx(0.3 / kt)
    assert current == pytest.approx(6.283185307179586, rel=1e-9)


def test_current_under_load_adds_no_load_current():
    motor = _bldc(no_load_current_a=0.5)
    kt = torque_constant_nm_per_a(motor)
    current = current_under_load_a(motor, 0.3)
    assert current == pytest.approx(0.5 + 0.3 / kt)


def test_current_under_load_rejects_overload():
    motor = _bldc()  # max_torque_nm = 1.0
    with pytest.raises(ValueError):
        current_under_load_a(motor, 2.0)


def test_current_under_load_rejects_negative_torque():
    motor = _bldc()
    with pytest.raises(ValueError):
        current_under_load_a(motor, -0.1)


def test_stepper_current_is_constant_regardless_of_load():
    stepper = Motor(name="Крок", kind=MotorKind.STEPPER, voltage_v=12.0, nominal_current_a=1.5, max_torque_nm=0.4)
    assert current_under_load_a(stepper, 0.1) == pytest.approx(1.5)
    assert current_under_load_a(stepper, 0.39) == pytest.approx(1.5)
    with pytest.raises(ValueError):
        current_under_load_a(stepper, 0.5)


def test_power_input_hand_verified():
    motor = _bldc()
    assert power_input_w(motor, 6.283185307179586) == pytest.approx(24.0 * 6.283185307179586)


def test_heat_dissipation_energy_balance_hand_verified():
    motor = _bldc()
    torque, current = 0.3, current_under_load_a(_bldc(), 0.3)
    omega = rpm_to_rad_s(1000.0)
    power_in = power_input_w(motor, current)
    power_out = power_w(torque, omega)
    expected_heat = power_in - power_out
    actual_heat = heat_dissipation_w(motor, current, torque_nm=torque, angular_velocity_rad_s=omega)
    assert actual_heat == pytest.approx(expected_heat)


def test_heat_dissipation_i2r_hand_verified():
    dc = Motor(
        name="dc", kind=MotorKind.DC_BRUSHED, voltage_v=12.0, nominal_current_a=2.0, max_torque_nm=0.5,
        winding_resistance_ohm=1.5,
    )
    # I²R = 2² · 1.5 = 6 Вт
    assert heat_dissipation_w(dc, 2.0) == pytest.approx(6.0)


def test_heat_dissipation_efficiency_fallback_hand_verified():
    dc = Motor(name="dc2", kind=MotorKind.DC_BRUSHED, voltage_v=12.0, nominal_current_a=2.0, max_torque_nm=0.5, efficiency=0.7)
    # втрати = U·I·(1-η) = 12·2·0.3 = 7.2 Вт
    assert heat_dissipation_w(dc, 2.0) == pytest.approx(7.2)


def test_to_consumption_point_uses_socket_kind_and_real_power():
    motor = _bldc()
    current = 6.283185307179586
    point = to_consumption_point(motor, Point(1000, 2000), current, name="М1")
    assert point.kind is PointKind.SOCKET
    assert point.name == "М1"
    assert point.position == Point(1000, 2000)
    assert point.power_w == pytest.approx(motor.voltage_v * current)


def test_motor_pcb_track_width_matches_direct_call():
    motor = _bldc()
    torque = 0.3
    current = current_under_load_a(motor, torque)
    assert motor_pcb_track_width_mm(motor, torque) == pytest.approx(required_track_width_mm(current))
