import pytest

from kovadlo.geometry import Point
from kovadlo.materials import Material
from kovadlo.room import Room
from kovadlo.wall import Wall

BRICK = Material(name="цегла", density_kg_m3=1800)


def test_room_from_contour_rectangle():
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    room = Room.from_contour(contour, height=2700, thickness=200, material=BRICK, name="Спальня")

    assert room.floor_area_m2 == pytest.approx(12.0)
    assert len(room.walls) == 4
    assert room.perimeter_mm == pytest.approx(14000.0)

    lengths = sorted(w.length_mm for w in room.walls)
    assert lengths == pytest.approx([3000.0, 3000.0, 4000.0, 4000.0])


def test_room_wall_areas_sum():
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    room = Room.from_contour(contour, height=2700, thickness=200, material=BRICK)

    expected_total = 2 * (4000 + 3000) * 2700 / 1_000_000
    assert room.total_wall_area_m2 == pytest.approx(expected_total)


def test_room_with_protrusion_l_shape():
    contour = [
        Point(0, 0),
        Point(4000, 0),
        Point(4000, 2000),
        Point(5500, 2000),
        Point(5500, 3000),
        Point(0, 3000),
    ]
    walls = [
        Wall.create(
            start=contour[i],
            end=contour[(i + 1) % len(contour)],
            height=2700,
            thickness=200,
            material=BRICK,
        )
        for i in range(len(contour))
    ]
    room = Room(contour=contour, walls=walls, name="Кімната з виступом")

    assert room.floor_area_m2 == pytest.approx(13.5)
    assert len(room.walls) == 6
    assert room.total_wall_area_m2 == pytest.approx(sum(w.area_m2 for w in walls))


def test_room_requires_at_least_three_points():
    with pytest.raises(ValueError):
        Room(contour=[Point(0, 0), Point(1000, 0)], walls=[])


def test_room_from_contour_snaps_sequential_edges():
    # точки навмисно "неточні" — очікуємо прив'язку кута кожного намальованого ребра
    contour = [Point(0, 0), Point(4000, 15), Point(4005, 3000), Point(-5, 3005)]
    room = Room.from_contour(contour, height=2700, thickness=200, material=BRICK, snap=True, snap_step=15)

    # усі ребра, крім замикаючого (останнє -> перше), мають кут кратний 15°
    for wall in room.walls[:-1]:
        assert wall.direction_deg % 15 == pytest.approx(0.0, abs=1e-6)
