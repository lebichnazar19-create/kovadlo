import pytest

from kovadlo.geometry import Point
from kovadlo.materials import Material
from kovadlo.room import Room
from kovadlo.surface import Surface
from kovadlo.wall import Wall

BRICK = Material(name="цегла", density_kg_m3=1800)


def test_surface_from_room_floor():
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    room = Room.from_contour(contour, height=2700, thickness=200, material=BRICK, name="Кухня")
    surface = Surface.from_room_floor(room)

    assert surface.contour == room.contour
    assert surface.area_m2 == pytest.approx(12.0)
    assert "Кухня" in surface.name


def test_surface_from_wall():
    wall = Wall.create(start=Point(0, 0), end=Point(4000, 0), height=2700, thickness=200, material=BRICK)
    surface = Surface.from_wall(wall)

    assert surface.area_m2 == pytest.approx(4.0 * 2.7)
    rects = surface.rectangles()
    assert len(rects) == 1
    assert rects[0].width == pytest.approx(4000.0)
    assert rects[0].height == pytest.approx(2700.0)
