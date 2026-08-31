"""Тести балки модуля 12 — вага, кут нахилу, згин, прогин, перевірка міцності.

Ключове число з завдання — "прогин балки" — перевірене вручну в
`test_evaluate_beam_hand_verified_simply_supported`.
"""

import math

import pytest

from kovadlo.beam import (
    Beam,
    BeamCheckResult,
    LoadScheme,
    Structure,
    bending_moment_max_nmm,
    bending_stress_mpa,
    evaluate_beam,
    max_deflection_mm,
)
from kovadlo.geometry3d import Point3
from kovadlo.materials import Material
from kovadlo.steel_profiles import IBeamProfile, RoundBarProfile

STEEL = Material(name="Сталь конструкційна S235JR", density_kg_m3=7850)
I_BEAM = IBeamProfile(height=100, flange_width=50, web_thickness=5, flange_thickness=7)


def test_beam_length_and_weight_hand_verified():
    beam = Beam(start=Point3(0, 0, 0), end=Point3(3000, 0, 0), profile=I_BEAM, material=STEEL)
    assert beam.length_mm == pytest.approx(3000.0)

    area_mm2 = I_BEAM.cross_section_area_mm2()  # 1130 мм² (перевірено в test_steel_profiles.py)
    volume_mm3 = area_mm2 * 3000
    expected_mass_kg = volume_mm3 * 7850 / 1_000_000_000.0
    assert beam.volume_mm3 == pytest.approx(volume_mm3)
    assert beam.weight_kg == pytest.approx(expected_mass_kg)
    assert beam.weight_n == pytest.approx(expected_mass_kg * 9.81)


def test_beam_weight_requires_density():
    beam = Beam(
        start=Point3(0, 0, 0), end=Point3(1000, 0, 0), profile=I_BEAM, material=Material(name="без густини")
    )
    with pytest.raises(ValueError):
        beam.weight_kg


def test_beam_angle_horizontal():
    beam = Beam(start=Point3(0, 0, 0), end=Point3(4000, 0, 0), profile=I_BEAM, material=STEEL)
    assert beam.angle_to_horizontal_deg == pytest.approx(0.0)
    assert beam.angle_to_vertical_deg == pytest.approx(90.0)


def test_beam_angle_vertical():
    beam = Beam(start=Point3(0, 0, 0), end=Point3(0, 2500, 0), profile=I_BEAM, material=STEEL)
    assert beam.angle_to_horizontal_deg == pytest.approx(90.0)
    assert beam.angle_to_vertical_deg == pytest.approx(0.0)


def test_beam_angle_incline_hand_verified():
    # Проекція 3000 по x, підйом 1500 по y -> кут до горизонталі = arcsin(1500/L)
    beam = Beam(start=Point3(0, 0, 0), end=Point3(3000, 1500, 0), profile=I_BEAM, material=STEEL)
    length = math.hypot(3000, 1500)
    expected_angle_h = math.degrees(math.asin(1500 / length))
    assert beam.length_mm == pytest.approx(length)
    assert beam.angle_to_horizontal_deg == pytest.approx(expected_angle_h)
    assert beam.angle_to_vertical_deg == pytest.approx(90.0 - expected_angle_h)


def test_bending_moment_schemes_hand_verified():
    load, length = 5000.0, 3000.0
    assert bending_moment_max_nmm(load, length, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT) == pytest.approx(
        load * length / 4
    )
    assert bending_moment_max_nmm(load, length, LoadScheme.SIMPLY_SUPPORTED_UNIFORM) == pytest.approx(
        load * length / 8
    )
    assert bending_moment_max_nmm(load, length, LoadScheme.CANTILEVER_END_POINT) == pytest.approx(load * length)
    assert bending_moment_max_nmm(load, length, LoadScheme.CANTILEVER_UNIFORM) == pytest.approx(load * length / 2)


def test_bending_stress_hand_verified():
    # Круглий пруток d=20: W = π/32·20³ = 785.398 мм³ (з test_steel_profiles.py)
    profile = RoundBarProfile(diameter=20)
    w = profile.section_modulus_mm3()
    moment = 100_000.0  # Н·мм
    assert bending_stress_mpa(moment, w) == pytest.approx(moment / w)
    assert bending_stress_mpa(moment, w) == pytest.approx(100_000 / (math.pi / 32 * 8000))


def test_deflection_hand_verified_simply_supported_center_point():
    # δ = P·L³ / (48·E·I) — класична формула прогину балки посередині
    # прольоту під зосередженою силою (опір матеріалів).
    load, length, e, i = 5000.0, 3000.0, 210_000.0, I_BEAM.moment_of_inertia_mm4()
    expected = load * length**3 / (48 * e * i)
    actual = max_deflection_mm(load, length, e, i, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT)
    assert actual == pytest.approx(expected)
    assert actual == pytest.approx(7.51792473735378, rel=1e-9)


def test_deflection_cantilever_end_point_hand_verified():
    # δ = P·L³/(3EI) — консоль із силою на кінці, у 16 разів більша за
    # шарнірно оперту балку з тим самим P, L, EI (48/3 = 16) — гарний
    # незалежний спосіб перевірити коефіцієнт.
    load, length, e, i = 1000.0, 2000.0, 210_000.0, I_BEAM.moment_of_inertia_mm4()
    simply = max_deflection_mm(load, length, e, i, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT)
    cantilever = max_deflection_mm(load, length, e, i, LoadScheme.CANTILEVER_END_POINT)
    assert cantilever == pytest.approx(simply * 16)


def test_deflection_rejects_non_positive_ei():
    with pytest.raises(ValueError):
        max_deflection_mm(1000.0, 2000.0, 0.0, 100.0, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT)


def test_evaluate_beam_hand_verified_simply_supported():
    beam = Beam(start=Point3(0, 0, 0), end=Point3(3000, 0, 0), profile=I_BEAM, material=STEEL, name="Балка 1")
    result = evaluate_beam(beam, 5000.0, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT, yield_strength_mpa=235.0)

    assert isinstance(result, BeamCheckResult)
    length = 3000.0
    w = I_BEAM.section_modulus_mm3()
    i_val = I_BEAM.moment_of_inertia_mm4()
    expected_moment = 5000.0 * length / 4
    expected_stress = expected_moment / w
    expected_deflection = 5000.0 * length**3 / (48 * 210_000.0 * i_val)

    assert result.moment_max_nmm == pytest.approx(expected_moment)
    assert result.stress_mpa == pytest.approx(expected_stress)
    assert result.deflection_mm == pytest.approx(expected_deflection)
    assert result.allowable_stress_mpa == pytest.approx(235.0 / 1.5)
    assert result.deflection_limit_mm == pytest.approx(length / 250.0)
    assert result.safety_margin == pytest.approx(235.0 / expected_stress)
    assert result.passes_strength is True
    assert result.passes_deflection is True
    assert result.passes is True


def test_evaluate_beam_fails_strength_with_overload():
    beam = Beam(start=Point3(0, 0, 0), end=Point3(3000, 0, 0), profile=I_BEAM, material=STEEL)
    # Величезне навантаження — точно перевищить допустиме напруження.
    result = evaluate_beam(beam, 500_000.0, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT, yield_strength_mpa=235.0)
    assert result.passes_strength is False
    assert result.passes is False


def test_evaluate_beam_requires_elastic_modulus_for_unknown_material():
    unknown = Material(name="Невідомий метал", density_kg_m3=7000)
    beam = Beam(start=Point3(0, 0, 0), end=Point3(2000, 0, 0), profile=I_BEAM, material=unknown)
    with pytest.raises(ValueError):
        evaluate_beam(beam, 1000.0, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT, yield_strength_mpa=200.0)

    # З явно переданим модулем пружності — рахує без бази.
    result = evaluate_beam(
        beam, 1000.0, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT, yield_strength_mpa=200.0, elastic_modulus_mpa=200_000.0
    )
    assert result.moment_max_nmm > 0


def test_evaluate_beam_rejects_negative_load():
    beam = Beam(start=Point3(0, 0, 0), end=Point3(2000, 0, 0), profile=I_BEAM, material=STEEL)
    with pytest.raises(ValueError):
        evaluate_beam(beam, -100.0, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT, yield_strength_mpa=200.0)


def test_structure_total_weight_hand_verified():
    beam1 = Beam(start=Point3(0, 0, 0), end=Point3(3000, 0, 0), profile=I_BEAM, material=STEEL, name="Балка 1")
    beam2 = Beam(start=Point3(0, 0, 0), end=Point3(2000, 0, 0), profile=I_BEAM, material=STEEL, name="Балка 2")
    structure = Structure()
    structure.add(beam1)
    structure.add(beam2)

    expected_total_kg = beam1.weight_kg + beam2.weight_kg
    assert structure.total_weight_kg == pytest.approx(expected_total_kg)
    assert structure.total_weight_n == pytest.approx(expected_total_kg * 9.81)


def test_structure_rejects_duplicate_name():
    beam1 = Beam(start=Point3(0, 0, 0), end=Point3(1000, 0, 0), profile=I_BEAM, material=STEEL, name="Балка 1")
    beam2 = Beam(start=Point3(0, 0, 0), end=Point3(1000, 0, 0), profile=I_BEAM, material=STEEL, name="Балка 1")
    structure = Structure()
    structure.add(beam1)
    with pytest.raises(ValueError):
        structure.add(beam2)


def test_structure_auto_names_unnamed_beams():
    structure = Structure()
    structure.add(Beam(start=Point3(0, 0, 0), end=Point3(1000, 0, 0), profile=I_BEAM, material=STEEL))
    structure.add(Beam(start=Point3(0, 0, 0), end=Point3(1000, 0, 0), profile=I_BEAM, material=STEEL))
    assert set(structure.beams.keys()) == {"балка 1", "балка 2"}
