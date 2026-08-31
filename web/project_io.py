"""
Формат проєкту (модуль 14): повний стан застосунку (кімната, плитка*,
проводка, інженерні системи, 3D) в один JSON-документ — для збереження
у файл на телефоні й повторного відкриття.

Це НОВИЙ, окремий від наявних "_state"-обробників серіалізатор: наявні
`_handle_*_state` методи (модуль 9) віддають дані, зручні для МАЛЮВАННЯ
(вже порахований `routes_json` з підставленим щитком тощо) — для
збереження проєкту потрібні СИРІ вхідні параметри, з яких можна
відновити той самий стан один в один, тому вони серіалізуються тут
окремо, без зміни жодного наявного обробника.

*Плитка (модуль 2) на сервері не зберігається як стан (кожен розрахунок
`/api/tiling` — самостійний, без збереження параметрів) — її налаштування
живуть лише в HTML-полях на клієнті; клієнтська частина зберігання
проєкту (`index.html`) додає їх до цього ж JSON окремим полем
`client.tiling_settings`, який ця функція не чіпає.
"""

from __future__ import annotations

import re
from typing import TYPE_CHECKING, Any

from kovadlo import (
    ClimateZone,
    ConsumptionPoint,
    DetectorKind,
    Duct,
    DuctShape,
    FireDetector,
    FixtureKind,
    LightFixture,
    Material,
    Opening,
    OpeningKind,
    PhaseType,
    Point,
    PointKind,
    Room,
    RoomPurpose,
    VentilatedRoomKind,
    Wall3D,
)

if TYPE_CHECKING:
    from .server import AppState, GroupMeta, Opening3DState

PROJECT_FORMAT = "kovadlo-project"
PROJECT_FORMAT_VERSION = 1


def _max_trailing_number(names: list[str], prefix: str) -> int:
    """Найбільше число в кінці імен виду "<prefix> <N>" — щоб після
    завантаження проєкту нові автоімена не збігалися зі старими."""
    best = 0
    pattern = re.compile(rf"^{re.escape(prefix)} (\d+)$")
    for name in names:
        match = pattern.match(name)
        if match:
            best = max(best, int(match.group(1)))
    return best


def export_project(state: "AppState") -> dict[str, Any]:
    """Повний стан сервера -> JSON-сумісний словник."""
    room = state.room
    room_json = None
    if room is not None:
        wall = room.walls[0] if room.walls else None
        room_json = {
            "contour": [[p.x, p.z] for p in room.contour],
            "wall_height": wall.height if wall else 2700.0,
            "wall_thickness": wall.thickness_mm if wall else 200.0,
            "material_name": wall.material.name if wall else "цегла",
            "material_density": wall.material.density_kg_m3 if wall else None,
            "room_name": room.name,
        }

    electrical_json = {
        "panel": (
            {"name": state.panel.name, "position": [state.panel.position.x, state.panel.position.z]}
            if state.panel is not None
            else None
        ),
        "points": [
            {
                "name": point.name,
                "kind": point.kind.name,
                "position": [point.position.x, point.position.z],
                "power_w": point.power_w,
            }
            for point in state.points.values()
        ],
        "point_group": dict(state.point_group),
        # СИРІ точки траси (після щитка, до build_route) — саме так їх
        # тримає AppState.routes; повний маршрут (з підставленим щитком)
        # відновлюється build_route при потребі, не зберігається тут.
        "routes": {name: [[p.x, p.z] for p in points] for name, points in state.routes.items()},
        "group_meta": {
            group_name: {
                "phase": meta.phase.name,
                "power_factor": meta.power_factor,
                "connection_allowance_m": meta.connection_allowance_m,
                "min_cross_section_mm2": meta.min_cross_section_mm2,
                "max_voltage_drop_percent": meta.max_voltage_drop_percent,
            }
            for group_name, meta in state.group_meta.items()
        },
    }

    lighting_json = {
        "room_purpose": state.lighting.room_purpose.name,
        "utilization_factor": state.lighting.utilization_factor,
        "maintenance_factor": state.lighting.maintenance_factor,
        "fixtures": [
            {
                "name": fixture.name,
                "kind": fixture.kind.name,
                "position": [fixture.position.x, fixture.position.z],
                "luminous_flux_lm": fixture.luminous_flux_lm,
                "power_w": fixture.power_w,
                "beam_angle_deg": fixture.beam_angle_deg,
                "color_temp_k": fixture.color_temp_k,
            }
            for fixture in state.lighting.fixtures.values()
        ],
    }

    ventilation_json = {
        "room_kind": state.ventilation.room_kind.name,
        "ducts": [
            {
                "name": name,
                "points": [[p.x, p.z] for p in duct.points],
                "shape": duct.shape.name,
                "diameter_mm": duct.diameter_mm,
                "width_mm": duct.width_mm,
                "height_mm": duct.height_mm,
            }
            for name, duct in state.ventilation.ducts.items()
        ],
    }

    heat_json = {
        "indoor_temp_c": state.heat.indoor_temp_c,
        "indoor_rh_percent": state.heat.indoor_rh_percent,
        "climate_zone": state.heat.climate_zone.name,
        "wall_layers": {
            str(wall_index): [[name, thickness_m] for name, thickness_m in layers]
            for wall_index, layers in state.heat.wall_layers.items()
        },
    }

    fire_json = {
        "detector_kind": state.fire.detector_kind.name,
        "detectors": [
            {"name": d.name, "kind": d.kind.name, "position": [d.position.x, d.position.z]}
            for d in state.fire.detectors.values()
        ],
    }

    roof_json = {
        "roof_type": state.roof.roof_type,
        "slope_deg": state.roof.slope_deg,
        "low_side": state.roof.low_side,
        "ridge_along": state.roof.ridge_along,
    }

    openings3d_json = [
        {
            "name": o.name,
            "wall_index": o.wall_index,
            "kind": o.kind,
            "offset_mm": o.offset_mm,
            "sill_height_mm": o.sill_height_mm,
            "width_mm": o.width_mm,
            "height_mm": o.height_mm,
        }
        for o in state.openings3d.values()
    ]

    return {
        "format": PROJECT_FORMAT,
        "version": PROJECT_FORMAT_VERSION,
        "room": room_json,
        "electrical": electrical_json,
        "lighting": lighting_json,
        "ventilation": ventilation_json,
        "heat": heat_json,
        "fire": fire_json,
        "roof": roof_json,
        "openings3d": openings3d_json,
    }


def import_project(state: "AppState", data: dict[str, Any]) -> None:
    """Відновлює `state` (МУТУЄ його на місці — так само, як усі інші
    обробники модулів 9/11) з JSON, зробленого `export_project`.

    Валідація повторно використовує справжні конструктори ядра
    (`Room.from_contour`, `ConsumptionPoint`, `Wall3D`/`Opening` тощо) —
    так само, як і у відповідних `_handle_*` обробниках, а не
    переписує їхню логіку.
    """
    if data.get("format") != PROJECT_FORMAT:
        raise ValueError(f"Не файл проєкту Ковадла (очікував format={PROJECT_FORMAT!r})")
    if data.get("version", 0) > PROJECT_FORMAT_VERSION:
        raise ValueError(f"Проєкт збережено новішою версією формату ({data.get('version')}) — онови застосунок")

    from .server import GroupMeta, Opening3DState  # локальний імпорт: уникаємо циклу server<->project_io

    # --- кімната ---------------------------------------------------------
    room_data = data.get("room")
    if room_data is None:
        state.room = None
    else:
        points = [Point(float(x), float(z)) for x, z in room_data["contour"]]
        material = Material(name=room_data["material_name"], density_kg_m3=room_data.get("material_density"))
        state.room = Room.from_contour(
            points,
            height=float(room_data["wall_height"]),
            thickness=float(room_data["wall_thickness"]),
            material=material,
            name=room_data.get("room_name") or "",
            snap=False,
        )

    # --- електропроводка (модуль 4/5) -------------------------------------
    electrical = data.get("electrical") or {}
    panel_data = electrical.get("panel")
    state.panel = (
        ConsumptionPoint(
            name=panel_data["name"],
            kind=PointKind.PANEL,
            position=Point(*panel_data["position"]),
        )
        if panel_data
        else None
    )

    state.points.clear()
    for entry in electrical.get("points", []):
        point = ConsumptionPoint(
            name=entry["name"],
            kind=PointKind[entry["kind"]],
            position=Point(*entry["position"]),
            power_w=entry.get("power_w"),
        )
        state.points[point.name] = point
    state._next_index = {
        kind: _max_trailing_number([p.name for p in state.points.values() if p.kind is kind], kind.value.capitalize())
        for kind in PointKind
    }

    state.point_group = dict(electrical.get("point_group", {}))
    state.routes = {
        name: [Point(float(x), float(z)) for x, z in raw_points]
        for name, raw_points in electrical.get("routes", {}).items()
    }
    state.group_meta = {
        group_name: GroupMeta(
            phase=PhaseType[meta["phase"]],
            power_factor=float(meta["power_factor"]),
            connection_allowance_m=float(meta["connection_allowance_m"]),
            min_cross_section_mm2=float(meta["min_cross_section_mm2"]),
            max_voltage_drop_percent=float(meta["max_voltage_drop_percent"]),
        )
        for group_name, meta in electrical.get("group_meta", {}).items()
    }

    # --- освітлення (9.1) --------------------------------------------------
    lighting = data.get("lighting") or {}
    state.lighting.room_purpose = RoomPurpose[lighting.get("room_purpose", state.lighting.room_purpose.name)]
    state.lighting.utilization_factor = float(lighting.get("utilization_factor", state.lighting.utilization_factor))
    state.lighting.maintenance_factor = float(lighting.get("maintenance_factor", state.lighting.maintenance_factor))
    state.lighting.fixtures = {
        entry["name"]: LightFixture(
            name=entry["name"],
            kind=FixtureKind[entry["kind"]],
            position=Point(*entry["position"]),
            luminous_flux_lm=float(entry["luminous_flux_lm"]),
            power_w=float(entry["power_w"]),
            beam_angle_deg=float(entry.get("beam_angle_deg", 120.0)),
            color_temp_k=float(entry.get("color_temp_k", 4000.0)),
        )
        for entry in lighting.get("fixtures", [])
    }
    state.lighting._next_index = _max_trailing_number(list(state.lighting.fixtures.keys()), "Світильник")

    # --- вентиляція (9.2) ---------------------------------------------------
    ventilation = data.get("ventilation") or {}
    state.ventilation.room_kind = VentilatedRoomKind[ventilation.get("room_kind", state.ventilation.room_kind.name)]
    ducts: dict[str, Duct] = {}
    for entry in ventilation.get("ducts", []):
        shape = DuctShape[entry["shape"]]
        extra: dict[str, float] = {}
        if shape is DuctShape.ROUND:
            extra["diameter_mm"] = float(entry["diameter_mm"])
        else:
            extra["width_mm"] = float(entry["width_mm"])
            extra["height_mm"] = float(entry["height_mm"])
        ducts[entry["name"]] = Duct(points=[Point(*p) for p in entry["points"]], shape=shape, **extra)
    state.ventilation.ducts = ducts
    state.ventilation._next_index = _max_trailing_number(list(ducts.keys()), "Повітропровід")

    # --- тепло (9.4) ---------------------------------------------------------
    heat = data.get("heat") or {}
    state.heat.indoor_temp_c = float(heat.get("indoor_temp_c", state.heat.indoor_temp_c))
    state.heat.indoor_rh_percent = float(heat.get("indoor_rh_percent", state.heat.indoor_rh_percent))
    state.heat.climate_zone = ClimateZone[heat.get("climate_zone", state.heat.climate_zone.name)]
    state.heat.wall_layers = {
        int(wall_index): [(name, float(thickness_m)) for name, thickness_m in layers]
        for wall_index, layers in heat.get("wall_layers", {}).items()
    }

    # --- пожежна безпека (9.5) -----------------------------------------------
    fire = data.get("fire") or {}
    state.fire.detector_kind = DetectorKind[fire.get("detector_kind", state.fire.detector_kind.name)]
    state.fire.detectors = {
        entry["name"]: FireDetector(name=entry["name"], kind=DetectorKind[entry["kind"]], position=Point(*entry["position"]))
        for entry in fire.get("detectors", [])
    }

    # --- дах і отвори (модуль 11) ---------------------------------------------
    roof = data.get("roof") or {}
    state.roof.roof_type = roof.get("roof_type", "NONE")
    state.roof.slope_deg = float(roof.get("slope_deg", 30.0))
    state.roof.low_side = roof.get("low_side", "south")
    state.roof.ridge_along = roof.get("ridge_along", "x")

    openings: dict[str, Opening3DState] = {}
    for entry in data.get("openings3d", []):
        wall_index = int(entry["wall_index"])
        if state.room is not None:
            # та сама справжня валідація меж, що й у _handle_opening3d —
            # пошкоджений/несумісний проєкт (напр. після ручного
            # редагування файлу) не має тихо завантажитися з отворами,
            # що виходять за межі стіни.
            existing = [
                Opening(
                    kind=OpeningKind[o["kind"]],
                    offset_mm=o["offset_mm"],
                    sill_height_mm=o["sill_height_mm"],
                    width_mm=o["width_mm"],
                    height_mm=o["height_mm"],
                    name=o["name"],
                )
                for o in data["openings3d"]
                if o["wall_index"] == wall_index
            ]
            if wall_index < 0 or wall_index >= len(state.room.walls):
                raise ValueError(f"Отвір «{entry['name']}»: немає стіни з індексом {wall_index}")
            Wall3D(wall=state.room.walls[wall_index], openings=existing)
        openings[entry["name"]] = Opening3DState(
            wall_index=wall_index,
            kind=entry["kind"],
            offset_mm=float(entry["offset_mm"]),
            sill_height_mm=float(entry["sill_height_mm"]),
            width_mm=float(entry["width_mm"]),
            height_mm=float(entry["height_mm"]),
            name=entry["name"],
        )
    state.openings3d = openings
    # лічильник автоімен спільний для "Вікно N" і "Двері N" (див.
    # AppState.next_opening_name) — беремо максимум серед обох префіксів.
    state._opening_next_index = max(
        _max_trailing_number([o.name for o in openings.values()], "Вікно"),
        _max_trailing_number([o.name for o in openings.values()], "Двері"),
    )
