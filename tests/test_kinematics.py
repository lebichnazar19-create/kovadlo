"""Тести кінематики модуля 12 — швидкість колеса, час розгону, чи вистачить моменту."""

import math

import pytest

from kovadlo.kinematics import (
    available_force_n,
    can_move_mass,
    required_force_to_move_n,
    time_to_speed_s,
    wheel_angular_velocity_rad_s,
    wheel_linear_speed_m_s,
)


def test_wheel_linear_speed_hand_verified():
    # d=300 мм (r=0.15 м), ω=20 рад/с -> v = 20·0.15 = 3.0 м/с
    assert wheel_linear_speed_m_s(300, 20.0) == pytest.approx(3.0)


def test_wheel_angular_velocity_is_inverse_of_speed():
    speed = wheel_linear_speed_m_s(300, 20.0)
    assert wheel_angular_velocity_rad_s(300, speed) == pytest.approx(20.0)


def test_wheel_linear_speed_rejects_non_positive_diameter():
    with pytest.raises(ValueError):
        wheel_linear_speed_m_s(0, 10.0)


def test_time_to_speed_hand_verified():
    # d=300мм (r=0.15), ціль 5 м/с, маса 50 кг, момент 10 Н·м,
    # власний момент інерції обертових частин 0.5 кг·м².
    # ω_ціль = 5/0.15 = 33.333...; I_еф = 0.5 + 50·0.15² = 0.5+1.125=1.625
    # t = I_еф·ω_ціль / M = 1.625·33.333/10 = 5.41667 с
    r = 0.15
    target_omega = 5.0 / r
    i_eff = 0.5 + 50.0 * r**2
    expected = i_eff * target_omega / 10.0
    actual = time_to_speed_s(5.0, 300.0, 50.0, 10.0, 0.5)
    assert actual == pytest.approx(expected)
    assert actual == pytest.approx(5.416666666666667, rel=1e-9)


def test_time_to_speed_without_rotational_inertia():
    # без rotational_inertia (0.0) — лише маса, приведена через r².
    r = 0.2
    target_omega = 2.0 / r
    i_eff = 20.0 * r**2
    expected = i_eff * target_omega / 5.0
    assert time_to_speed_s(2.0, 400.0, 20.0, 5.0) == pytest.approx(expected)


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(target_speed_m_s=-1, wheel_diameter_mm=300, mass_kg=50, torque_nm=10),
        dict(target_speed_m_s=5, wheel_diameter_mm=300, mass_kg=-1, torque_nm=10),
        dict(target_speed_m_s=5, wheel_diameter_mm=300, mass_kg=50, torque_nm=0),
        dict(target_speed_m_s=5, wheel_diameter_mm=300, mass_kg=50, torque_nm=10, rotational_inertia_kg_m2=-1),
    ],
)
def test_time_to_speed_rejects_bad_inputs(kwargs):
    with pytest.raises(ValueError):
        time_to_speed_s(**kwargs)


def test_required_force_to_move_flat_no_friction_is_zero():
    assert required_force_to_move_n(100.0, friction_coefficient=0.0, incline_deg=0.0) == pytest.approx(0.0)


def test_required_force_to_move_hand_verified():
    # m=100 кг, μ=0.3, схил 10°: F = m·g·(sin10° + μ·cos10°)
    mass, mu, incline = 100.0, 0.3, 10.0
    expected = mass * 9.81 * (math.sin(math.radians(incline)) + mu * math.cos(math.radians(incline)))
    assert required_force_to_move_n(mass, mu, incline) == pytest.approx(expected)
    assert required_force_to_move_n(mass, mu, incline) == pytest.approx(460.1777840027514, rel=1e-9)


def test_available_force_hand_verified():
    # M=20 Н·м, d=300мм (r=0.15): F = 20/0.15 = 133.333 Н
    assert available_force_n(20.0, 300.0) == pytest.approx(20.0 / 0.15)


def test_can_move_mass_true_when_torque_enough():
    # Легка маса на пласкій поверхні з невеликим тертям — малого моменту досить.
    assert can_move_mass(torque_nm=5.0, wheel_diameter_mm=300, mass_kg=10.0, friction_coefficient=0.2) is True


def test_can_move_mass_false_when_torque_not_enough():
    # Та сама конфігурація, що й у test_required_force_to_move_hand_verified,
    # де required (460 Н) сильно перевищує available (133 Н) при M=20 Н·м.
    assert can_move_mass(torque_nm=20.0, wheel_diameter_mm=300, mass_kg=100.0, friction_coefficient=0.3, incline_deg=10.0) is False


def test_can_move_mass_boundary_equal_is_true():
    # На межі (available == required) перевірка нестрога (>=) — проходить.
    mass, mu = 50.0, 0.25
    required = required_force_to_move_n(mass, mu, 0.0)
    wheel_diameter_mm = 400.0
    radius_m = 0.2
    torque_at_boundary = required * radius_m
    assert can_move_mass(torque_at_boundary, wheel_diameter_mm, mass, mu, 0.0) is True
