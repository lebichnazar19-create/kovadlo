"""Тести експорту IFC (web/ifc_export.py).

IfcOpenShell ставиться лише поза Termux/Android-python (нема колеса під
android_* тег платформи) — у proot-distro/звичайному Linux-venv через
`pip install -e ".[ifc]"`. Якщо бібліотеки нема — весь файл скіпається,
щоб основний прогін тестів (Termux) лишався зеленим без неї.
"""

from __future__ import annotations

import pytest

ifcopenshell = pytest.importorskip("ifcopenshell")

from kovadlo.geometry import Point
from kovadlo.materials import Material
from kovadlo.opening import Opening, OpeningKind
from kovadlo.room import Room
from web.ifc_export import RoomExport, export_project


def _shoelace_area_m2(contour: list[Point]) -> float:
    """Площа контуру шнурівкою, незалежно від того, як її рахує сам
    export_project/IfcSlab — той самий підхід, що verify.mjs для OCCT."""
    total = 0.0
    n = len(contour)
    for i in range(n):
        p0, p1 = contour[i], contour[(i + 1) % n]
        total += p0.x * p1.z - p1.x * p0.z
    return abs(total) / 2 / 1_000_000  # мм² -> м²


def _world_bbox(product) -> tuple[list[float], list[float], list[float]]:
    import ifcopenshell.geom as geom

    settings = geom.settings()
    settings.set("use-world-coords", True)
    shape = geom.create_shape(settings, product)
    verts = shape.geometry.verts
    return verts[0::3], verts[1::3], verts[2::3]


@pytest.fixture
def simple_room() -> Room:
    return Room.from_contour(
        [Point(0, 0), Point(3500, 0), Point(3500, 4200), Point(0, 4200)],
        height=2700,
        thickness=200,
        material=Material(name="цегла"),
    )


def test_export_creates_one_wall_per_contour_side(simple_room, tmp_path):
    room_export = RoomExport(room=simple_room, floor_thickness_mm=150)
    out_path = tmp_path / "room.ifc"
    export_project([room_export], str(out_path), "Тестовий проєкт")

    ifc = ifcopenshell.open(str(out_path))
    walls = ifc.by_type("IfcWallStandardCase")
    assert len(walls) == len(simple_room.contour)


def test_export_hierarchy_project_site_building_storey(simple_room, tmp_path):
    room_export = RoomExport(room=simple_room, floor_thickness_mm=150)
    out_path = tmp_path / "room.ifc"
    export_project([room_export], str(out_path), "Тестовий проєкт")

    ifc = ifcopenshell.open(str(out_path))
    (project,) = ifc.by_type("IfcProject")
    (site,) = ifc.by_type("IfcSite")
    (building,) = ifc.by_type("IfcBuilding")
    (storey,) = ifc.by_type("IfcBuildingStorey")
    assert project.Name == "Тестовий проєкт"

    def parent_of(entity):
        (rel,) = [r for r in ifc.by_type("IfcRelAggregates") if entity in r.RelatedObjects]
        return rel.RelatingObject

    assert parent_of(site) == project
    assert parent_of(building) == site
    assert parent_of(storey) == building


def test_slab_area_matches_independent_shoelace_calculation(simple_room, tmp_path):
    floor_thickness_mm = 150.0
    room_export = RoomExport(room=simple_room, floor_thickness_mm=floor_thickness_mm)
    out_path = tmp_path / "room.ifc"
    export_project([room_export], str(out_path), "Тестовий проєкт")

    ifc = ifcopenshell.open(str(out_path))
    (slab,) = ifc.by_type("IfcSlab")
    assert slab.PredefinedType == "FLOOR"

    xs, ys, zs = _world_bbox(slab)
    volume_m3 = (max(xs) - min(xs)) * (max(ys) - min(ys)) * (max(zs) - min(zs))
    expected_area_m2 = _shoelace_area_m2(simple_room.contour)
    expected_volume_m3 = expected_area_m2 * (floor_thickness_mm / 1000)
    assert volume_m3 == pytest.approx(expected_volume_m3, rel=1e-6)


def test_wall_material_name_mapped(simple_room, tmp_path):
    room_export = RoomExport(room=simple_room, floor_thickness_mm=150)
    out_path = tmp_path / "room.ifc"
    export_project([room_export], str(out_path), "Тестовий проєкт")

    ifc = ifcopenshell.open(str(out_path))
    import ifcopenshell.util.element as element_util

    for wall in ifc.by_type("IfcWallStandardCase"):
        material = element_util.get_material(wall)
        assert material.is_a("IfcMaterial")
        assert material.Name == "Brick"  # "цегла" -> Brick, MATERIAL_NAME_MAP


def test_opening_exists_and_lies_within_its_wall(simple_room, tmp_path):
    door = Opening(kind=OpeningKind.DOOR, offset_mm=200, sill_height_mm=0, width_mm=900, height_mm=2100)
    room_export = RoomExport(room=simple_room, floor_thickness_mm=150, openings_by_wall={0: [door]})
    out_path = tmp_path / "room.ifc"
    export_project([room_export], str(out_path), "Тестовий проєкт")

    ifc = ifcopenshell.open(str(out_path))
    (opening,) = ifc.by_type("IfcOpeningElement")
    (void_rel,) = ifc.by_type("IfcRelVoidsElement")
    assert void_rel.RelatedOpeningElement == opening

    host_wall = void_rel.RelatingBuildingElement
    assert host_wall.is_a("IfcWallStandardCase")

    ox, oy, oz = _world_bbox(opening)
    wx, wy, wz = _world_bbox(host_wall)

    # Уздовж стіни й по висоті — проріз строго В МЕЖАХ стіни.
    assert min(ox) >= min(wx) - 1e-6 and max(ox) <= max(wx) + 1e-6
    assert min(oz) >= min(wz) - 1e-6 and max(oz) <= max(wz) + 1e-6
    # По товщині проріз навмисно ШИРШИЙ за стіну (на _OPENING_MARGIN_M з
    # кожного боку — гарантоване булеве проникнення, той самий прийом,
    # що офіційний приклад ifcopenshell.api.feature.add_feature), тому
    # тут не "в межах", а "стіна цілком всередині прорізу по товщині".
    assert min(oy) <= min(wy) and max(oy) >= max(wy)

    # Офсет і ширина прорізу відповідають заданим (з точністю до margin
    # на товщині, який на довжину стіни не впливає).
    assert (max(ox) - min(ox)) == pytest.approx(door.width_mm / 1000, rel=1e-6)
    assert (max(oz) - min(oz)) == pytest.approx(door.height_mm / 1000, rel=1e-6)


def test_export_project_with_roof(simple_room, tmp_path):
    from kovadlo.roof3d import build_gable_roof

    roof = build_gable_roof(simple_room.contour, base_height_mm=2700, slope_deg=25)
    room_export = RoomExport(room=simple_room, floor_thickness_mm=150, roof_faces=roof.faces)
    out_path = tmp_path / "room.ifc"
    export_project([room_export], str(out_path), "З дахом")

    ifc = ifcopenshell.open(str(out_path))
    assert len(ifc.by_type("IfcRoof")) == 1
