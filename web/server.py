"""
Локальний веб-сервер модулів 3 і 5 (візуалізація плану і плитки; модуль 5
додає візуалізацію електропроводки поверх того самого плану).

Лише стандартна бібліотека Python, без зовнішніх залежностей. Обслуговує
одну HTML-сторінку (`static/index.html`) і невеликий JSON API, через
який ця сторінка читає дані з ядра (модулі 1-2, 4 у `kovadlo/`) — сервер
лише викликає функції ядра, нічого в ньому не змінюючи.

Стан (поточна намальована кімната й побудований план проводки)
тримається в пам'яті процесу — цього достатньо для локального
однокористувацького інструменту.
"""

from __future__ import annotations

import json
import math
import sys
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from kovadlo import (
    DEFAULT_INDOOR_TEMP_C,
    DEFAULT_MAINTENANCE_FACTOR,
    DEFAULT_UTILIZATION_FACTOR,
    DESIGN_OUTDOOR_TEMP_C,
    RECOMMENDED_LUX,
    WT2021_MAX_U_WALL_W_M2K,
    CableRoute,
    ClimateZone,
    ConsumptionPoint,
    DetectorKind,
    Duct,
    DuctShape,
    FireDetector,
    FixtureKind,
    Grout,
    Group,
    LightFixture,
    MAX_VOLTAGE_DROP_PERCENT_DEFAULT,
    MIN_CROSS_SECTION_LIGHTING_MM2,
    Material,
    Opening,
    OpeningKind,
    PhaseType,
    Point,
    PointKind,
    Room,
    RoomPurpose,
    RowOffset,
    Surface,
    Tile,
    TileLayout,
    VentilatedRoomKind,
    Wall3D,
    WallLayer,
    WiringPlan,
    air_velocity_m_s,
    auto_place_detectors,
    build_default_database,
    build_route,
    calculate_tiling,
    condensation_risk_warnings,
    format_report,
    format_wiring_report,
    illuminance_lux,
    loop_length_m,
    pressure_loss_pa,
    required_airflow_m3_h,
    required_luminous_flux_lm,
    select_fan,
    snap_point,
    wall_thermal_resistance_m2k_w,
    wall_u_value_w_m2k,
)
from kovadlo.fire_safety_norms import COVERAGE_AREA_M2

from .project_io import export_project, import_project
from .reports import format_fire_report, format_heat_report, format_lighting_report, format_ventilation_report
from .scene3d import build_scene
from .tiling_render import render_tile_placements

_MATERIAL_DB = build_default_database()  # спільна, лише для читання (модуль 7)

STATIC_DIR = Path(__file__).parent / "static"
INDEX_FILE = STATIC_DIR / "index.html"

DEFAULT_PORT = 8765


@dataclass
class GroupMeta:
    """Налаштування групи, що збираються поступово через веб-інтерфейс
    (стан побудови плану в модулі 5 — не частина ядра)."""

    phase: PhaseType = PhaseType.SINGLE
    power_factor: float = 1.0
    connection_allowance_m: float = 0.5
    min_cross_section_mm2: float = MIN_CROSS_SECTION_LIGHTING_MM2
    max_voltage_drop_percent: float = MAX_VOLTAGE_DROP_PERCENT_DEFAULT


@dataclass
class LightingState:
    """Стан вкладки «Освітлення» (модуль 9.1)."""

    room_purpose: RoomPurpose = RoomPurpose.LIVING_ROOM
    utilization_factor: float = DEFAULT_UTILIZATION_FACTOR
    maintenance_factor: float = DEFAULT_MAINTENANCE_FACTOR
    fixtures: dict[str, LightFixture] = field(default_factory=dict)
    _next_index: int = 0

    def next_name(self) -> str:
        self._next_index += 1
        return f"Світильник {self._next_index}"


@dataclass
class VentilationState:
    """Стан вкладки «Вентиляція» (модуль 9.2)."""

    room_kind: VentilatedRoomKind = VentilatedRoomKind.LIVING_ROOM
    ducts: dict[str, Duct] = field(default_factory=dict)
    _next_index: int = 0

    def next_name(self) -> str:
        self._next_index += 1
        return f"Повітропровід {self._next_index}"


@dataclass
class HeatState:
    """Стан вкладки «Тепло» (модуль 9.4): конструкція шарів по стінах.

    Шари зберігаються як (назва_матеріалу, товщина_м), а не готові
    `WallLayer`, — назва матеріалу лишається "посиланням на базу"
    (модуль 7), і `MaterialSpec` підставляється заново з `_MATERIAL_DB`
    щоразу при розрахунку."""

    wall_layers: dict[int, list[tuple[str, float]]] = field(default_factory=dict)
    indoor_temp_c: float = DEFAULT_INDOOR_TEMP_C
    indoor_rh_percent: float = 50.0
    climate_zone: ClimateZone = ClimateZone.ZONE_III


@dataclass
class FireSafetyState:
    """Стан вкладки «Пожежна безпека» (модуль 9.5)."""

    detector_kind: DetectorKind = DetectorKind.SMOKE
    detectors: dict[str, FireDetector] = field(default_factory=dict)


@dataclass
class RoofState:
    """Стан даху для вкладки «3D» (модуль 11) — параметри для
    `build_shed_roof`/`build_gable_roof` (модуль 10)."""

    roof_type: str = "NONE"  # "NONE" | "SHED" | "GABLE"
    slope_deg: float = 30.0
    low_side: str = "south"  # для SHED
    ridge_along: str = "x"  # для GABLE


@dataclass
class Opening3DState:
    """Вікно чи двері в конкретній стіні (модуль 10, `Opening`) —
    зберігаємо сирі поля, а не готовий `Opening`, щоб JSON-серіалізація
    була тривіальною; сам `Opening`/`Wall3D` збираються при валідації
    й при побудові сцени."""

    wall_index: int
    kind: str  # "WINDOW" | "DOOR"
    offset_mm: float
    sill_height_mm: float
    width_mm: float
    height_mm: float
    name: str = ""


@dataclass
class AppState:
    """Стан застосунку: поточна кімната і план проводки, що будується поступово."""

    room: Room | None = None

    # --- модуль 5: електропроводка ---
    panel: ConsumptionPoint | None = None
    points: dict[str, ConsumptionPoint] = field(default_factory=dict)
    point_group: dict[str, str] = field(default_factory=dict)
    routes: dict[str, list[Point]] = field(default_factory=dict)  # ім'я точки -> точки ПІСЛЯ щитка
    group_meta: dict[str, GroupMeta] = field(default_factory=dict)
    _next_index: dict[PointKind, int] = field(default_factory=dict)

    # --- модуль 9: інженерні системи (кожна підсистема — модуль 8) ---
    lighting: LightingState = field(default_factory=LightingState)
    ventilation: VentilationState = field(default_factory=VentilationState)
    heat: HeatState = field(default_factory=HeatState)
    fire: FireSafetyState = field(default_factory=FireSafetyState)

    # --- модуль 11: 3D-перегляд ---
    roof: RoofState = field(default_factory=RoofState)
    openings3d: dict[str, Opening3DState] = field(default_factory=dict)
    _opening_next_index: int = 0

    def next_point_name(self, kind: PointKind) -> str:
        """Автогенероване ім'я точки: «Розетка 1», «Розетка 2», ..."""
        n = self._next_index.get(kind, 0) + 1
        self._next_index[kind] = n
        return f"{kind.value.capitalize()} {n}"

    def next_opening_name(self, kind: str) -> str:
        """Автогенероване ім'я отвору: «Вікно 1», «Двері 1», ..."""
        self._opening_next_index += 1
        label = "Вікно" if kind == "WINDOW" else "Двері"
        return f"{label} {self._opening_next_index}"


def _json_bytes(data: Any) -> bytes:
    return json.dumps(data, ensure_ascii=False).encode("utf-8")


def _room_to_json(room: Room) -> dict:
    return {
        "name": room.name,
        "contour": [[p.x, p.z] for p in room.contour],
        "floor_area_m2": room.floor_area_m2,
        "perimeter_mm": room.perimeter_mm,
        "walls": [
            {
                "index": i,
                "start": [wall.start.x, wall.start.z],
                "end": [wall.end.x, wall.end.z],
                "length_mm": wall.length_mm,
                "thickness_mm": wall.thickness_mm,
                "height_mm": wall.height,
                "material": wall.material.name,
                "area_m2": wall.area_m2,
            }
            for i, wall in enumerate(room.walls)
        ],
    }


def _row_offset_from_str(value: str) -> RowOffset:
    try:
        return RowOffset[value]
    except KeyError as exc:
        raise ValueError(f"Невідомий зсув рядів: {value!r}") from exc


def _point_kind_from_str(value: str) -> PointKind:
    try:
        return PointKind[value]
    except KeyError as exc:
        raise ValueError(f"Невідомий тип точки: {value!r}") from exc


def _phase_from_str(value: str) -> PhaseType:
    try:
        return PhaseType[value]
    except KeyError as exc:
        raise ValueError(f"Невідома фаза: {value!r}") from exc


def _fixture_kind_from_str(value: str) -> FixtureKind:
    try:
        return FixtureKind[value]
    except KeyError as exc:
        raise ValueError(f"Невідомий тип світильника: {value!r}") from exc


def _room_purpose_from_str(value: str) -> RoomPurpose:
    try:
        return RoomPurpose[value]
    except KeyError as exc:
        raise ValueError(f"Невідоме призначення кімнати: {value!r}") from exc


def _duct_shape_from_str(value: str) -> DuctShape:
    try:
        return DuctShape[value]
    except KeyError as exc:
        raise ValueError(f"Невідома форма повітропроводу: {value!r}") from exc


def _ventilated_room_kind_from_str(value: str) -> VentilatedRoomKind:
    try:
        return VentilatedRoomKind[value]
    except KeyError as exc:
        raise ValueError(f"Невідоме призначення приміщення: {value!r}") from exc


def _climate_zone_from_str(value: str) -> ClimateZone:
    try:
        return ClimateZone[value]
    except KeyError as exc:
        raise ValueError(f"Невідома кліматична зона: {value!r}") from exc


def _detector_kind_from_str(value: str) -> DetectorKind:
    try:
        return DetectorKind[value]
    except KeyError as exc:
        raise ValueError(f"Невідомий тип датчика: {value!r}") from exc


def _light_fixture_to_json(fixture: LightFixture) -> dict:
    return {
        "name": fixture.name,
        "kind": fixture.kind.name,
        "kind_label": fixture.kind.value,
        "position": [fixture.position.x, fixture.position.z],
        "luminous_flux_lm": fixture.luminous_flux_lm,
        "power_w": fixture.power_w,
        "beam_angle_deg": fixture.beam_angle_deg,
        "color_temp_k": fixture.color_temp_k,
    }


def _duct_to_json(name: str, duct: Duct) -> dict:
    data: dict[str, Any] = {
        "name": name,
        "shape": duct.shape.name,
        "shape_label": duct.shape.value,
        "points": [[p.x, p.z] for p in duct.points],
        "length_m": duct.length_m,
    }
    if duct.shape is DuctShape.ROUND:
        data["diameter_mm"] = duct.diameter_mm
    else:
        data["width_mm"] = duct.width_mm
        data["height_mm"] = duct.height_mm
    return data


def _electrical_point_to_json(point: ConsumptionPoint, group_name: str | None, has_route: bool) -> dict:
    return {
        "name": point.name,
        "kind": point.kind.name,
        "kind_label": point.kind.value,
        "position": [point.position.x, point.position.z],
        "power_w": point.power_w,
        "group": group_name,
        "has_route": has_route,
    }


def _build_groups(state: AppState) -> tuple[list[Group], list[str]]:
    """Складає повноцінні `Group` (ядро, модуль 4) із поточного стану.

    Повертає (готові_групи, імена_точок_без_групи_або_траси) — незавершені
    точки не блокують розрахунок решти, а просто позначаються як "в очікуванні".
    """
    if state.panel is None:
        return [], list(state.points.keys())

    by_group: dict[str, list[ConsumptionPoint]] = {}
    routes_by_group: dict[str, dict[str, CableRoute]] = {}
    pending: list[str] = []

    for name, point in state.points.items():
        group_name = state.point_group.get(name)
        raw_route = state.routes.get(name)
        if group_name is None or raw_route is None:
            pending.append(name)
            continue
        by_group.setdefault(group_name, []).append(point)
        route = build_route(state.panel.position, raw_route, snap=False)
        routes_by_group.setdefault(group_name, {})[name] = route

    groups: list[Group] = []
    for group_name, points in by_group.items():
        meta = state.group_meta.get(group_name, GroupMeta())
        groups.append(
            Group(
                name=group_name,
                phase=meta.phase,
                points=points,
                routes=routes_by_group[group_name],
                power_factor=meta.power_factor,
                connection_allowance_m=meta.connection_allowance_m,
                min_cross_section_mm2=meta.min_cross_section_mm2,
                max_voltage_drop_percent=meta.max_voltage_drop_percent,
            )
        )
    return groups, pending


def build_handler_class(state: AppState) -> type[BaseHTTPRequestHandler]:
    """Створює клас-обробник запитів, прив'язаний до конкретного `AppState`.

    Фабрика (а не єдиний глобальний стан на рівні модуля) потрібна, щоб
    кожен запущений сервер — і кожен тест — мав власний, ізольований
    стан кімнати.
    """

    class Handler(BaseHTTPRequestHandler):
        server_version = "KovadloViz/1.0"

        def log_message(self, format: str, *args: Any) -> None:  # noqa: A002
            pass  # тихий сервер: не засмічуємо консоль стандартними логами http.server

        # ---- допоміжні методи відповіді ----

        def _send_json(self, status: int, data: Any) -> None:
            body = _json_bytes(data)
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _send_error_json(self, status: int, message: str) -> None:
            self._send_json(status, {"error": message})

        def _read_json_body(self) -> dict:
            length = int(self.headers.get("Content-Length", 0) or 0)
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw or b"{}")

        # ---- маршрутизація ----

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._serve_index()
            elif self.path == "/api/room":
                self._handle_get_room()
            elif self.path == "/api/electrical/state":
                self._handle_electrical_state()
            elif self.path == "/api/electrical/report":
                self._handle_electrical_report()
            elif self.path == "/api/lighting/state":
                self._handle_lighting_state()
            elif self.path == "/api/ventilation/state":
                self._handle_ventilation_state()
            elif self.path == "/api/heat/materials":
                self._handle_heat_materials()
            elif self.path == "/api/heat/state":
                self._handle_heat_state()
            elif self.path == "/api/fire/state":
                self._handle_fire_state()
            elif self.path == "/api/scene3d":
                self._handle_scene3d()
            elif self.path == "/api/project/export":
                self._handle_project_export()
            else:
                self._send_error_json(404, "Не знайдено")

        def do_POST(self) -> None:  # noqa: N802
            if self.path == "/api/snap":
                self._handle_snap()
            elif self.path == "/api/room":
                self._handle_post_room()
            elif self.path == "/api/tiling":
                self._handle_tiling()
            elif self.path == "/api/electrical/point":
                self._handle_electrical_point()
            elif self.path == "/api/electrical/point_delete":
                self._handle_electrical_point_delete()
            elif self.path == "/api/electrical/assign_group":
                self._handle_electrical_assign_group()
            elif self.path == "/api/electrical/route":
                self._handle_electrical_route()
            elif self.path == "/api/electrical/reset":
                self._handle_electrical_reset()
            elif self.path == "/api/lighting/settings":
                self._handle_lighting_settings()
            elif self.path == "/api/lighting/fixture":
                self._handle_lighting_fixture()
            elif self.path == "/api/lighting/fixture_delete":
                self._handle_lighting_fixture_delete()
            elif self.path == "/api/lighting/reset":
                self._handle_lighting_reset()
            elif self.path == "/api/ventilation/settings":
                self._handle_ventilation_settings()
            elif self.path == "/api/ventilation/duct":
                self._handle_ventilation_duct()
            elif self.path == "/api/ventilation/duct_delete":
                self._handle_ventilation_duct_delete()
            elif self.path == "/api/ventilation/reset":
                self._handle_ventilation_reset()
            elif self.path == "/api/heat/settings":
                self._handle_heat_settings()
            elif self.path == "/api/heat/wall_layers":
                self._handle_heat_wall_layers()
            elif self.path == "/api/heat/reset":
                self._handle_heat_reset()
            elif self.path == "/api/fire/settings":
                self._handle_fire_settings()
            elif self.path == "/api/fire/auto_place":
                self._handle_fire_auto_place()
            elif self.path == "/api/fire/reset":
                self._handle_fire_reset()
            elif self.path == "/api/roof/settings":
                self._handle_roof_settings()
            elif self.path == "/api/opening3d":
                self._handle_opening3d()
            elif self.path == "/api/opening3d_delete":
                self._handle_opening3d_delete()
            elif self.path == "/api/opening3d_reset":
                self._handle_opening3d_reset()
            elif self.path == "/api/project/import":
                self._handle_project_import()
            else:
                self._send_error_json(404, "Не знайдено")

        # ---- обробники ----

        def _serve_index(self) -> None:
            body = INDEX_FILE.read_bytes()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _handle_snap(self) -> None:
            try:
                payload = self._read_json_body()
                origin = Point(float(payload["origin"][0]), float(payload["origin"][1]))
                target = Point(float(payload["target"][0]), float(payload["target"][1]))
                step = float(payload.get("step", 15.0))
                snapped = snap_point(origin, target, step)
                self._send_json(200, {"x": snapped.x, "z": snapped.z})
            except Exception as exc:  # noqa: BLE001 - межа процесу: будь-яка помилка -> 400 клієнту
                self._send_error_json(400, str(exc))

        def _handle_get_room(self) -> None:
            if state.room is None:
                self._send_error_json(404, "Кімнату ще не намальовано")
                return
            self._send_json(200, _room_to_json(state.room))

        def _handle_post_room(self) -> None:
            try:
                payload = self._read_json_body()
                points = [Point(float(x), float(z)) for x, z in payload["points"]]
                height = float(payload.get("wall_height", 2700))
                thickness = float(payload.get("wall_thickness", 200))
                material_name = payload.get("material_name") or "цегла"
                density = payload.get("material_density")
                name = payload.get("room_name") or ""
                material = Material(name=material_name, density_kg_m3=density)

                # точки вже прив'язані до кута на клієнті (через /api/snap
                # по мірі малювання), тож тут повторний snap не потрібен.
                room = Room.from_contour(
                    points, height=height, thickness=thickness, material=material, name=name, snap=False
                )
                state.room = room
                self._send_json(200, _room_to_json(room))
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_tiling(self) -> None:
            try:
                if state.room is None:
                    raise ValueError("Спочатку намалюйте кімнату")
                payload = self._read_json_body()

                surface_spec = payload["surface"]
                if surface_spec == "floor":
                    surface = Surface.from_room_floor(state.room)
                else:
                    wall_index = int(surface_spec["wall_index"])
                    wall = state.room.walls[wall_index]
                    surface = Surface.from_wall(wall, name=f"стіна {wall_index + 1}")

                tile_payload = payload["tile"]
                tile = Tile(
                    width=float(tile_payload["width"]),
                    height=float(tile_payload["height"]),
                    name=tile_payload.get("name") or "",
                    color=tile_payload.get("color") or "#c9beac",
                )
                grout_payload = payload["grout"]
                grout = Grout(
                    width_mm=float(grout_payload["width_mm"]),
                    color=grout_payload.get("color") or "#8a8a8a",
                )

                layout_payload = payload.get("layout") or {}
                start = layout_payload.get("start", [0, 0])
                layout = TileLayout(
                    start=Point(float(start[0]), float(start[1])),
                    row_offset=_row_offset_from_str(layout_payload.get("row_offset", "NONE")),
                    angle=float(layout_payload.get("angle", 0)),
                )

                tiles_per_package = int(payload.get("tiles_per_package", 1))
                waste_fraction = float(payload.get("waste_fraction", 0.10))

                result = calculate_tiling(
                    surface,
                    tile,
                    grout,
                    layout,
                    tiles_per_package=tiles_per_package,
                    waste_fraction=waste_fraction,
                )
                placements = render_tile_placements(surface, tile, grout, layout)

                self._send_json(
                    200,
                    {
                        "surface": {
                            "name": surface.name,
                            "contour": [[p.x, p.z] for p in surface.contour],
                        },
                        "report_text": format_report(surface, tile, grout, layout, result),
                        "whole_tiles_count": result.whole_tiles_count,
                        "cuts_count": result.cuts_count,
                        "total_tiles_needed": result.total_tiles_needed,
                        "packages_needed": result.packages_needed,
                        "reserve_tiles": result.reserve_tiles,
                        "grout_area_m2": result.grout_area_m2,
                        "tile_color": tile.color,
                        "grout_color": grout.color,
                        "placements": [
                            {
                                "points": [[p.x, p.z] for p in placement.points],
                                "kind": placement.kind,
                                "label": placement.label,
                            }
                            for placement in placements
                        ],
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        # ---- модуль 5: електропроводка ----

        def _handle_electrical_point(self) -> None:
            """Ставить точку споживання (або щиток) на плані."""
            try:
                payload = self._read_json_body()
                kind = _point_kind_from_str(payload["kind"])
                position = Point(float(payload["position"][0]), float(payload["position"][1]))

                if kind is PointKind.PANEL:
                    name = payload.get("name") or "Щиток"
                    state.panel = ConsumptionPoint(name=name, kind=PointKind.PANEL, position=position)
                    self._send_json(200, _electrical_point_to_json(state.panel, None, True))
                    return

                name = payload.get("name") or state.next_point_name(kind)
                power_w = payload.get("power_w")
                point = ConsumptionPoint(name=name, kind=kind, position=position, power_w=power_w)
                state.points[name] = point
                self._send_json(
                    200, _electrical_point_to_json(point, state.point_group.get(name), name in state.routes)
                )
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_electrical_point_delete(self) -> None:
            """Прибирає точку (і її групування/трасу) з плану."""
            try:
                payload = self._read_json_body()
                name = payload["point_name"]
                state.points.pop(name, None)
                state.point_group.pop(name, None)
                state.routes.pop(name, None)
                self._send_json(200, {"deleted": name})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_electrical_assign_group(self) -> None:
            """Прив'язує точку до групи; за потреби створює/оновлює групу."""
            try:
                payload = self._read_json_body()
                point_name = payload["point_name"]
                if point_name not in state.points:
                    raise ValueError(f"Немає такої точки: {point_name!r}")
                group_name = payload["group_name"]
                if not group_name:
                    raise ValueError("Назва групи не може бути порожньою")

                meta = state.group_meta.get(group_name, GroupMeta())
                if "phase" in payload:
                    meta.phase = _phase_from_str(payload["phase"])
                if "power_factor" in payload:
                    meta.power_factor = float(payload["power_factor"])
                if "connection_allowance_m" in payload:
                    meta.connection_allowance_m = float(payload["connection_allowance_m"])
                if "min_cross_section_mm2" in payload:
                    meta.min_cross_section_mm2 = float(payload["min_cross_section_mm2"])
                if "max_voltage_drop_percent" in payload:
                    meta.max_voltage_drop_percent = float(payload["max_voltage_drop_percent"])
                state.group_meta[group_name] = meta
                state.point_group[point_name] = group_name

                self._send_json(200, {"point_name": point_name, "group_name": group_name})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_electrical_route(self) -> None:
            """Зберігає завершену трасу кабелю для точки (без щитка — він
            підставляється з поточного `state.panel` при кожному використанні,
            тож переміщення щитка автоматично "тягне" за собою всі траси)."""
            try:
                payload = self._read_json_body()
                point_name = payload["point_name"]
                if point_name not in state.points:
                    raise ValueError(f"Немає такої точки: {point_name!r}")
                if state.panel is None:
                    raise ValueError("Спочатку поставте щиток")

                raw_points = [Point(float(x), float(z)) for x, z in payload["points"]]
                # точки вже прив'язані до 90° на клієнті (через /api/snap),
                # тут лише перевіряємо, що траса взагалі будується.
                route = build_route(state.panel.position, raw_points, snap=False)
                state.routes[point_name] = raw_points

                self._send_json(200, {"point_name": point_name, "length_m": route.length_m})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_electrical_state(self) -> None:
            """Повний поточний стан плану проводки — для малювання на canvas."""
            points_json = [
                _electrical_point_to_json(point, state.point_group.get(name), name in state.routes)
                for name, point in state.points.items()
            ]
            routes_json: dict[str, list[list[float]]] = {}
            if state.panel is not None:
                for name, raw in state.routes.items():
                    route = build_route(state.panel.position, raw, snap=False)
                    routes_json[name] = [[p.x, p.z] for p in route.points]

            self._send_json(
                200,
                {
                    "panel": (
                        {"name": state.panel.name, "position": [state.panel.position.x, state.panel.position.z]}
                        if state.panel is not None
                        else None
                    ),
                    "points": points_json,
                    "groups": sorted({g for g in state.point_group.values()}),
                    "routes": routes_json,
                },
            )

        def _handle_electrical_report(self) -> None:
            """Розрахунок (ядро, модуль 4) по всіх завершених групах +
            текстовий звіт зі специфікацією на закупівлю."""
            groups, pending = _build_groups(state)
            if not groups:
                self._send_json(200, {"report_text": "", "groups": [], "pending_points": pending})
                return

            plan = WiringPlan(panel=state.panel, groups=groups)
            calcs = plan.calculations()
            self._send_json(
                200,
                {
                    "report_text": format_wiring_report(plan),
                    "groups": [
                        {
                            "group_name": c.group_name,
                            "phase": c.phase.name,
                            "total_power_w": c.total_power_w,
                            "design_current_a": c.design_current_a,
                            "breaker_rating_a": c.breaker_rating_a,
                            "cross_section_mm2": c.cross_section_mm2,
                            "voltage_drop_percent": c.voltage_drop_percent,
                            "rcd_required": c.rcd_required,
                            "rcd_note": c.rcd_note,
                        }
                        for c in calcs
                    ],
                    "pending_points": pending,
                },
            )

        def _handle_electrical_reset(self) -> None:
            """Скидає весь план проводки (кімната лишається)."""
            state.panel = None
            state.points.clear()
            state.point_group.clear()
            state.routes.clear()
            state.group_meta.clear()
            state._next_index.clear()
            self._send_json(200, {"reset": True})

        # ---- модуль 9.1: освітлення ----

        def _handle_lighting_settings(self) -> None:
            try:
                payload = self._read_json_body()
                if "room_purpose" in payload:
                    state.lighting.room_purpose = _room_purpose_from_str(payload["room_purpose"])
                if "utilization_factor" in payload:
                    state.lighting.utilization_factor = float(payload["utilization_factor"])
                if "maintenance_factor" in payload:
                    state.lighting.maintenance_factor = float(payload["maintenance_factor"])
                self._send_json(200, {"ok": True})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_lighting_fixture(self) -> None:
            try:
                payload = self._read_json_body()
                kind = _fixture_kind_from_str(payload["kind"])
                position = Point(float(payload["position"][0]), float(payload["position"][1]))
                name = payload.get("name") or state.lighting.next_name()
                fixture = LightFixture(
                    name=name,
                    kind=kind,
                    position=position,
                    luminous_flux_lm=float(payload.get("luminous_flux_lm", 800.0)),
                    power_w=float(payload.get("power_w", 8.0)),
                    beam_angle_deg=float(payload.get("beam_angle_deg", 120.0)),
                    color_temp_k=float(payload.get("color_temp_k", 4000.0)),
                )
                state.lighting.fixtures[name] = fixture
                self._send_json(200, _light_fixture_to_json(fixture))
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_lighting_fixture_delete(self) -> None:
            try:
                payload = self._read_json_body()
                name = payload["name"]
                state.lighting.fixtures.pop(name, None)
                self._send_json(200, {"deleted": name})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_lighting_reset(self) -> None:
            state.lighting.fixtures.clear()
            state.lighting._next_index = 0
            self._send_json(200, {"reset": True})

        def _handle_lighting_state(self) -> None:
            try:
                if state.room is None:
                    raise ValueError("Спочатку намалюйте кімнату")
                fixtures = list(state.lighting.fixtures.values())
                purpose = state.lighting.room_purpose
                uf, mf = state.lighting.utilization_factor, state.lighting.maintenance_factor
                target_lux = RECOMMENDED_LUX[purpose]
                total_flux = sum(f.luminous_flux_lm for f in fixtures)
                achieved = (
                    illuminance_lux(total_flux, state.room.floor_area_m2, utilization_factor=uf, maintenance_factor=mf)
                    if total_flux > 0
                    else 0.0
                )
                meets = achieved >= target_lux
                deficit_flux = None
                if not meets:
                    deficit_flux = (
                        required_luminous_flux_lm(
                            target_lux, state.room.floor_area_m2, utilization_factor=uf, maintenance_factor=mf
                        )
                        - total_flux
                    )
                report_text = format_lighting_report(
                    state.room, purpose, fixtures, utilization_factor=uf, maintenance_factor=mf
                )
                self._send_json(
                    200,
                    {
                        "room_purpose": purpose.name,
                        "target_lux": target_lux,
                        "fixtures": [_light_fixture_to_json(f) for f in fixtures],
                        "total_flux_lm": total_flux,
                        "achieved_lux": achieved,
                        "meets_target": meets,
                        "deficit_flux_lm": deficit_flux,
                        "total_power_w": sum(f.power_w for f in fixtures),
                        "report_text": report_text,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        # ---- модуль 9.2: вентиляція ----

        def _handle_ventilation_settings(self) -> None:
            try:
                payload = self._read_json_body()
                if "room_kind" in payload:
                    state.ventilation.room_kind = _ventilated_room_kind_from_str(payload["room_kind"])
                self._send_json(200, {"ok": True})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_ventilation_duct(self) -> None:
            try:
                payload = self._read_json_body()
                points = [Point(float(x), float(z)) for x, z in payload["points"]]
                shape = _duct_shape_from_str(payload["shape"])
                extra: dict[str, float] = {}
                if shape is DuctShape.ROUND:
                    extra["diameter_mm"] = float(payload["diameter_mm"])
                else:
                    extra["width_mm"] = float(payload["width_mm"])
                    extra["height_mm"] = float(payload["height_mm"])
                duct = Duct(points=points, shape=shape, **extra)
                name = payload.get("name") or state.ventilation.next_name()
                state.ventilation.ducts[name] = duct
                self._send_json(200, _duct_to_json(name, duct))
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_ventilation_duct_delete(self) -> None:
            try:
                payload = self._read_json_body()
                name = payload["name"]
                state.ventilation.ducts.pop(name, None)
                self._send_json(200, {"deleted": name})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_ventilation_reset(self) -> None:
            state.ventilation.ducts.clear()
            state.ventilation._next_index = 0
            self._send_json(200, {"reset": True})

        def _handle_ventilation_state(self) -> None:
            try:
                if state.room is None:
                    raise ValueError("Спочатку намалюйте кімнату")
                room_kind = state.ventilation.room_kind
                # висота кімнати береться з першої стіни (Room.from_contour
                # будує всі стіни з однією висотою) — орієнтовно для об'єму.
                height_m = (state.room.walls[0].height / 1000.0) if state.room.walls else 0.0
                volume_m3 = state.room.floor_area_m2 * height_m
                airflow = required_airflow_m3_h(room_kind, volume_m3) if volume_m3 > 0 else 0.0

                ducts_info = []
                report_ducts = []
                total_dp = 0.0
                for name, duct in state.ventilation.ducts.items():
                    area = duct.cross_section_area_m2()
                    velocity = air_velocity_m_s(airflow, area) if airflow > 0 else 0.0
                    dp = pressure_loss_pa(duct, airflow) if airflow > 0 else 0.0
                    total_dp += dp
                    info = _duct_to_json(name, duct)
                    info["velocity_m_s"] = velocity
                    info["pressure_loss_pa"] = dp
                    ducts_info.append(info)
                    report_ducts.append((name, duct, velocity, dp))

                fan = None
                if state.ventilation.ducts and airflow > 0:
                    try:
                        fan = select_fan(airflow, total_dp)
                    except ValueError:
                        fan = None

                report_text = format_ventilation_report(state.room, room_kind, airflow, report_ducts, fan)

                self._send_json(
                    200,
                    {
                        "room_kind": room_kind.name,
                        "required_airflow_m3_h": airflow,
                        "ducts": ducts_info,
                        "total_pressure_loss_pa": total_dp,
                        "fan": {"name": fan[0], "max_flow_m3_h": fan[1], "max_pressure_pa": fan[2]} if fan else None,
                        "report_text": report_text,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        # ---- модуль 9.4: тепло ----

        def _handle_heat_materials(self) -> None:
            self._send_json(
                200,
                [
                    {
                        "name": material.name,
                        "category": material.category.value,
                        "thermal_conductivity_w_mk": material.thermal_conductivity_w_mk,
                    }
                    for material in _MATERIAL_DB.materials
                    if material.thermal_conductivity_w_mk is not None
                ],
            )

        def _handle_heat_settings(self) -> None:
            try:
                payload = self._read_json_body()
                if "indoor_temp_c" in payload:
                    state.heat.indoor_temp_c = float(payload["indoor_temp_c"])
                if "indoor_rh_percent" in payload:
                    state.heat.indoor_rh_percent = float(payload["indoor_rh_percent"])
                if "climate_zone" in payload:
                    state.heat.climate_zone = _climate_zone_from_str(payload["climate_zone"])
                self._send_json(200, {"ok": True})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_heat_wall_layers(self) -> None:
            try:
                if state.room is None:
                    raise ValueError("Спочатку намалюйте кімнату")
                payload = self._read_json_body()
                wall_index = int(payload["wall_index"])
                if wall_index < 0 or wall_index >= len(state.room.walls):
                    raise ValueError(f"Немає стіни з індексом {wall_index}")

                layers: list[tuple[str, float]] = []
                for entry in payload.get("layers", []):
                    material_name = entry["material_name"]
                    if _MATERIAL_DB.find_by_name(material_name) is None:
                        raise ValueError(f"Немає матеріалу «{material_name}» в базі (модуль 7)")
                    thickness_mm = float(entry["thickness_mm"])
                    if thickness_mm <= 0:
                        raise ValueError("Товщина шару має бути додатною")
                    layers.append((material_name, thickness_mm / 1000.0))

                if layers:
                    state.heat.wall_layers[wall_index] = layers
                else:
                    state.heat.wall_layers.pop(wall_index, None)

                self._send_json(200, {"wall_index": wall_index, "layers_count": len(layers)})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_heat_reset(self) -> None:
            state.heat.wall_layers.clear()
            self._send_json(200, {"reset": True})

        def _handle_heat_state(self) -> None:
            try:
                if state.room is None:
                    raise ValueError("Спочатку намалюйте кімнату")
                zone = state.heat.climate_zone
                outdoor_temp = DESIGN_OUTDOOR_TEMP_C[zone]
                indoor_temp = state.heat.indoor_temp_c
                indoor_rh = state.heat.indoor_rh_percent

                walls_json = []
                report_wall_data = []
                for index, wall in enumerate(state.room.walls):
                    raw_layers = state.heat.wall_layers.get(index)
                    entry: dict[str, Any] = {
                        "index": index,
                        "length_mm": wall.length_mm,
                        "height_mm": wall.height,
                        "area_m2": wall.area_m2,
                        "has_layers": raw_layers is not None,
                        "layers": [
                            {"material_name": name, "thickness_mm": thickness_m * 1000.0}
                            for name, thickness_m in (raw_layers or [])
                        ],
                    }
                    if raw_layers:
                        wall_layers = [
                            WallLayer(_MATERIAL_DB.find_by_name(name), thickness_m) for name, thickness_m in raw_layers
                        ]
                        r_total = wall_thermal_resistance_m2k_w(wall_layers)
                        u_value = wall_u_value_w_m2k(wall_layers)
                        delta_t = indoor_temp - outdoor_temp
                        entry["r_value_m2k_w"] = r_total
                        entry["u_value_w_m2k"] = u_value
                        entry["meets_wt2021"] = u_value <= WT2021_MAX_U_WALL_W_M2K + 1e-9
                        entry["heat_loss_w"] = wall.area_m2 * u_value * delta_t
                        entry["condensation_warnings"] = condensation_risk_warnings(
                            wall_layers, indoor_temp, indoor_rh, outdoor_temp
                        )
                        report_wall_data.append((index, wall_layers, indoor_temp, indoor_rh))
                    walls_json.append(entry)

                report_text = format_heat_report(state.room, report_wall_data, zone)

                self._send_json(
                    200,
                    {
                        "climate_zone": zone.name,
                        "indoor_temp_c": indoor_temp,
                        "indoor_rh_percent": indoor_rh,
                        "outdoor_design_temp_c": outdoor_temp,
                        "max_u_wt2021": WT2021_MAX_U_WALL_W_M2K,
                        "walls": walls_json,
                        "report_text": report_text,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        # ---- модуль 9.5: пожежна безпека ----

        def _handle_fire_settings(self) -> None:
            try:
                payload = self._read_json_body()
                if "detector_kind" in payload:
                    state.fire.detector_kind = _detector_kind_from_str(payload["detector_kind"])
                self._send_json(200, {"ok": True})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_fire_auto_place(self) -> None:
            try:
                if state.room is None:
                    raise ValueError("Спочатку намалюйте кімнату")
                detectors = auto_place_detectors(state.room, state.fire.detector_kind)
                state.fire.detectors = {d.name: d for d in detectors}
                self._send_json(200, {"count": len(detectors)})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_fire_reset(self) -> None:
            state.fire.detectors.clear()
            self._send_json(200, {"reset": True})

        def _handle_fire_state(self) -> None:
            try:
                if state.room is None:
                    raise ValueError("Спочатку намалюйте кімнату")
                detectors = list(state.fire.detectors.values())
                loop = None
                if state.panel is not None:
                    loop = loop_length_m(state.panel.position, [d.position for d in detectors])
                radius_m = math.sqrt(COVERAGE_AREA_M2[state.fire.detector_kind] / math.pi)
                report_text = format_fire_report(state.room, state.fire.detector_kind, detectors, loop)

                self._send_json(
                    200,
                    {
                        "detector_kind": state.fire.detector_kind.name,
                        "detectors": [
                            {"name": d.name, "kind": d.kind.name, "position": [d.position.x, d.position.z]}
                            for d in detectors
                        ],
                        "coverage_radius_m": radius_m,
                        "loop_length_m": loop,
                        "panel_position": [state.panel.position.x, state.panel.position.z] if state.panel else None,
                        "report_text": report_text,
                    },
                )
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        # ---- модуль 11: 3D-перегляд ----

        def _handle_scene3d(self) -> None:
            """Повний опис сцени для вкладки «3D» (`web/scene3d.py`)."""
            try:
                scene = build_scene(state, _MATERIAL_DB)
                self._send_json(200, scene)
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_roof_settings(self) -> None:
            try:
                payload = self._read_json_body()
                roof_type = payload.get("roof_type", state.roof.roof_type)
                if roof_type not in ("NONE", "SHED", "GABLE"):
                    raise ValueError(f"Невідомий тип даху: {roof_type!r}")
                state.roof.roof_type = roof_type
                if "slope_deg" in payload:
                    state.roof.slope_deg = float(payload["slope_deg"])
                if "low_side" in payload:
                    state.roof.low_side = payload["low_side"]
                if "ridge_along" in payload:
                    state.roof.ridge_along = payload["ridge_along"]
                self._send_json(200, {"ok": True})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_opening3d(self) -> None:
            """Додає вікно/двері в конкретну стіну. Перевикористовує
            справжню валідацію ядра (`Wall3D`, модуль 10) — чи отвір
            узагалі вписується в стіну, — замість дублювати цю
            перевірку тут."""
            try:
                if state.room is None:
                    raise ValueError("Спочатку намалюйте кімнату")
                payload = self._read_json_body()
                wall_index = int(payload["wall_index"])
                if wall_index < 0 or wall_index >= len(state.room.walls):
                    raise ValueError(f"Немає стіни з індексом {wall_index}")
                kind = payload["kind"]
                if kind not in ("WINDOW", "DOOR"):
                    raise ValueError(f"Невідомий тип отвору: {kind!r}")

                offset_mm = float(payload["offset_mm"])
                sill_height_mm = float(payload.get("sill_height_mm", 0.0))
                width_mm = float(payload["width_mm"])
                height_mm = float(payload["height_mm"])
                name = payload.get("name") or state.next_opening_name(kind)

                def _to_core_opening(entry_kind: str, o_offset: float, o_sill: float, o_width: float, o_height: float, o_name: str) -> Opening:
                    return Opening(
                        kind=OpeningKind.WINDOW if entry_kind == "WINDOW" else OpeningKind.DOOR,
                        offset_mm=o_offset,
                        sill_height_mm=o_sill,
                        width_mm=o_width,
                        height_mm=o_height,
                        name=o_name,
                    )

                existing = [
                    _to_core_opening(o.kind, o.offset_mm, o.sill_height_mm, o.width_mm, o.height_mm, o.name)
                    for o in state.openings3d.values()
                    if o.wall_index == wall_index
                ]
                new_opening = _to_core_opening(kind, offset_mm, sill_height_mm, width_mm, height_mm, name)
                Wall3D(wall=state.room.walls[wall_index], openings=[*existing, new_opening])  # валідація меж

                state.openings3d[name] = Opening3DState(
                    wall_index=wall_index,
                    kind=kind,
                    offset_mm=offset_mm,
                    sill_height_mm=sill_height_mm,
                    width_mm=width_mm,
                    height_mm=height_mm,
                    name=name,
                )
                self._send_json(200, {"name": name, "wall_index": wall_index})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_opening3d_delete(self) -> None:
            try:
                payload = self._read_json_body()
                name = payload["name"]
                state.openings3d.pop(name, None)
                self._send_json(200, {"deleted": name})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

        def _handle_opening3d_reset(self) -> None:
            state.openings3d.clear()
            state._opening_next_index = 0
            self._send_json(200, {"reset": True})

        # ---- модуль 14: файл проєкту ----

        def _handle_project_export(self) -> None:
            """Повний стан сервера як JSON — те, що клієнт зберігає у файл
            (`web/project_io.py`)."""
            self._send_json(200, export_project(state))

        def _handle_project_import(self) -> None:
            """Відновлює стан сервера з JSON файлу проєкту."""
            try:
                payload = self._read_json_body()
                import_project(state, payload)
                self._send_json(200, {"ok": True})
            except Exception as exc:  # noqa: BLE001
                self._send_error_json(400, str(exc))

    return Handler


def create_server(port: int = DEFAULT_PORT, state: AppState | None = None) -> ThreadingHTTPServer:
    """Створює (але не запускає) HTTP-сервер, прив'язаний до `state`.

    `port=0` дозволяє ОС обрати вільний порт (зручно для тестів).
    """
    state = state if state is not None else AppState()
    handler_cls = build_handler_class(state)
    return ThreadingHTTPServer(("127.0.0.1", port), handler_cls)


def run(port: int = DEFAULT_PORT) -> None:
    """Запускає сервер і блокує потік, поки його не зупинять (Ctrl+C)."""
    server = create_server(port)
    actual_port = server.server_address[1]
    print(f"Ковадло — модуль 3 (візуалізація) запущено: http://127.0.0.1:{actual_port}/")
    print("Зупинити: Ctrl+C")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    port_arg = int(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_PORT
    run(port_arg)
