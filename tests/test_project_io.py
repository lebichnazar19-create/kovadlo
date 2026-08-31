"""Тести формату проєкту (модуль 14): export_project/import_project."""

import pytest

from kovadlo import (
    ConsumptionPoint,
    DetectorKind,
    Duct,
    DuctShape,
    FireDetector,
    FixtureKind,
    LightFixture,
    Material,
    PhaseType,
    Point,
    PointKind,
    Room,
)
from web.project_io import PROJECT_FORMAT, PROJECT_FORMAT_VERSION, export_project, import_project
from web.server import AppState, GroupMeta, Opening3DState


def _room() -> Room:
    return Room.from_contour(
        [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)],
        height=2700,
        thickness=200,
        material=Material(name="Бетон C25/30", density_kg_m3=2400),
        name="Кухня",
        snap=False,
    )


def test_export_empty_state():
    data = export_project(AppState())
    assert data["format"] == PROJECT_FORMAT
    assert data["version"] == PROJECT_FORMAT_VERSION
    assert data["room"] is None
    assert data["electrical"]["panel"] is None
    assert data["electrical"]["points"] == []
    assert data["lighting"]["fixtures"] == []
    assert data["ventilation"]["ducts"] == []
    assert data["fire"]["detectors"] == []
    assert data["roof"]["roof_type"] == "NONE"
    assert data["openings3d"] == []


def test_import_rejects_wrong_format():
    with pytest.raises(ValueError):
        import_project(AppState(), {"format": "not-kovadlo", "version": 1})


def test_import_rejects_newer_version():
    with pytest.raises(ValueError):
        import_project(AppState(), {"format": PROJECT_FORMAT, "version": PROJECT_FORMAT_VERSION + 1})


def test_roundtrip_room_only():
    state = AppState()
    state.room = _room()
    data = export_project(state)

    new_state = AppState()
    import_project(new_state, data)

    assert new_state.room is not None
    assert new_state.room.name == "Кухня"
    assert len(new_state.room.walls) == 4
    assert new_state.room.walls[0].material.name == "Бетон C25/30"
    assert new_state.room.walls[0].material.density_kg_m3 == 2400
    assert export_project(new_state) == data


def test_roundtrip_full_state_hand_verified():
    state = AppState()
    state.room = _room()
    state.panel = ConsumptionPoint(name="Щиток", kind=PointKind.PANEL, position=Point(0, 0))
    state.points["Розетка 1"] = ConsumptionPoint(name="Розетка 1", kind=PointKind.SOCKET, position=Point(1000, 1000), power_w=100.0)
    state.points["Розетка 3"] = ConsumptionPoint(name="Розетка 3", kind=PointKind.SOCKET, position=Point(2000, 1000), power_w=150.0)
    state.point_group["Розетка 1"] = "Кухня-розетки"
    state.routes["Розетка 1"] = [Point(0, 1000), Point(1000, 1000)]
    state.group_meta["Кухня-розетки"] = GroupMeta(phase=PhaseType.SINGLE, power_factor=0.95)

    state.lighting.fixtures["Світильник 2"] = LightFixture(
        name="Світильник 2", kind=FixtureKind.CEILING, position=Point(2000, 1500), luminous_flux_lm=800.0, power_w=8.0
    )
    state.ventilation.ducts["Повітропровід 1"] = Duct(
        points=[Point(0, 0), Point(1000, 0)], shape=DuctShape.ROUND, diameter_mm=100.0
    )
    state.heat.wall_layers[0] = [("Бетон C25/30", 0.2), ("Мінеральна вата (кам'яна)", 0.1)]
    state.fire.detectors["Датчик 1"] = FireDetector(name="Датчик 1", kind=DetectorKind.SMOKE, position=Point(2000, 1500))
    state.roof.roof_type = "GABLE"
    state.roof.slope_deg = 35.0
    state.openings3d["Вікно 1"] = Opening3DState(
        wall_index=0, kind="WINDOW", offset_mm=1500, sill_height_mm=900, width_mm=1200, height_mm=1400, name="Вікно 1"
    )

    data = export_project(state)
    new_state = AppState()
    import_project(new_state, data)

    # побудова заново — точне співпадіння результату export є найкращим
    # доказом round-trip (усі поля пройшли туди й назад без втрат).
    assert export_project(new_state) == data

    # і кілька прямих перевірок ручного значення для певності:
    assert new_state.points["Розетка 1"].power_w == 100.0
    assert new_state.point_group["Розетка 1"] == "Кухня-розетки"
    assert new_state.routes["Розетка 1"] == [Point(0, 1000), Point(1000, 1000)]
    assert new_state.group_meta["Кухня-розетки"].power_factor == 0.95
    assert new_state.heat.wall_layers[0] == [("Бетон C25/30", 0.2), ("Мінеральна вата (кам'яна)", 0.1)]
    assert new_state.roof.slope_deg == 35.0
    assert new_state.openings3d["Вікно 1"].width_mm == 1200


def test_import_restores_name_counters_hand_verified():
    """Після завантаження проєкту нові автоімена не повинні збігатися з
    уже наявними (лічильники відновлюються з максимального номера серед
    завантажених імен)."""
    state = AppState()
    state.room = _room()
    state.points["Розетка 1"] = ConsumptionPoint(name="Розетка 1", kind=PointKind.SOCKET, position=Point(0, 0))
    state.points["Розетка 5"] = ConsumptionPoint(name="Розетка 5", kind=PointKind.SOCKET, position=Point(0, 0))
    state.lighting.fixtures["Світильник 3"] = LightFixture(
        name="Світильник 3", kind=FixtureKind.CEILING, position=Point(0, 0), luminous_flux_lm=800.0, power_w=8.0
    )

    new_state = AppState()
    import_project(new_state, export_project(state))

    assert new_state.next_point_name(PointKind.SOCKET) == "Розетка 6"
    assert new_state.lighting.next_name() == "Світильник 4"


def test_import_opening_rejects_out_of_bounds_after_room_shrunk():
    """Отвір, що виходить за межі стіни в новій кімнаті проєкту, — файл
    пошкоджено/несумісний, і це має провалитись, а не тихо завантажитись."""
    state = AppState()
    state.room = _room()
    state.openings3d["Вікно 1"] = Opening3DState(
        wall_index=0, kind="WINDOW", offset_mm=1500, sill_height_mm=900, width_mm=1200, height_mm=1400, name="Вікно 1"
    )
    data = export_project(state)
    # підміняємо кімнату на значно меншу (як від пошкодженого/зміненого вручну файлу)
    data["room"]["contour"] = [[0, 0], [500, 0], [500, 500], [0, 500]]

    with pytest.raises(ValueError):
        import_project(AppState(), data)


def test_import_opening_rejects_bad_wall_index():
    state = AppState()
    state.room = _room()
    data = export_project(state)
    data["openings3d"] = [
        {
            "name": "Вікно 1", "wall_index": 99, "kind": "WINDOW", "offset_mm": 0, "sill_height_mm": 900,
            "width_mm": 1000, "height_mm": 1000,
        }
    ]
    with pytest.raises(ValueError):
        import_project(AppState(), data)


def test_roundtrip_no_room_keeps_openings_unvalidated_but_present():
    # Без кімнати неможливо перевірити межі отвору геометрично — імпорт
    # просто довіряє даним (сумісно з форматом, де кімнату видалили, а
    # отвори лишились у файлі старої версії проєкту).
    data = {
        "format": PROJECT_FORMAT, "version": PROJECT_FORMAT_VERSION, "room": None,
        "electrical": {}, "lighting": {}, "ventilation": {}, "heat": {}, "fire": {},
        "roof": {}, "openings3d": [
            {"name": "Вікно 1", "wall_index": 0, "kind": "WINDOW", "offset_mm": 0, "sill_height_mm": 900, "width_mm": 1000, "height_mm": 1000}
        ],
    }
    state = AppState()
    import_project(state, data)
    assert state.room is None
    assert "Вікно 1" in state.openings3d
