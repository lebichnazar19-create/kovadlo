import pytest

from kovadlo.geometry import Point
from kovadlo.pcb_component import Component, ComponentKind, Unit
from kovadlo.pcb_footprints import two_pin_footprint
from kovadlo.pcb_board import Board, Placement, Track, Via, build_track
from kovadlo.pcb_norms import Layer


def _resistor(spacing: float = 5.0) -> Component:
    return Component("R1", "Резистор", ComponentKind.RESISTOR, two_pin_footprint("THT-2", spacing=spacing), 220, Unit.OHM)


def test_placement_pin_position_no_rotation():
    r = _resistor(spacing=5.0)
    placement = Placement(component=r, position=Point(10, 10))
    assert placement.pin_position(1) == Point(10, 10)
    assert placement.pin_position(2) == Point(15, 10)


def test_placement_pin_position_rotated_90_degrees():
    # локальний вивід 2 на (5,0); поворот на 90° CCW навколо початку дає (0,5)
    r = _resistor(spacing=5.0)
    placement = Placement(component=r, position=Point(10, 10), rotation_deg=90)
    p2 = placement.pin_position(2)
    assert p2.x == pytest.approx(10.0)
    assert p2.z == pytest.approx(15.0)


def test_placement_pin_position_rotated_180_degrees():
    r = _resistor(spacing=5.0)
    placement = Placement(component=r, position=Point(0, 0), rotation_deg=180)
    p2 = placement.pin_position(2)
    assert p2.x == pytest.approx(-5.0, abs=1e-9)
    assert p2.z == pytest.approx(0.0, abs=1e-9)


def test_track_requires_at_least_two_points():
    with pytest.raises(ValueError):
        Track(points=[Point(0, 0)], width_mm=0.3, layer=Layer.TOP, net="SIG")


def test_track_requires_positive_width():
    with pytest.raises(ValueError):
        Track(points=[Point(0, 0), Point(1, 0)], width_mm=0, layer=Layer.TOP, net="SIG")


def test_track_length_sums_segments():
    t = Track(points=[Point(0, 0), Point(3, 0), Point(3, 4)], width_mm=0.3, layer=Layer.TOP, net="SIG")
    assert t.length_mm == pytest.approx(7.0)  # 3 + 4
    assert t.length_m == pytest.approx(0.007)


def test_build_track_snaps_to_45_degrees():
    # ціль трохи повз рівно 45° від початку (0,0)
    t = build_track(Point(0, 0), [Point(10.5, 9.4)], width_mm=0.3, layer=Layer.TOP, net="SIG", snap_step=45.0)
    assert len(t.points) == 2
    # після прив'язки до 45° x і z мають бути рівні (напрямок точно (1,1))
    assert t.points[1].x == pytest.approx(t.points[1].z, abs=1e-6)


def test_build_track_without_snap_uses_raw_points():
    t = build_track(Point(0, 0), [Point(7, 3)], width_mm=0.3, layer=Layer.TOP, net="SIG", snap=False)
    assert t.points[1] == Point(7, 3)


def test_via_requires_pad_larger_than_drill():
    with pytest.raises(ValueError):
        Via(position=Point(0, 0), net="SIG", drill_diameter_mm=0.5, pad_diameter_mm=0.5)


def test_board_area_and_perimeter_from_core_geometry():
    board = Board(contour=[Point(0, 0), Point(40, 0), Point(40, 30), Point(0, 30)])
    assert board.area_mm2 == pytest.approx(1200.0)
    assert board.area_m2 == pytest.approx(1200.0 / 1_000_000)
    assert board.perimeter_mm == pytest.approx(140.0)


def test_board_requires_at_least_three_contour_points():
    with pytest.raises(ValueError):
        Board(contour=[Point(0, 0), Point(1, 0)])


def test_board_pin_position_uses_placement():
    r = _resistor(spacing=5.0)
    board = Board(contour=[Point(0, 0), Point(50, 0), Point(50, 40), Point(0, 40)])
    board.placements["R1"] = Placement(component=r, position=Point(10, 10))
    assert board.pin_position("R1", 2) == Point(15, 10)


def test_board_pin_position_missing_placement_raises():
    board = Board(contour=[Point(0, 0), Point(50, 0), Point(50, 40), Point(0, 40)])
    with pytest.raises(KeyError):
        board.pin_position("R1", 1)


def test_board_tracks_on_net_and_total_length():
    board = Board(contour=[Point(0, 0), Point(50, 0), Point(50, 40), Point(0, 40)])
    board.tracks.append(Track(points=[Point(0, 0), Point(10, 0)], width_mm=0.3, layer=Layer.TOP, net="A"))
    board.tracks.append(Track(points=[Point(0, 0), Point(0, 20)], width_mm=0.3, layer=Layer.TOP, net="B"))
    assert len(board.tracks_on_net("A")) == 1
    assert board.total_track_length_m == pytest.approx(0.030)


def test_board_vias_on_net():
    board = Board(contour=[Point(0, 0), Point(50, 0), Point(50, 40), Point(0, 40)])
    board.vias.append(Via(position=Point(5, 5), net="A", drill_diameter_mm=0.3, pad_diameter_mm=0.6))
    board.vias.append(Via(position=Point(5, 5), net="B", drill_diameter_mm=0.3, pad_diameter_mm=0.6))
    assert len(board.vias_on_net("A")) == 1
