import pytest

from kovadlo.cable_route import CableRoute, build_route
from kovadlo.geometry import Point


def test_route_length_sums_polyline_segments():
    route = CableRoute(points=[Point(0, 0), Point(0, 3000), Point(2000, 3000)])
    assert route.length_mm == pytest.approx(5000.0)
    assert route.length_m == pytest.approx(5.0)


def test_route_requires_at_least_two_points():
    with pytest.raises(ValueError):
        CableRoute(points=[Point(0, 0)])


def test_build_route_requires_at_least_one_waypoint():
    with pytest.raises(ValueError):
        build_route(Point(0, 0), [])


def test_build_route_without_snap_uses_raw_points():
    route = build_route(Point(0, 0), [Point(1000, 37)], snap=False)
    assert route.points[-1] == Point(1000, 37)


def test_build_route_snaps_each_segment_to_90_degrees():
    # неточний клік трохи повз вертикаль і трохи повз горизонталь
    route = build_route(Point(0, 0), [Point(12, 3000), Point(2000, 3005)], snap=True, snap_step=90.0)
    assert len(route.points) == 3
    # перший сегмент прив'язаний до 90° (вертикально вгору) від (0,0)
    assert route.points[1].x == pytest.approx(route.points[0].x, abs=1e-6)
    # другий сегмент прив'язаний до 0°/180° (горизонтально) від попередньої точки
    assert route.points[2].z == pytest.approx(route.points[1].z, abs=1e-6)


def test_build_route_first_point_is_panel_position():
    panel = Point(500, 500)
    route = build_route(panel, [Point(500, 2000)])
    assert route.points[0] == panel
