"""Тести специфікації деталей (BOM) конструкції з балок (модуль 12)."""

import pytest

from kovadlo.beam import Beam
from kovadlo.bom import BomLine, build_bill_of_materials
from kovadlo.geometry3d import Point3
from kovadlo.materials import Material
from kovadlo.steel_profiles import AngleProfile, RoundTubeProfile

STEEL = Material(name="Сталь конструкційна S235JR", density_kg_m3=7850)
ALUMINUM = Material(name="Алюміній (сплав 6060, Т6)", density_kg_m3=2700)

ANGLE_50 = AngleProfile(leg_a=50, leg_b=50, thickness=5)
TUBE_30 = RoundTubeProfile(outer_diameter=30, wall_thickness=3)


def _beam(profile, material, length_mm, *, angle=0.0, start_x=0.0):
    return Beam(
        start=Point3(start_x, 0, 0),
        end=Point3(start_x, 0, length_mm),
        profile=profile,
        material=material,
        angle=angle,
    )


def test_identical_beams_merge_into_one_line_with_count():
    beams = [_beam(ANGLE_50, STEEL, 1200), _beam(ANGLE_50, STEEL, 1200), _beam(ANGLE_50, STEEL, 1200)]
    lines = build_bill_of_materials(beams)
    assert len(lines) == 1
    assert lines[0].count == 3
    assert lines[0].position == 1


def test_angle_does_not_affect_grouping():
    # Той самий профіль/матеріал/довжина, повернутий на різний кут —
    # ріжеться однаково, тому це одна позиція, а не дві.
    beams = [_beam(TUBE_30, STEEL, 1000, angle=0.0), _beam(TUBE_30, STEEL, 1000, angle=180.0)]
    lines = build_bill_of_materials(beams)
    assert len(lines) == 1
    assert lines[0].count == 2


def test_different_material_gives_separate_lines():
    beams = [_beam(ANGLE_50, STEEL, 1200), _beam(ANGLE_50, ALUMINUM, 1200)]
    lines = build_bill_of_materials(beams)
    assert len(lines) == 2
    assert {line.count for line in lines} == {1, 1}
    assert {line.material_name for line in lines} == {STEEL.name, ALUMINUM.name}
    assert {line.name for line in lines} == {"Кутник"}  # той самий профіль — та сама назва


def test_different_profile_type_gives_separate_lines():
    beams = [_beam(ANGLE_50, STEEL, 1000), _beam(TUBE_30, STEEL, 1000)]
    lines = build_bill_of_materials(beams)
    assert len(lines) == 2


def test_different_profile_dimensions_gives_separate_lines():
    other_angle = AngleProfile(leg_a=60, leg_b=60, thickness=5)
    beams = [_beam(ANGLE_50, STEEL, 1000), _beam(other_angle, STEEL, 1000)]
    lines = build_bill_of_materials(beams)
    assert len(lines) == 2


def test_length_within_tolerance_merges():
    beams = [_beam(ANGLE_50, STEEL, 1200.0), _beam(ANGLE_50, STEEL, 1200.4)]
    lines = build_bill_of_materials(beams, length_tolerance_mm=1.0)
    assert len(lines) == 1
    assert lines[0].count == 2


def test_length_beyond_tolerance_separates():
    beams = [_beam(ANGLE_50, STEEL, 1200.0), _beam(ANGLE_50, STEEL, 1202.0)]
    lines = build_bill_of_materials(beams, length_tolerance_mm=1.0)
    assert len(lines) == 2
    assert {line.count for line in lines} == {1, 1}


def test_position_numbers_follow_first_occurrence_order():
    beams = [_beam(TUBE_30, STEEL, 500), _beam(ANGLE_50, STEEL, 1000), _beam(TUBE_30, STEEL, 500)]
    lines = build_bill_of_materials(beams)
    assert [line.position for line in lines] == [1, 2]
    assert lines[0].count == 2  # труба — перша за появою, тому позиція 1
    assert lines[1].count == 1  # кутник — друга


def test_numbering_is_stable_across_repeated_calls():
    beams = [_beam(TUBE_30, STEEL, 500), _beam(ANGLE_50, STEEL, 1000), _beam(TUBE_30, ALUMINUM, 700)]
    first = build_bill_of_materials(beams)
    second = build_bill_of_materials(beams)
    assert first == second


def test_empty_input_returns_empty_list():
    assert build_bill_of_materials([]) == []


def test_rejects_non_positive_tolerance():
    with pytest.raises(ValueError):
        build_bill_of_materials([_beam(ANGLE_50, STEEL, 1000)], length_tolerance_mm=0)


def test_line_name_and_size_are_human_readable():
    lines = build_bill_of_materials([_beam(ANGLE_50, STEEL, 1200)])
    line = lines[0]
    assert isinstance(line, BomLine)
    assert line.name == "Кутник"
    assert line.material_name == STEEL.name
    assert STEEL.name not in line.name  # матеріал — окреме поле, не частина назви
    assert "50" in line.size
    assert "1200" in line.size
