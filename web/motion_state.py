"""
Демонстраційний стенд руху для незалежного режиму «Механізми»: дві
зчеплені шестерні (`Rotation` + `Geared.from_mesh`) і деталь, що
відлітає й зупиняється (`Linear`) — доказ, що `kovadlo/motion.py`
підключений до веб-шару. Ядро руху не змінене, тут лише позиціонування
у власних (не прив'язаних до кімнати) координатах і серіалізація в
JSON для three.js. Стенд НЕ залежить від `Room` — режим «Механізми» не
має ні кімнати, ні стін, ні підлоги, лише сам механізм.

Стенд навмисно не вдає, що реальні деталі будівлі (двері, вентилятор
повітроводу) фізично рухаються — такої геометрії (стулка, лопаті) в
модулі 10 ще нема. Це чесно позначений навчальний приклад, той самий
підхід, що й у `examples/*_demo.py`.

Координати деталей рахуються в мм (система ядра — модуль 10, `Point3`).
Матриці для three.js конвертуються тут-таки: мм -> м, без дзеркалення
осей (та сама пряма конвенція `x/1000, y/1000, z/1000`, що й уся інша
геометрія 3D-вкладки в `static/index.html` — стіни/повітроводи/траси/
світильники; дзеркалить Z лише `buildFloorMesh`, і то як локальна
компенсація власного `rotateX(-90°)`, а не конвенція сцени).

Другий сценарій цього модуля — розліт (exploded view) шарів обраної
стіни (`kovadlo.exploded_view_motion_plan`): дані про шари бере з
`HeatState.wall_layers` (вкладка «Тепло», модуль 9.4) веб-шару, нормаль
стіни рахує сам (той самий прийом вибору "назовні", що й
`place_detectors_along_contour` у `kovadlo/fire_safety.py`).
"""

from __future__ import annotations

import math
from typing import Any

from kovadlo.geometry3d import Point3
from kovadlo.motion import Geared, Linear, Motion, MotionPlan, Rotation, Transform, exploded_view_motion_plan
from kovadlo.transmission import Gear, GearMesh

Vector3 = tuple[float, float, float]

_MM_TO_M = 0.001

# Реальна зубчаста пара (kovadlo.transmission): радіуси на сцені беруться
# з pitch_diameter_mm цих коліс, а не з довільних констант "для наочності".
_GEAR_MODULE_MM = 8.0
_GEAR_THICKNESS_MM = 20.0  # ширина вінця (демо-значення — GearMesh її не використовує)
_GEAR_A = Gear(module_mm=_GEAR_MODULE_MM, teeth=20, width_mm=_GEAR_THICKNESS_MM)
_GEAR_B = Gear(module_mm=_GEAR_MODULE_MM, teeth=40, width_mm=_GEAR_THICKNESS_MM)
_GEAR_MESH = GearMesh(_GEAR_A, _GEAR_B)
_GEAR_A_RPM = 20.0

# Власні координати стенду — режим «Механізми» не має кімнати, тож
# нема відносно чого позиціонувати: просто фіксована точка опори.
_RIG_BASE = Point3(0.0, 200.0, 0.0)

_FRAGMENT_SIZE_MM = 100.0
_FRAGMENT_TRAVEL_MM = 500.0
_FRAGMENT_DURATION_S = 3.0
_FRAGMENT_OFFSET_Z_MM = 400.0   # зсув стартової точки уламка від осі шестерень

_WALL_EXPLOSION_GAP_MM = 300.0
_WALL_EXPLOSION_DURATION_S = 2.0


def _rig_origins() -> dict[str, Point3]:
    """Точки опори деталей стенду — власні координати, не прив'язані до
    жодної кімнати (режим «Механізми» кімнати не має взагалі).

    Для шестерень це водночас вісь обертання (`Rotation.origin`/
    `Geared.own_origin`) і точка, у якій центрована їхня геометрія на
    клієнті; для деталі, що відлітає, — лише стартова точка геометрії
    (`Linear` осі опори не має).

    `gear_b` рознесена від `gear_a` на `GearMesh.center_distance_mm`
    уздовж X, на тій самій висоті Y і Z — так реально стоять два
    циліндричні колеса в зовнішньому зачепленні (паралельні вали,
    відстань між осями = напівсума ділильних діаметрів). Обертання
    `gear_b` все одно навколо ЇЇ ВЛАСНОЇ осі (`Geared.from_mesh(...,
    origin=...)` нижче), а не навколо `gear_a` — інакше вона летіла б
    по колу навколо чужої осі замість обертання на місці.
    """
    base = _RIG_BASE
    return {
        "gear_a": base,
        "gear_b": Point3(base.x + _GEAR_MESH.center_distance_mm, base.y, base.z),
        "fragment": Point3(base.x, base.y, base.z + _FRAGMENT_OFFSET_Z_MM),
    }


def build_demo_motion_plan() -> MotionPlan:
    """Демо-план: `gear_a` (Rotation) веде `gear_b` (Geared.from_mesh —
    передатне число з реального зачеплення `_GEAR_MESH`), `fragment`
    відлітає (Linear). Незалежний від кімнати — режим «Механізми»."""
    origins = _rig_origins()
    gear_a = Rotation(axis=(0, 1, 0), origin=origins["gear_a"], rpm=_GEAR_A_RPM)
    gear_b = Geared.from_mesh(gear_a, _GEAR_MESH, origin=origins["gear_b"])
    fragment = Linear(axis=(0, 0, 1), distance=_FRAGMENT_TRAVEL_MM, duration=_FRAGMENT_DURATION_S)
    return MotionPlan(motions={"gear_a": gear_a, "gear_b": gear_b, "fragment": fragment})


def demo_motion_rig_layout() -> list[dict]:
    """Статичний (t=0) опис деталей стенду — геометрія для побудови на
    клієнті. Радіуси коліс — з `Gear.pitch_diameter_mm`, не з констант."""
    origins = _rig_origins()
    return [
        {
            "name": "gear_a",
            "kind": "gear",
            "position_mm": [origins["gear_a"].x, origins["gear_a"].y, origins["gear_a"].z],
            "radius_mm": _GEAR_A.pitch_diameter_mm / 2.0,
            "thickness_mm": _GEAR_A.width_mm,
            "color": "#c9a24b",
        },
        {
            "name": "gear_b",
            "kind": "gear",
            "position_mm": [origins["gear_b"].x, origins["gear_b"].y, origins["gear_b"].z],
            "radius_mm": _GEAR_B.pitch_diameter_mm / 2.0,
            "thickness_mm": _GEAR_B.width_mm,
            "color": "#8fa8c9",
        },
        {
            "name": "fragment",
            "kind": "fragment",
            "position_mm": [origins["fragment"].x, origins["fragment"].y, origins["fragment"].z],
            "size_mm": _FRAGMENT_SIZE_MM,
            "color": "#c96b4b",
        },
    ]


def _to_three_matrix(transform: Transform) -> list[float]:
    """`Transform` (мм, координати ядра) -> плоска row-major 4x4-матриця
    three.js (`THREE.Matrix4.set(...)`), у метрах.

    Без дзеркалення осей: у `static/index.html` лише `buildFloorMesh`
    негує Z, і то як локальна компенсація власного `rotateX(-90°)` для
    контуру підлоги — стіни, повітроводи, траси й світильники кладуть
    `x/1000, y/1000, z/1000` напряму. Той самий прямий переказ тут.
    """
    r, t = transform.rotation, transform.translation
    flat: list[float] = []
    for i in range(3):
        flat.extend(r[i])
        flat.append(t[i] * _MM_TO_M)
    flat.extend([0.0, 0.0, 0.0, 1.0])
    return flat


def serialize_motion_state(plan: MotionPlan, ts: list[float]) -> dict:
    """Стан усіх деталей плану в кожен момент з `ts`, однією пачкою кадрів."""
    frames = []
    for t in ts:
        transforms = plan.state_at(t)
        frames.append(
            {
                "t": t,
                "parts": {name: {"matrix": _to_three_matrix(transform)} for name, transform in transforms.items()},
            }
        )
    return {"frames": frames}


def merge_motion_plans(*plans: MotionPlan) -> MotionPlan:
    """Об'єднує кілька `MotionPlan` в один — демо-стенд і розліт стіни
    рухаються тим самим повзунком часу, тож `/api/motion/state` рахує
    для них ОДИН план, а не окремі запити. Ключі деталей з різних
    планів не мають перетинатись (стенд: "gear_a"/"gear_b"/"fragment",
    шари стіни: "{індекс}:{ім'я}") — якщо все ж перетнулись, це
    помилка конфігурації, а не тихе затирання деталі."""
    merged: dict[str, Motion] = {}
    for plan in plans:
        for name, motion in plan.motions.items():
            if name in merged:
                raise ValueError(f"Колізія імені деталі в MotionPlan: «{name}»")
            merged[name] = motion
    return MotionPlan(motions=merged)


def _wall_outward_normal(room: Any, wall: Any) -> Vector3:
    """Нормаль стіни, що вказує НАЗОВНІ (від центроїда контуру кімнати).

    Той самий прийом, що й `place_detectors_along_contour`
    (`kovadlo/fire_safety.py`: перпендикуляр до ребра + звірка знаку
    через скалярний добуток з напрямком на центроїд) — лише знак
    навпаки: там обирають нормаль ВСЕРЕДИНУ контуру, тут — назовні,
    бо шари стіни при розльоті йдуть від внутрішньої поверхні на
    вулицю, а не в кімнату.
    """
    contour = room.contour
    centroid_x = sum(p.x for p in contour) / len(contour)
    centroid_z = sum(p.z for p in contour) / len(contour)

    dx = wall.end.x - wall.start.x
    dz = wall.end.z - wall.start.z
    length = math.hypot(dx, dz) or 1.0
    nx, nz = -dz / length, dx / length

    mid_x = (wall.start.x + wall.end.x) / 2.0
    mid_z = (wall.start.z + wall.end.z) / 2.0
    to_centroid_x, to_centroid_z = centroid_x - mid_x, centroid_z - mid_z
    if nx * to_centroid_x + nz * to_centroid_z > 0:
        nx, nz = -nx, -nz  # це вказувало б усередину контуру — розліт має йти назовні
    return (nx, 0.0, nz)


def wall_explosion_layout(room: Any, wall_index: int, wall_layers_mm: list[tuple[str, float]]) -> dict:
    """Статичний (t=0, зібраний) опис шарів обраної стіни для побудови
    геометрії на клієнті: коробка на всю довжину/висоту стіни, зі своєю
    товщиною, зсунута від осьової лінії стіни на кумулятивну відстань —
    той самий підхід (довжина/висота/кут стіни), що й `buildWallMesh`
    в `index.html`, лише по одному шару замість усієї товщини стіни.

    `wall_layers_mm` — `(ім'я, товщина_мм)` від внутрішньої поверхні
    стіни до зовнішньої (та сама форма й порядок, що й
    `HeatState.wall_layers`, лише товщина тут у мм)."""
    wall = room.walls[wall_index]
    nx, _, nz = _wall_outward_normal(room, wall)
    angle_deg = math.degrees(math.atan2(wall.end.z - wall.start.z, wall.end.x - wall.start.x))
    mid_x = (wall.start.x + wall.end.x) / 2.0
    mid_z = (wall.start.z + wall.end.z) / 2.0

    # пакет шарів центрований на осьовій лінії стіни — так само, як
    # товщина стіни модуля 1 ділиться порівну по обидва боки від неї.
    total_thickness_mm = sum(thickness_mm for _, thickness_mm in wall_layers_mm)
    cumulative_mm = -total_thickness_mm / 2.0

    layers = []
    for i, (name, thickness_mm) in enumerate(wall_layers_mm):
        center_offset_mm = cumulative_mm + thickness_mm / 2.0
        layers.append(
            {
                # той самий ключ, що будує exploded_view_motion_plan
                # (kovadlo/motion.py) — щоб зіставити цей шар з його
                # трансформацією з /api/motion/state.
                "motion_name": f"{i}:{name}",
                "name": name,
                "thickness_mm": thickness_mm,
                "position_mm": [mid_x + nx * center_offset_mm, wall.height / 2.0, mid_z + nz * center_offset_mm],
                "length_mm": wall.length_mm,
                "height_mm": wall.height,
                "angle_deg": angle_deg,
            }
        )
        cumulative_mm += thickness_mm

    return {"wall_index": wall_index, "direction": [nx, 0.0, nz], "layers": layers}


def build_wall_explosion_plan(
    room: Any,
    wall_index: int,
    wall_layers_mm: list[tuple[str, float]],
    *,
    gap_mm: float = _WALL_EXPLOSION_GAP_MM,
    duration: float = _WALL_EXPLOSION_DURATION_S,
) -> MotionPlan:
    """`MotionPlan` розльоту шарів обраної стіни — тонка обгортка навколо
    `kovadlo.exploded_view_motion_plan` з нормаллю саме цієї стіни."""
    direction = _wall_outward_normal(room, room.walls[wall_index])
    return exploded_view_motion_plan(wall_layers_mm, direction=direction, gap_mm=gap_mm, duration=duration)


def wall_layers_mm_from_heat_state(raw_layers_m: list[tuple[str, float]]) -> list[tuple[str, float]]:
    """Конвертує шари з `HeatState.wall_layers` (`web/server.py`, товщина
    в метрах) у мм — форму, яку приймають `wall_explosion_layout` і
    `build_wall_explosion_plan`."""
    return [(name, thickness_m * 1000.0) for name, thickness_m in raw_layers_m]
