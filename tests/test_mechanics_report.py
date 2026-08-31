"""Тести текстових звітів модуля 12 — лише перевірка вмісту (без графіки)."""

import pytest

from kovadlo.beam import Beam, LoadScheme, Structure, evaluate_beam
from kovadlo.geometry3d import Point3
from kovadlo.materials import Material
from kovadlo.mechanics_report import format_beam_report, format_drive_report, format_structure_report
from kovadlo.motor import Motor, MotorKind, current_under_load_a
from kovadlo.steel_profiles import IBeamProfile
from kovadlo.transmission import GearboxTransmission

STEEL = Material(name="Сталь конструкційна S235JR", density_kg_m3=7850)
I_BEAM = IBeamProfile(height=100, flange_width=50, web_thickness=5, flange_thickness=7)


def _beam_and_result(name="Балка 1", load_n=5000.0, scheme=LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT):
    beam = Beam(start=Point3(0, 0, 0), end=Point3(3000, 0, 0), profile=I_BEAM, material=STEEL, name=name)
    result = evaluate_beam(beam, load_n, scheme, yield_strength_mpa=235.0)
    return beam, result


def test_format_beam_report_contains_key_numbers():
    beam, result = _beam_and_result()
    report = format_beam_report(beam, result)

    assert "Балка 1" in report
    assert beam.profile.name in report
    assert beam.material.name in report
    assert "ПРОХОДИТЬ" in report
    assert f"{result.stress_mpa:.1f}" in report
    assert f"{result.deflection_mm:.2f}" in report


def test_format_beam_report_marks_failure():
    beam, result = _beam_and_result(load_n=500_000.0)
    assert result.passes is False
    report = format_beam_report(beam, result)
    assert "НЕ ПРОХОДИТЬ" in report


def test_format_beam_report_skips_weight_without_density():
    no_density = Material(name="без густини")
    beam = Beam(start=Point3(0, 0, 0), end=Point3(1000, 0, 0), profile=I_BEAM, material=no_density)
    result = evaluate_beam(
        beam, 100.0, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT, yield_strength_mpa=200.0, elastic_modulus_mpa=200_000.0
    )
    report = format_beam_report(beam, result)
    assert "Вага:" not in report


def test_format_structure_report_hand_verified_total_weight():
    beam1, result1 = _beam_and_result(name="Балка 1")
    beam2 = Beam(start=Point3(0, 0, 0), end=Point3(2000, 0, 0), profile=I_BEAM, material=STEEL, name="Балка 2")
    result2 = evaluate_beam(beam2, 500.0, LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT, yield_strength_mpa=235.0)

    structure = Structure()
    structure.add(beam1)
    structure.add(beam2)
    report = format_structure_report(structure, {"Балка 1": result1, "Балка 2": result2})

    expected_total_kg = beam1.weight_kg + beam2.weight_kg
    assert f"{expected_total_kg:.2f}" in report
    assert "Разом балок:              2" in report
    assert "Усі перевірені балки проходять" in report


def test_format_structure_report_lists_failing_beams():
    beam1, result1 = _beam_and_result(name="Добра", load_n=100.0)
    beam2, result2 = _beam_and_result(name="Погана", load_n=500_000.0)
    structure = Structure()
    structure.add(beam1)
    structure.add(beam2)
    report = format_structure_report(structure, {"Добра": result1, "Погана": result2})
    assert "Не проходять перевірку:   Погана" in report


def test_format_structure_report_handles_beam_without_result():
    beam1, result1 = _beam_and_result(name="Перевірена")
    beam2 = Beam(start=Point3(0, 0, 0), end=Point3(1000, 0, 0), profile=I_BEAM, material=STEEL, name="Без перевірки")
    structure = Structure()
    structure.add(beam1)
    structure.add(beam2)
    report = format_structure_report(structure, {"Перевірена": result1})
    assert "без перевірки навантаження" in report


def test_format_drive_report_hand_verified():
    motor = Motor(
        name="Мотор коліс", kind=MotorKind.BLDC, voltage_v=24.0, nominal_current_a=5.0, max_torque_nm=5.0,
        kv_rpm_per_v=200.0, efficiency=0.85,
    )
    gearbox = GearboxTransmission(gear_ratio=5, efficiency=0.9)
    report = format_drive_report(motor, gearbox, input_rpm=1500, load_torque_output_nm=2.0)

    expected_input_torque = 2.0 / (5 * 0.9)
    expected_current = current_under_load_a(motor, expected_input_torque)

    assert "Мотор коліс" in report
    assert f"{expected_input_torque:.3f}" in report
    assert f"{expected_current:.2f}" in report
    assert "Обороти на виході:           300" in report
    assert "GearboxTransmission" in report
