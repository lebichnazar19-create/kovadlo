import pytest

from kovadlo.geometry import Point
from kovadlo.materials import Material
from kovadlo.wall import Wall

BRICK = Material(name="цегла", density_kg_m3=1800)


def test_wall_create_basic():
    wall = Wall.create(start=Point(0, 0), end=Point(4000, 0), height=2700, thickness=250, material=BRICK)
    assert wall.length_mm == pytest.approx(4000.0)
    assert wall.thickness_mm == pytest.approx(250.0)
    assert wall.height == pytest.approx(2700.0)
    assert wall.material is BRICK


def test_wall_area():
    wall = Wall.create(start=Point(0, 0), end=Point(4000, 0), height=2700, thickness=250, material=BRICK)
    assert wall.area_mm2 == pytest.approx(4000 * 2700)
    assert wall.area_m2 == pytest.approx(10.8)


def test_wall_diagonal_length():
    wall = Wall.create(start=Point(0, 0), end=Point(3000, 4000), height=2500, thickness=200, material=BRICK)
    assert wall.length_mm == pytest.approx(5000.0)


def test_wall_zero_height_raises():
    with pytest.raises(ValueError):
        Wall.create(start=Point(0, 0), end=Point(1000, 0), height=0, thickness=200, material=BRICK)


def test_wall_zero_length_raises():
    with pytest.raises(ValueError):
        Wall.create(start=Point(0, 0), end=Point(0, 0), height=2700, thickness=200, material=BRICK)
