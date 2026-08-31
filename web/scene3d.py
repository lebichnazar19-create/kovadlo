"""
Складання даних тривимірної сцени (модуль 11) з поточного стану сервера.

Лише серіалізація в JSON для клієнта — саму геометрію (стіни з реальними
прорізами, труби повітроводів, текстуру плитки) будує three.js на
клієнті. Тут використовуються ЛИШЕ публічні функції ядра (модулі 1, 4,
7, 8, 10), нічого в ньому не змінюється.
"""

from __future__ import annotations

from typing import Any

from kovadlo import build_gable_roof, build_route, build_shed_roof
from kovadlo.material_database import MaterialDatabase


def _wall_material_category(wall: Any, material_db: MaterialDatabase) -> str | None:
    spec = material_db.find_by_name(wall.material.name)
    return spec.category.name if spec is not None else None


def build_scene(state: Any, material_db: MaterialDatabase) -> dict:
    """Збирає повний опис сцени для вкладки «3D»."""
    room = state.room
    if room is None:
        raise ValueError("Спочатку намалюйте кімнату")

    openings_by_wall: dict[int, list] = {}
    for opening in state.openings3d.values():
        openings_by_wall.setdefault(opening.wall_index, []).append(opening)

    walls_json = []
    for i, wall in enumerate(room.walls):
        walls_json.append(
            {
                "index": i,
                "start": [wall.start.x, wall.start.z],
                "end": [wall.end.x, wall.end.z],
                "length_mm": wall.length_mm,
                "thickness_mm": wall.thickness_mm,
                "height_mm": wall.height,
                "material_name": wall.material.name,
                "material_category": _wall_material_category(wall, material_db),
                "openings": [
                    {
                        "name": o.name,
                        "kind": o.kind,
                        "offset_mm": o.offset_mm,
                        "sill_height_mm": o.sill_height_mm,
                        "width_mm": o.width_mm,
                        "height_mm": o.height_mm,
                    }
                    for o in openings_by_wall.get(i, [])
                ],
            }
        )

    base_height_mm = room.walls[0].height if room.walls else 2700.0

    roof_json = None
    roof_state = state.roof
    if roof_state.roof_type != "NONE":
        try:
            if roof_state.roof_type == "SHED":
                roof = build_shed_roof(room.contour, base_height_mm, roof_state.slope_deg, low_side=roof_state.low_side)
            else:
                roof = build_gable_roof(
                    room.contour, base_height_mm, roof_state.slope_deg, ridge_along=roof_state.ridge_along
                )
            roof_json = {
                "type": roof.roof_type.name,
                "slope_deg": roof.slope_deg,
                "ridge_rise_mm": roof.ridge_rise_mm,
                "faces": [[[p.x, p.y, p.z] for p in face.points] for face in roof.faces],
            }
        except ValueError:
            # непрямокутний контур чи некоректний кут — дах просто не рендеримо,
            # решта сцени (стіни/підлога) лишається робочою.
            roof_json = None

    ducts_json = []
    for name, duct in state.ventilation.ducts.items():
        entry: dict[str, Any] = {
            "name": name,
            "shape": duct.shape.name,
            "points": [[p.x, p.z] for p in duct.points],
        }
        if duct.diameter_mm:
            entry["diameter_mm"] = duct.diameter_mm
        else:
            entry["width_mm"] = duct.width_mm
            entry["height_mm"] = duct.height_mm
        ducts_json.append(entry)

    routes_json: dict[str, list[list[float]]] = {}
    if state.panel is not None:
        for name, raw in state.routes.items():
            route = build_route(state.panel.position, raw, snap=False)
            routes_json[name] = [[p.x, p.z] for p in route.points]

    fixtures_json = [
        {"name": fixture.name, "position": [fixture.position.x, fixture.position.z]}
        for fixture in state.lighting.fixtures.values()
    ]

    return {
        "room": {
            "name": room.name,
            "contour": [[p.x, p.z] for p in room.contour],
            "walls": walls_json,
            "floor_area_m2": room.floor_area_m2,
        },
        "floor_slab": {"thickness_mm": 200.0},
        "roof": roof_json,
        "ducts": ducts_json,
        "electrical_routes": routes_json,
        "fixtures": fixtures_json,
    }
