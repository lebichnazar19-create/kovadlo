"""
Приклад: тривимірна модель кімнати (модуль 10) — кухня 4×3 м, стіни з
реальних шарів конструкції (модуль 8.4/7), вікно, підлога, двосхилий
дах; розрахунок об'єму, площі огороджень і матеріалів; експорт сітки
в OBJ для майбутнього рендеру.

Лише розрахунок і текстовий вивід (+ файл .obj) — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.building_3d_demo
"""

from __future__ import annotations

from kovadlo import (
    Material,
    Opening,
    OpeningKind,
    Point,
    Room,
    Slab,
    Wall3D,
    WallLayer,
    build_default_database,
    build_gable_roof,
    build_room_mesh,
    exterior_envelope_area_m2,
    room_volume_m3,
    wall_material_costs_pln,
    wall_material_volumes_m3,
)

WALL_THICKNESS_MM = 380.0  # 200 мм бетону + 180 мм вати


def build_room() -> Room:
    return Room.from_contour(
        [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)],
        height=2700,
        thickness=WALL_THICKNESS_MM,
        material=Material(name="стіна", density_kg_m3=2000),
        name="Кухня",
    )


def build_walls3d(room: Room, db) -> list[Wall3D]:
    concrete = db.find_by_name("Бетон C25/30")
    wool = db.find_by_name("Мінеральна вата (кам'яна)")
    layers = [WallLayer(concrete, thickness_m=0.20), WallLayer(wool, thickness_m=0.18)]

    window = Opening(OpeningKind.WINDOW, offset_mm=1500, sill_height_mm=900, width_mm=1200, height_mm=1400, name="Вікно 1")

    walls3d = []
    for i, wall in enumerate(room.walls):
        openings = [window] if i == 0 else []
        walls3d.append(Wall3D(wall=wall, layers=list(layers), openings=openings))
    return walls3d


def main() -> None:
    db = build_default_database()
    room = build_room()
    walls3d = build_walls3d(room, db)

    print(f"Кімната «{room.name}»: {room.floor_area_m2:.1f} м², об'єм {room_volume_m3(room):.1f} м³ (для модуля 8.2)")
    print()

    envelope = exterior_envelope_area_m2(walls3d)
    gross_total = sum(w.wall.area_m2 for w in walls3d)
    print("Площа огороджень (для тепловтрат, модуль 8.3):")
    print(f"  валова (без отворів): {gross_total:.2f} м²")
    print(f"  чиста (з вирахуванням вікна): {envelope:.2f} м²")
    print()

    print("Об'єм і орієнтовна вартість матеріалів стін:")
    volumes = wall_material_volumes_m3(walls3d)
    costs = wall_material_costs_pln(walls3d)
    for name, volume in volumes.items():
        cost = costs.get(name)
        cost_str = f", ≈{cost:.0f} зл" if cost is not None else ""
        print(f"  {name}: {volume:.3f} м³{cost_str}")
    print()

    floor = Slab(contour=room.contour, base_height_mm=0, thickness_mm=200)
    roof = build_gable_roof(room.contour, base_height_mm=int(room.walls[0].height), slope_deg=30.0, ridge_along="x")
    print(f"Дах: {roof.roof_type.value}, площа схилів {roof.area_m2:.2f} м², гребінь +{roof.ridge_rise_mm / 1000:.2f} м")
    print()

    mesh = build_room_mesh(walls3d, slabs=[floor], roof=roof)
    obj_path = "kovadlo_room.obj"
    with open(obj_path, "w", encoding="utf-8") as f:
        f.write(mesh.to_obj())
    print(f"Сітка: {mesh.vertex_count} вершин, {mesh.triangle_count} трикутників")
    print(f"Експортовано в {obj_path} (для рендеру пізніше)")


if __name__ == "__main__":
    main()
