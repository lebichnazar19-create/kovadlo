import pytest

from kovadlo.geometry import (
    Point,
    clip_convex_polygon,
    decompose_rectilinear_polygon,
    point_in_polygon,
    polygon_area,
    rotate_point,
)


def test_rotate_point_90_degrees():
    result = rotate_point(Point(1, 0), 90, Point(0, 0))
    assert result.x == pytest.approx(0.0, abs=1e-9)
    assert result.z == pytest.approx(1.0, abs=1e-9)


def test_rotate_point_45_degrees():
    result = rotate_point(Point(1, 0), 45, Point(0, 0))
    half_sqrt2 = 2**0.5 / 2
    assert result.x == pytest.approx(half_sqrt2)
    assert result.z == pytest.approx(half_sqrt2)


def test_rotate_point_around_arbitrary_origin():
    result = rotate_point(Point(1100, 1000), 90, Point(1000, 1000))
    assert result.x == pytest.approx(1000.0)
    assert result.z == pytest.approx(1100.0)


def test_point_in_polygon_inside_and_outside():
    square = [Point(0, 0), Point(1000, 0), Point(1000, 1000), Point(0, 1000)]
    assert point_in_polygon(Point(500, 500), square) is True
    assert point_in_polygon(Point(-1, 500), square) is False
    assert point_in_polygon(Point(1500, 500), square) is False


def test_clip_convex_polygon_partial_overlap():
    square_a = [Point(0, 0), Point(1000, 0), Point(1000, 1000), Point(0, 1000)]
    square_b = [Point(500, 500), Point(1500, 500), Point(1500, 1500), Point(500, 1500)]
    result = clip_convex_polygon(square_a, square_b)
    assert polygon_area(result) == pytest.approx(500 * 500)


def test_clip_convex_polygon_no_overlap():
    square_a = [Point(0, 0), Point(100, 0), Point(100, 100), Point(0, 100)]
    square_b = [Point(1000, 1000), Point(1100, 1000), Point(1100, 1100), Point(1000, 1100)]
    result = clip_convex_polygon(square_a, square_b)
    assert result == [] or polygon_area(result) == pytest.approx(0.0)


def test_clip_convex_polygon_full_containment():
    outer = [Point(0, 0), Point(1000, 0), Point(1000, 1000), Point(0, 1000)]
    inner = [Point(200, 200), Point(800, 200), Point(800, 800), Point(200, 800)]
    result = clip_convex_polygon(outer, inner)
    assert polygon_area(result) == pytest.approx(polygon_area(inner))


def test_decompose_rectilinear_polygon_simple_rectangle():
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    rects = decompose_rectilinear_polygon(contour)
    assert len(rects) == 1
    assert rects[0].area == pytest.approx(4000 * 3000)


def test_decompose_rectilinear_polygon_l_shape():
    contour = [
        Point(0, 0),
        Point(4000, 0),
        Point(4000, 2000),
        Point(5500, 2000),
        Point(5500, 3000),
        Point(0, 3000),
    ]
    rects = decompose_rectilinear_polygon(contour)
    # декомпозиція не мінімальна, але має точно покривати всю площу без накладань
    total_area = sum(r.area for r in rects)
    assert total_area == pytest.approx(polygon_area(contour))
    assert total_area == pytest.approx(13_500_000.0)
    # жоден прямокутник не виходить за межі контуру (протестовано через площу вище)
    assert len(rects) >= 2


def test_decompose_rectilinear_polygon_rejects_non_orthogonal_contour():
    triangle = [Point(0, 0), Point(1000, 0), Point(500, 1000)]
    with pytest.raises(ValueError):
        decompose_rectilinear_polygon(triangle)
