import pytest

from kovadlo.geometry import Point
from kovadlo.slab3d import Slab


def test_slab_requires_short_contour_rejected():
    with pytest.raises(ValueError):
        Slab(contour=[Point(0, 0), Point(1, 0)], base_height_mm=0, thickness_mm=200)


def test_slab_requires_positive_thickness():
    contour = [Point(0, 0), Point(1000, 0), Point(1000, 1000), Point(0, 1000)]
    with pytest.raises(ValueError):
        Slab(contour=contour, base_height_mm=0, thickness_mm=0)


def test_slab_area_and_volume_hand_verified():
    """Плита 4×3 м, товщина 200 мм: площа 12 м², об'єм 12×0.2=2.4 м³."""
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    slab = Slab(contour=contour, base_height_mm=0, thickness_mm=200)
    assert slab.area_m2 == pytest.approx(12.0)
    assert slab.volume_m3 == pytest.approx(2.4)


def test_slab_faces_at_correct_heights():
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    slab = Slab(contour=contour, base_height_mm=2700, thickness_mm=300)
    bottom = slab.bottom_face()
    top = slab.top_face()
    assert all(p.y == 2700 for p in bottom.points)
    assert all(p.y == 3000 for p in top.points)
    assert bottom.area_m2 == pytest.approx(top.area_m2)
