"""
Приклад: кімната з виступом (L-подібна форма).

Показує:
  - побудову довільного полігонального контуру;
  - прив'язку (snap) кута до кратного 15° значення при неточному кліку;
  - стіни з різною товщиною і матеріалом на різних ділянках контуру;
  - автоматичний розрахунок площі підлоги та площі кожної стіни.

Запуск з кореня репозиторію:
    python -m examples.room_with_protrusion
"""

from __future__ import annotations

from kovadlo import Material, Point, Room, Wall, snap_point

BRICK = Material(name="цегла", density_kg_m3=1800)
GYPSUM = Material(name="гіпсокартон", density_kg_m3=800)

WALL_HEIGHT = 2700.0  # мм


def demo_snap() -> None:
    """Демонстрація прив'язки кута стіни до кроку 15°."""
    origin = Point(0, 0)
    rough_click = Point(4020, 1985)  # оператор клацнув неточно, майже вздовж осі X
    angle_before = origin.angle_to(rough_click)
    snapped_point = snap_point(origin, rough_click, step=15.0)
    angle_after = origin.angle_to(snapped_point)

    print("Прив'язка кута (snap):")
    print(f"  кут до прив'язки:   {angle_before:.2f}°")
    print(f"  кут після прив'язки: {angle_after:.2f}° (крок 15°)")
    print(f"  точка після прив'язки: ({snapped_point.x:.1f}, {snapped_point.z:.1f})")
    print()


def build_room_with_protrusion() -> Room:
    """
    L-подібна кімната: прямокутник 4000x3000 мм з виступом 1500x1000 мм
    у верхньому правому куті (вигляд згори, вісь X — направо, Z — вгору):

        (0,3000)                      (4000,3000)   (5500,3000)
            p5 ------------------------------ p4-------- p3'
             |                                          |
             |            основна кімната               | виступ
             |                                          |
            p0 ------------------------------ p1 ------ p2
        (0,0)                          (4000,0)   (4000,2000)...

    Основні стіни (p0-p1, p4-p5, p5-p0) — цегла 250 мм.
    Стіни виступу (p1-p2, p2-p3, p3-p4) — гіпсокартон 100 мм.
    """
    contour = [
        Point(0, 0),  # p0
        Point(4000, 0),  # p1
        Point(4000, 2000),  # p2
        Point(5500, 2000),  # p3
        Point(5500, 3000),  # p4
        Point(0, 3000),  # p5
    ]

    walls = [
        Wall.create(start=contour[0], end=contour[1], height=WALL_HEIGHT, thickness=250, material=BRICK),
        Wall.create(start=contour[1], end=contour[2], height=WALL_HEIGHT, thickness=100, material=GYPSUM),
        Wall.create(start=contour[2], end=contour[3], height=WALL_HEIGHT, thickness=100, material=GYPSUM),
        Wall.create(start=contour[3], end=contour[4], height=WALL_HEIGHT, thickness=100, material=GYPSUM),
        Wall.create(start=contour[4], end=contour[5], height=WALL_HEIGHT, thickness=250, material=BRICK),
        Wall.create(start=contour[5], end=contour[0], height=WALL_HEIGHT, thickness=250, material=BRICK),
    ]

    return Room(contour=contour, walls=walls, name="Кімната з виступом")


def main() -> None:
    demo_snap()

    room = build_room_with_protrusion()
    print(f"Кімната: «{room.name}»")
    print(f"Периметр:        {room.perimeter_mm / 1000:.2f} м")
    print(f"Площа підлоги:   {room.floor_area_m2:.2f} м²")
    print()
    print("Стіни:")
    for i, wall in enumerate(room.walls, start=1):
        print(
            f"  {i}. довжина={wall.length_mm / 1000:.2f} м, "
            f"товщина={wall.thickness_mm:.0f} мм, "
            f"матеріал={wall.material.name}, "
            f"площа={wall.area_m2:.2f} м²"
        )
    print()
    print(f"Сумарна площа стін: {room.total_wall_area_m2:.2f} м²")


if __name__ == "__main__":
    main()
