import math

import pytest

from kovadlo.geometry import Point
from kovadlo.geometry3d import Face, Point3


def test_point3_from_plan_and_to_plan_roundtrip():
    p = Point(1000, 2000)
    p3 = Point3.from_plan(p, height=2700)
    assert p3 == Point3(1000, 2700, 2000)
    assert p3.to_plan() == p


def test_point3_distance():
    a = Point3(0, 0, 0)
    b = Point3(3, 4, 0)
    assert a.distance_to(b) == pytest.approx(5.0)


def test_face_requires_at_least_three_points():
    with pytest.raises(ValueError):
        Face(points=[Point3(0, 0, 0), Point3(1, 0, 0)])


def test_face_area_vertical_rectangle():
    face = Face(points=[Point3(0, 0, 0), Point3(1000, 0, 0), Point3(1000, 2700, 0), Point3(0, 2700, 0)])
    assert face.area_mm2 == pytest.approx(1000 * 2700)
    assert face.area_m2 == pytest.approx(2.7)


def test_face_area_horizontal_rectangle():
    face = Face(points=[Point3(0, 1000, 0), Point3(4000, 1000, 0), Point3(4000, 1000, 3000), Point3(0, 1000, 3000)])
    assert face.area_m2 == pytest.approx(12.0)


def test_face_area_tilted_matches_footprint_over_cosine():
    """Інваріант: площа нахиленої (плоскої) грані = площа її горизонтальної
    проєкції / cos(кут нахилу) — незалежно від напрямку нахилу."""
    theta = math.radians(30)
    rise = 3000 * math.tan(theta)
    face = Face(points=[Point3(0, 0, 0), Point3(4000, 0, 0), Point3(4000, rise, 3000), Point3(0, rise, 3000)])
    expected = (4000 * 3000 / 1_000_000) / math.cos(theta)
    assert face.area_m2 == pytest.approx(expected)


def test_face_area_independent_of_winding_direction():
    pts = [Point3(0, 0, 0), Point3(1000, 0, 0), Point3(1000, 2000, 0), Point3(0, 2000, 0)]
    face_forward = Face(points=pts)
    face_reversed = Face(points=list(reversed(pts)))
    assert face_forward.area_m2 == pytest.approx(face_reversed.area_m2)
