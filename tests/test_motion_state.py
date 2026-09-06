"""Тести демонстраційного стенду руху (режим «Механізми») і розльоту
шарів стіни (режим «Будівництво») — web/motion_state.py."""

import pytest

from kovadlo import Material, Point, Room
from web.motion_state import (
    _GEAR_A,
    _GEAR_B,
    _GEAR_MESH,
    _to_three_matrix,
    _wall_outward_normal,
    build_demo_motion_plan,
    build_wall_explosion_plan,
    demo_motion_rig_layout,
    merge_motion_plans,
    serialize_motion_state,
    wall_explosion_layout,
)

CONCRETE = Material(name="Бетон C25/30", density_kg_m3=2400)


def _make_room() -> Room:
    contour = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
    return Room.from_contour(contour, height=2700, thickness=200, material=CONCRETE, name="Кухня")


# ------------------------------------------------------------------ layout

def test_layout_has_three_named_parts_with_expected_kinds():
    layout = demo_motion_rig_layout()
    kinds = {part["name"]: part["kind"] for part in layout}
    assert kinds == {"gear_a": "gear", "gear_b": "gear", "fragment": "fragment"}


def test_layout_gear_radii_come_from_pitch_diameter():
    layout = demo_motion_rig_layout()
    by_name = {part["name"]: part for part in layout}
    assert by_name["gear_a"]["radius_mm"] == pytest.approx(_GEAR_A.pitch_diameter_mm / 2.0)
    assert by_name["gear_b"]["radius_mm"] == pytest.approx(_GEAR_B.pitch_diameter_mm / 2.0)


def test_layout_gear_b_offset_by_center_distance():
    layout = demo_motion_rig_layout()
    by_name = {part["name"]: part for part in layout}
    dx = by_name["gear_b"]["position_mm"][0] - by_name["gear_a"]["position_mm"][0]
    assert dx == pytest.approx(_GEAR_MESH.center_distance_mm)


# -------------------------------------------------------------- motion plan
# Стенд — режим «Механізми»: незалежний від кімнати (кімнати нема взагалі).

def test_plan_has_same_part_names_as_layout():
    plan = build_demo_motion_plan()
    layout_names = {part["name"] for part in demo_motion_rig_layout()}
    assert set(plan.motions.keys()) == layout_names


def test_gear_b_geared_to_gear_a_via_real_gear_mesh_ratio():
    plan = build_demo_motion_plan()
    gear_a, gear_b = plan.motions["gear_a"], plan.motions["gear_b"]
    # z_a=20, z_b=40 -> Geared.ratio = -1/mesh.ratio = -20/40 = -0.5
    assert gear_b.angle_deg(1.0) == pytest.approx(-0.5 * gear_a.angle_deg(1.0))


def test_gear_b_axis_offset_from_gear_a_by_center_distance():
    plan = build_demo_motion_plan()
    gear_a, gear_b = plan.motions["gear_a"], plan.motions["gear_b"]
    # осі рознесені на міжосьову відстань уздовж X, не коаксіально
    assert gear_b.origin.x - gear_a.origin.x == pytest.approx(_GEAR_MESH.center_distance_mm)
    assert gear_b.origin.y == pytest.approx(gear_a.origin.y)
    assert gear_b.origin.z == pytest.approx(gear_a.origin.z)
    assert gear_b.axis == gear_a.axis


def test_gear_centers_stay_fixed_while_rotating():
    """Регресія: центр кожного колеса — нерухома точка обертання, а не
    точка, що кружляє по колу. Перевіряємо ПОЛОЖЕННЯ (Transform.apply
    до власного центру), а не кут — саме тут раніше проявився б баг
    "поворот навколо чужої осі" (gear_b орбітувала б довкола gear_a,
    якби її origin не був її власним, рознесеним на center_distance_mm)."""
    plan = build_demo_motion_plan()
    gear_a, gear_b = plan.motions["gear_a"], plan.motions["gear_b"]

    center_a0 = gear_a.at(0.0).apply(gear_a.origin)
    center_b0 = gear_b.at(0.0).apply(gear_b.origin)

    for t in (1.0, 5.0):
        center_a = gear_a.at(t).apply(gear_a.origin)
        center_b = gear_b.at(t).apply(gear_b.origin)
        assert (center_a.x, center_a.y, center_a.z) == pytest.approx(
            (center_a0.x, center_a0.y, center_a0.z), abs=1e-6
        )
        assert (center_b.x, center_b.y, center_b.z) == pytest.approx(
            (center_b0.x, center_b0.y, center_b0.z), abs=1e-6
        )


def test_fragment_stops_after_its_duration():
    plan = build_demo_motion_plan()
    fragment = plan.motions["fragment"]
    far_future = fragment.at(1000.0)
    at_duration = fragment.at(fragment.duration)
    assert far_future.translation == pytest.approx(at_duration.translation)


# ---------------------------------------------------------- _to_three_matrix

def test_to_three_matrix_identity_transform():
    from kovadlo.motion import Transform

    flat = _to_three_matrix(Transform.identity())
    assert flat == pytest.approx([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])


def test_to_three_matrix_converts_mm_to_m_no_axis_mirroring():
    from kovadlo.motion import Transform

    flat = _to_three_matrix(Transform.translation_by((1000.0, 2000.0, 3000.0)))
    # рядок 0: [1,0,0, tx=1000мм->1м]; рядок 1: [0,1,0, ty=2000мм->2м];
    # рядок 2: [0,0,1, tz=3000мм->3м] — жодна вісь не дзеркалиться (та сама
    # конвенція, що й buildWallMesh/buildDuctMesh в index.html).
    assert flat[3] == pytest.approx(1.0)
    assert flat[7] == pytest.approx(2.0)
    assert flat[11] == pytest.approx(3.0)


def test_to_three_matrix_keeps_rotation_sign_around_y():
    from kovadlo.geometry3d import Point3
    from kovadlo.motion import Transform

    transform = Transform.rotation_about((0, 1, 0), Point3(0, 0, 0), 90)
    flat = _to_three_matrix(transform)
    # 90° навколо Y у координатах ядра: (1,0,0)->(0,0,-1), елемент R[2][0]=-sin(90)=-1;
    # без дзеркалення осей знак не міняється.
    assert flat[8] == pytest.approx(-1.0, abs=1e-9)  # рядок 2, стовпець 0


# ------------------------------------------------------------- serialization

def test_serialize_motion_state_one_frame_per_t():
    plan = build_demo_motion_plan()
    result = serialize_motion_state(plan, [0.0, 1.0, 2.5])
    frames = result["frames"]
    assert [f["t"] for f in frames] == [0.0, 1.0, 2.5]
    assert set(frames[0]["parts"].keys()) == {"gear_a", "gear_b", "fragment"}
    for part in frames[0]["parts"].values():
        assert len(part["matrix"]) == 16


def test_serialize_motion_state_at_zero_is_identity_for_every_part():
    plan = build_demo_motion_plan()
    frame = serialize_motion_state(plan, [0.0])["frames"][0]
    identity = [1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1]
    for part in frame["parts"].values():
        assert part["matrix"] == pytest.approx(identity, abs=1e-9)


def _apply_serialized_matrix(matrix: list[float], point_mm: list[float]) -> tuple[float, float, float]:
    """Застосовує серіалізовану row-major 4x4-матрицю (метри) до точки
    (мм, конвертованої в метри) — той самий розрахунок, що робить
    three.js на клієнті (`group.matrix.set(...)` + вершина в (0,0,0)
    локальних координат, запечена в `position_mm`)."""
    x_m, y_m, z_m = (v / 1000.0 for v in point_mm)
    x = matrix[0] * x_m + matrix[1] * y_m + matrix[2] * z_m + matrix[3]
    y = matrix[4] * x_m + matrix[5] * y_m + matrix[6] * z_m + matrix[7]
    z = matrix[8] * x_m + matrix[9] * y_m + matrix[10] * z_m + matrix[11]
    return (x, y, z)


def test_serialized_gear_centers_stay_fixed_at_various_times():
    """Той самий регресійний тест на положення (не кут), але через увесь
    шлях серіалізації — рахує так, як це робив би клієнт із матрицею
    з /api/mechanism/state, застосованою до запеченої (position_mm)
    вершини в центрі колеса."""
    plan = build_demo_motion_plan()
    layout = {part["name"]: part for part in demo_motion_rig_layout()}

    result = serialize_motion_state(plan, [0.0, 1.0, 5.0, 7.4, 8.7, 9.7])
    for name in ("gear_a", "gear_b"):
        rest_position_mm = layout[name]["position_mm"]
        centers = [
            _apply_serialized_matrix(frame["parts"][name]["matrix"], rest_position_mm)
            for frame in result["frames"]
        ]
        first = centers[0]
        for center in centers[1:]:
            assert center == pytest.approx(first, abs=1e-6)


# --------------------------------------------------------- wall explosion
# Розліт шарів стіни — режим «Будівництво»: прив'язаний до кімнати/стіни.

WALL_LAYERS_MM = [("Тиньк", 15.0), ("Цегла", 250.0), ("Утеплювач", 100.0), ("Штукатурка", 20.0)]


def test_wall_outward_normal_points_away_from_room_for_south_wall():
    room = _make_room()
    normal = _wall_outward_normal(room, room.walls[0])  # (0,0)->(4000,0), кімната вище (z>0)
    assert normal == pytest.approx((0.0, 0.0, -1.0))


def test_wall_outward_normal_points_away_from_room_for_east_wall():
    room = _make_room()
    normal = _wall_outward_normal(room, room.walls[1])  # (4000,0)->(4000,3000), кімната лівіше (x<4000)
    assert normal == pytest.approx((1.0, 0.0, 0.0))


def test_wall_explosion_layout_motion_names_match_plan_keys():
    room = _make_room()
    layout = wall_explosion_layout(room, 0, WALL_LAYERS_MM)
    plan = build_wall_explosion_plan(room, 0, WALL_LAYERS_MM)
    assert {layer["motion_name"] for layer in layout["layers"]} == set(plan.motions.keys())


def test_wall_explosion_layout_layers_centered_on_wall_axis():
    room = _make_room()
    layout = wall_explosion_layout(room, 0, WALL_LAYERS_MM)
    total = sum(t for _, t in WALL_LAYERS_MM)
    first_z = layout["layers"][0]["position_mm"][2]
    last_z = layout["layers"][-1]["position_mm"][2]
    # нормаль стіни 0 — (0,0,-1) (назовні = у -Z), тож зсув уздовж напрямку
    # (від'ємний для першого шару, додатний для останнього) дає ПРОТИЛЕЖНИЙ
    # знак у світовому Z: перший шар — на +Z (углиб кімнати), останній — на -Z.
    assert first_z == pytest.approx(total / 2 - WALL_LAYERS_MM[0][1] / 2)
    assert last_z == pytest.approx(-(total / 2 - WALL_LAYERS_MM[-1][1] / 2))


def test_wall_explosion_layout_layer_dimensions_match_wall():
    room = _make_room()
    layout = wall_explosion_layout(room, 0, WALL_LAYERS_MM)
    wall = room.walls[0]
    for layer in layout["layers"]:
        assert layer["length_mm"] == pytest.approx(wall.length_mm)
        assert layer["height_mm"] == pytest.approx(wall.height)


def test_build_wall_explosion_plan_first_layer_stays_fixed():
    room = _make_room()
    plan = build_wall_explosion_plan(room, 0, WALL_LAYERS_MM, gap_mm=50.0)
    first = plan.motions["0:Тиньк"]
    assert first.at(first.duration).translation == pytest.approx((0, 0, 0))


def test_build_wall_explosion_plan_moves_outward_by_index_times_gap():
    room = _make_room()
    plan = build_wall_explosion_plan(room, 0, WALL_LAYERS_MM, gap_mm=50.0)
    last = plan.motions["3:Штукатурка"]  # індекс 3, назовні для стіни 0 — це -Z
    dz_mm = last.at(last.duration).translation[2]
    assert dz_mm == pytest.approx(-3 * 50.0)


def test_merge_motion_plans_combines_all_parts():
    room = _make_room()
    rig = build_demo_motion_plan()
    wall = build_wall_explosion_plan(room, 0, WALL_LAYERS_MM)
    merged = merge_motion_plans(rig, wall)
    assert set(merged.motions.keys()) == set(rig.motions.keys()) | set(wall.motions.keys())


def test_merge_motion_plans_with_no_plans_is_empty():
    assert merge_motion_plans().motions == {}


def test_merge_motion_plans_raises_on_key_collision():
    from kovadlo.motion import Linear, MotionPlan

    a = MotionPlan(motions={"x": Linear(axis=(1, 0, 0), distance=10, duration=1)})
    b = MotionPlan(motions={"x": Linear(axis=(0, 1, 0), distance=10, duration=1)})
    with pytest.raises(ValueError):
        merge_motion_plans(a, b)
