"""Тести вала й обертових деталей модуля 12 (момент інерції обертової маси)."""

import math

import pytest

from kovadlo.geometry3d import Point3
from kovadlo.materials import Material
from kovadlo.shaft import (
    Shaft,
    disk_moment_of_inertia_kg_m2,
    ring_moment_of_inertia_kg_m2,
    wheel_moment_of_inertia_kg_m2,
)

STEEL = Material(name="Сталь конструкційна S235JR", density_kg_m3=7850)


def test_shaft_length_volume_mass_hand_verified():
    shaft = Shaft(axis_start=Point3(0, 0, 0), axis_end=Point3(0, 0, 500), diameter_mm=30, material=STEEL)
    assert shaft.length_mm == pytest.approx(500.0)

    expected_volume = math.pi / 4 * 30**2 * 500
    expected_mass = expected_volume * 7850 / 1_000_000_000.0
    assert shaft.volume_mm3 == pytest.approx(expected_volume)
    assert shaft.mass_kg == pytest.approx(expected_mass)


def test_shaft_moment_of_inertia_hand_verified():
    shaft = Shaft(axis_start=Point3(0, 0, 0), axis_end=Point3(0, 0, 500), diameter_mm=30, material=STEEL)
    r_m = 0.015
    expected = 0.5 * shaft.mass_kg * r_m**2
    assert shaft.mass_moment_of_inertia_kg_m2 == pytest.approx(expected)


def test_shaft_requires_positive_diameter():
    with pytest.raises(ValueError):
        Shaft(axis_start=Point3(0, 0, 0), axis_end=Point3(0, 0, 500), diameter_mm=0, material=STEEL)


def test_shaft_mass_requires_density():
    no_density = Material(name="без густини")
    shaft = Shaft(axis_start=Point3(0, 0, 0), axis_end=Point3(0, 0, 500), diameter_mm=30, material=no_density)
    with pytest.raises(ValueError):
        shaft.mass_kg


def test_disk_moment_of_inertia_hand_verified():
    # I = ½·10·0.2² = 0.2 кг·м²
    assert disk_moment_of_inertia_kg_m2(10.0, 0.2) == pytest.approx(0.2)


def test_ring_moment_of_inertia_hand_verified():
    # I = 10·0.2² = 0.4 кг·м² — рівно вдвічі більше за диск тієї самої
    # маси й радіуса (уся маса на ободі, а не розподілена по площі).
    assert ring_moment_of_inertia_kg_m2(10.0, 0.2) == pytest.approx(0.4)
    assert ring_moment_of_inertia_kg_m2(10.0, 0.2) == pytest.approx(2 * disk_moment_of_inertia_kg_m2(10.0, 0.2))


def test_wheel_reduces_to_disk_when_inner_radius_zero():
    assert wheel_moment_of_inertia_kg_m2(10.0, 0.2, 0.0) == pytest.approx(disk_moment_of_inertia_kg_m2(10.0, 0.2))


def test_wheel_thick_ring_hand_verified():
    # I = ½·10·(0.3² + 0.2²) = ½·10·0.13 = 0.65 кг·м²
    assert wheel_moment_of_inertia_kg_m2(10.0, 0.3, 0.2) == pytest.approx(0.65)


def test_wheel_rejects_inner_radius_greater_than_outer():
    with pytest.raises(ValueError):
        wheel_moment_of_inertia_kg_m2(10.0, 0.2, 0.3)


def test_wheel_rejects_negative_inner_radius():
    with pytest.raises(ValueError):
        wheel_moment_of_inertia_kg_m2(10.0, 0.2, -0.1)
