import pytest

from kovadlo.extrude import extrude_contour_walls, extrude_flat_faces
from kovadlo.geometry import Point


def test_extrude_rejects_short_contour():
    with pytest.raises(ValueError):
        extrude_contour_walls([Point(0, 0), Point(1, 0)], height=2700)


def test_extrude_rejects_non_positive_height():
    contour = [Point(0, 0), Point(1000, 0), Point(1000, 1000), Point(0, 1000)]
    with pytest.raises(ValueError):
        extrude_contour_walls(contour, height=0)


def test_extrude_rectangle_wall_area_hand_verified():
    """Прямокутник 4×3 м, висота 2.7 м: сумарна площа стін = 2*(4+3)*2.7 = 37.8 м²."""
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    faces = extrude_contour_walls(contour, height=2700)
    assert len(faces) == 4
    assert sum(f.area_m2 for f in faces) == pytest.approx(37.8)


def test_extrude_face_heights():
    contour = [Point(0, 0), Point(1000, 0), Point(1000, 1000), Point(0, 1000)]
    faces = extrude_contour_walls(contour, height=2700, base_height=300)
    face = faces[0]
    ys = sorted({p.y for p in face.points})
    assert ys == [300, 3000]


def test_extrude_flat_faces_match_floor_area():
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    bottom, top = extrude_flat_faces(contour, height=2700)
    assert bottom.area_m2 == pytest.approx(12.0)
    assert top.area_m2 == pytest.approx(12.0)
    assert bottom.points[0].y == 0
    assert top.points[0].y == 2700
