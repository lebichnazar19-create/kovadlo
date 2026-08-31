import pytest

from kovadlo.geometry import Point, polygon_area, polygon_perimeter, snap_angle, snap_point


def test_point_distance():
    p1 = Point(0, 0)
    p2 = Point(3000, 4000)
    assert p1.distance_to(p2) == pytest.approx(5000.0)


def test_point_angle_to():
    origin = Point(0, 0)
    assert origin.angle_to(Point(1000, 0)) == pytest.approx(0.0)
    assert origin.angle_to(Point(0, 1000)) == pytest.approx(90.0)
    assert origin.angle_to(Point(-1000, 0)) == pytest.approx(180.0)
    assert origin.angle_to(Point(0, -1000)) == pytest.approx(270.0)


@pytest.mark.parametrize(
    "angle, expected",
    [
        (0, 0),
        (7, 0),
        (8, 15),
        (14, 15),
        (22, 15),
        (23, 30),
        (44, 45),
        (350, 345),
        (352, 345),
        (-7, 0),
        (-10, 345),
    ],
)
def test_snap_angle(angle, expected):
    assert snap_angle(angle, step=15) == pytest.approx(expected)


def test_snap_angle_invalid_step():
    with pytest.raises(ValueError):
        snap_angle(10, step=0)


def test_snap_point_preserves_distance_and_snaps_angle():
    origin = Point(0, 0)
    target = Point(1000, 80)  # неточний клік, майже вздовж осі X
    snapped = snap_point(origin, target, step=15)
    assert origin.distance_to(snapped) == pytest.approx(origin.distance_to(target))
    assert origin.angle_to(snapped) % 15 == pytest.approx(0.0, abs=1e-6)


def test_snap_point_same_point_returns_origin():
    origin = Point(100, 200)
    assert snap_point(origin, Point(100, 200)) == origin


def test_polygon_area_rectangle():
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    assert polygon_area(contour) == pytest.approx(12_000_000.0)


def test_polygon_area_l_shape_with_protrusion():
    contour = [
        Point(0, 0),
        Point(4000, 0),
        Point(4000, 2000),
        Point(5500, 2000),
        Point(5500, 3000),
        Point(0, 3000),
    ]
    assert polygon_area(contour) == pytest.approx(13_500_000.0)


def test_polygon_area_too_few_points():
    assert polygon_area([Point(0, 0), Point(1, 1)]) == 0.0


def test_polygon_perimeter_rectangle():
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    assert polygon_perimeter(contour) == pytest.approx(14000.0)
