import pytest

from kovadlo.building3d import Building, Storey, contours_match
from kovadlo.geometry import Point

RECT = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
RECT_ROTATED_START = [Point(4000, 0), Point(4000, 3000), Point(0, 3000), Point(0, 0)]
RECT_REVERSED = list(reversed(RECT))
DIFFERENT_RECT = [Point(0, 0), Point(5000, 0), Point(5000, 3000), Point(0, 3000)]


def test_contours_match_identical():
    assert contours_match(RECT, list(RECT)) is True


def test_contours_match_rotated_start():
    assert contours_match(RECT, RECT_ROTATED_START) is True


def test_contours_match_reversed_winding():
    assert contours_match(RECT, RECT_REVERSED) is True


def test_contours_match_false_for_different_shape():
    assert contours_match(RECT, DIFFERENT_RECT) is False


def test_contours_match_false_for_different_vertex_count():
    triangle = [Point(0, 0), Point(1000, 0), Point(500, 1000)]
    assert contours_match(RECT, triangle) is False


def test_storey_rejects_short_contour_or_bad_height():
    with pytest.raises(ValueError):
        Storey("1", [Point(0, 0), Point(1, 0)], 2700)
    with pytest.raises(ValueError):
        Storey("1", RECT, 0)


def test_building_requires_at_least_one_storey():
    with pytest.raises(ValueError):
        Building(storeys=[])


def test_building_total_height_and_base_elevation():
    b = Building(
        storeys=[
            Storey("1 поверх", RECT, 2700),
            Storey("2 поверх", RECT, 2500),
            Storey("Мансарда", RECT, 2200),
        ]
    )
    assert b.total_height_mm == pytest.approx(2700 + 2500 + 2200)
    assert b.base_elevation_mm(0) == pytest.approx(0)
    assert b.base_elevation_mm(1) == pytest.approx(2700)
    assert b.base_elevation_mm(2) == pytest.approx(2700 + 2500)


def test_building_base_elevation_out_of_range():
    b = Building(storeys=[Storey("1", RECT, 2700)])
    with pytest.raises(IndexError):
        b.base_elevation_mm(5)


def test_building_contours_all_match_when_identical():
    b = Building(storeys=[Storey("1", RECT, 2700), Storey("2", list(RECT), 2700)])
    assert b.contours_all_match() is True
    assert b.contour_mismatches() == []


def test_building_detects_mismatched_contour_between_floors():
    b = Building(storeys=[Storey("1", RECT, 2700), Storey("2", DIFFERENT_RECT, 2700), Storey("3", DIFFERENT_RECT, 2700)])
    assert b.contours_all_match() is False
    assert b.contour_mismatches() == [(0, 1)]  # лише перехід 1->2 не збігається, 2->3 — так
