"""Тести руху деталей у часі: Transform, Linear, Rotation, Geared, Composite, MotionPlan."""

import math

import pytest

from kovadlo.geometry3d import Point3
from kovadlo.motion import (
    Composite,
    Geared,
    Linear,
    MotionPlan,
    Rotation,
    Transform,
    exploded_view_motion_plan,
)
from kovadlo.transmission import Gear, GearMesh


def _distance(a: Point3, b: Point3) -> float:
    return math.sqrt((a.x - b.x) ** 2 + (a.y - b.y) ** 2 + (a.z - b.z) ** 2)


# ---------------------------------------------------------------- Transform

def test_transform_identity_is_noop():
    p = Point3(10, 20, 30)
    assert Transform.identity().apply(p) == p


def test_transform_translation_by():
    p = Point3(0, 0, 0)
    moved = Transform.translation_by((10, 0, 5)).apply(p)
    assert (moved.x, moved.y, moved.z) == pytest.approx((10, 0, 5))


def test_transform_rotation_about_keeps_origin_fixed():
    origin = Point3(100, 0, 50)
    t = Transform.rotation_about((0, 1, 0), origin, 90)
    result = t.apply(origin)
    assert (result.x, result.y, result.z) == pytest.approx((origin.x, origin.y, origin.z))


def test_transform_rotation_about_y_axis_90deg_hand_verified():
    # Поворот навколо Y (через початок координат) на 90°: (1,0,0) -> (0,0,-1)
    # (права система координат, за формулою Родріга з x=(1,0,0), k=(0,1,0)).
    t = Transform.rotation_about((0, 1, 0), Point3(0, 0, 0), 90)
    result = t.apply(Point3(1, 0, 0))
    assert (result.x, result.y, result.z) == pytest.approx((0, 0, -1), abs=1e-9)


def test_transform_then_order_translate_then_rotate_differs_from_reverse():
    translate = Transform.translation_by((10, 0, 0))
    rotate = Transform.rotation_about((0, 1, 0), Point3(0, 0, 0), 90)
    p = Point3(1, 0, 0)

    translate_then_rotate = translate.then(rotate).apply(p)
    rotate_then_translate = rotate.then(translate).apply(p)

    assert _distance(translate_then_rotate, rotate_then_translate) > 1.0


def test_transform_then_matches_manual_apply_order():
    translate = Transform.translation_by((5, 0, 0))
    rotate = Transform.rotation_about((0, 1, 0), Point3(0, 0, 0), 45)
    p = Point3(2, 3, 4)

    combined = translate.then(rotate).apply(p)
    manual = rotate.apply(translate.apply(p))
    assert (combined.x, combined.y, combined.z) == pytest.approx((manual.x, manual.y, manual.z))


# -------------------------------------------------------------------- Linear

def test_linear_moves_uniformly_along_axis():
    motion = Linear(axis=(1, 0, 0), distance=100, duration=10)
    p = Point3(0, 0, 0)
    assert motion.at(5).apply(p).x == pytest.approx(50)
    assert motion.at(10).apply(p).x == pytest.approx(100)


def test_linear_normalizes_axis():
    motion = Linear(axis=(2, 0, 0), distance=100, duration=10)
    assert motion.at(10).apply(Point3(0, 0, 0)).x == pytest.approx(100)


def test_linear_clamps_before_start():
    motion = Linear(axis=(1, 0, 0), distance=100, duration=10)
    assert motion.at(-5).apply(Point3(0, 0, 0)).x == pytest.approx(0)


def test_linear_clamps_after_duration_stays_put():
    # Розліт деталей: після завершення (duration) деталь лишається на
    # кінцевій відстані, а не продовжує летіти.
    motion = Linear(axis=(1, 0, 0), distance=100, duration=10)
    assert motion.at(10).apply(Point3(0, 0, 0)).x == pytest.approx(100)
    assert motion.at(1000).apply(Point3(0, 0, 0)).x == pytest.approx(100)


def test_linear_rejects_non_positive_duration():
    with pytest.raises(ValueError):
        Linear(axis=(1, 0, 0), distance=100, duration=0)


# ------------------------------------------------------------------ Rotation

def test_rotation_full_turn_returns_to_start():
    rpm = 30.0
    period_s = 60.0 / rpm
    motion = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=rpm)
    p = Point3(100, 0, 0)

    result = motion.at(period_s).apply(p)
    assert (result.x, result.y, result.z) == pytest.approx((p.x, p.y, p.z), abs=1e-6)


def test_rotation_quarter_turn_angle():
    rpm = 15.0  # 90°/с
    motion = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=rpm)
    assert motion.angle_deg(1.0) == pytest.approx(90.0)


# -------------------------------------------------------------------- Geared

def test_geared_doubles_angle():
    parent = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=10.0)
    geared = Geared(parent=parent, ratio=2.0)
    assert geared.angle_deg(1.0) == pytest.approx(2 * parent.angle_deg(1.0))


def test_geared_negative_ratio_reverses_direction():
    parent = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=10.0)
    geared = Geared(parent=parent, ratio=-1.0)
    assert geared.angle_deg(1.0) == pytest.approx(-parent.angle_deg(1.0))


def test_geared_inherits_axis_and_origin_from_parent():
    origin = Point3(10, 0, 5)
    parent = Rotation(axis=(0, 1, 0), origin=origin, rpm=10.0)
    geared = Geared(parent=parent, ratio=3.0)
    assert geared.axis == parent.axis
    assert geared.origin == origin


def test_geared_chains_through_another_geared():
    parent = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=10.0)
    first_stage = Geared(parent=parent, ratio=2.0)
    second_stage = Geared(parent=first_stage, ratio=5.0)
    assert second_stage.angle_deg(1.0) == pytest.approx(10 * parent.angle_deg(1.0))


def test_geared_rejects_non_rotational_parent():
    linear = Linear(axis=(1, 0, 0), distance=100, duration=10)
    with pytest.raises(TypeError):
        Geared(parent=linear, ratio=2.0)


# ------------------------------------------------------------ Geared.from_mesh

def test_geared_from_mesh_ratio_hand_verified():
    # z_a=20, z_b=40 -> mesh.ratio=2.0 -> Geared.ratio = -1/2 = -0.5
    mesh = GearMesh(Gear(module_mm=8, teeth=20, width_mm=10), Gear(module_mm=8, teeth=40, width_mm=10))
    parent = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=20.0)
    geared = Geared.from_mesh(parent, mesh)
    assert geared.ratio == pytest.approx(-0.5)


def test_geared_from_mesh_matches_gear_mesh_output_rpm():
    mesh = GearMesh(Gear(module_mm=8, teeth=20, width_mm=10), Gear(module_mm=8, teeth=40, width_mm=10))
    parent_rpm = 20.0
    parent = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=parent_rpm)
    geared = Geared.from_mesh(parent, mesh)

    # "еквівалентні оберти" geared, виведені з кута (град/с / 6 = об/хв),
    # мають збігатися з GearMesh.output_rpm — та сама фізика зачеплення.
    geared_equivalent_rpm = geared.angle_deg(1.0) / 6.0
    assert geared_equivalent_rpm == pytest.approx(mesh.output_rpm(parent_rpm))


def test_geared_from_mesh_defaults_to_coaxial_with_parent():
    mesh = GearMesh(Gear(module_mm=8, teeth=20, width_mm=10), Gear(module_mm=8, teeth=40, width_mm=10))
    origin = Point3(10, 0, 5)
    parent = Rotation(axis=(0, 1, 0), origin=origin, rpm=20.0)
    geared = Geared.from_mesh(parent, mesh)
    assert geared.origin == origin
    assert geared.axis == parent.axis


def test_geared_from_mesh_accepts_own_origin_for_non_coaxial_gear():
    mesh = GearMesh(Gear(module_mm=8, teeth=20, width_mm=10), Gear(module_mm=8, teeth=40, width_mm=10))
    parent = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=20.0)
    own_origin = Point3(mesh.center_distance_mm, 0, 0)
    geared = Geared.from_mesh(parent, mesh, origin=own_origin)
    assert geared.origin == own_origin
    assert geared.axis == parent.axis  # паралельні вали — той самий напрям осі


def test_geared_from_mesh_equals_manual_ratio_construction():
    mesh = GearMesh(Gear(module_mm=8, teeth=20, width_mm=10), Gear(module_mm=8, teeth=40, width_mm=10))
    parent = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=20.0)
    via_mesh = Geared.from_mesh(parent, mesh)
    via_manual = Geared(parent=parent, ratio=-1.0 / mesh.ratio)
    assert via_mesh.angle_deg(1.0) == pytest.approx(via_manual.angle_deg(1.0))


# ----------------------------------------------------------------- Composite

def test_composite_order_matters():
    translate = Linear(axis=(1, 0, 0), distance=10, duration=1)
    rotate = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=15.0)  # 90°/с
    p = Point3(1, 0, 0)

    translate_then_rotate = Composite([translate, rotate]).at(1.0).apply(p)
    rotate_then_translate = Composite([rotate, translate]).at(1.0).apply(p)

    assert _distance(translate_then_rotate, rotate_then_translate) > 1.0


def test_composite_matches_sequential_manual_apply():
    translate = Linear(axis=(1, 0, 0), distance=10, duration=1)
    rotate = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=15.0)
    p = Point3(1, 0, 0)

    combined = Composite([translate, rotate]).at(1.0).apply(p)
    manual = rotate.at(1.0).apply(translate.at(1.0).apply(p))
    assert (combined.x, combined.y, combined.z) == pytest.approx((manual.x, manual.y, manual.z))


def test_composite_of_one_motion_matches_that_motion():
    rotate = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=15.0)
    p = Point3(1, 0, 0)
    combined = Composite([rotate]).at(1.0).apply(p)
    direct = rotate.at(1.0).apply(p)
    assert (combined.x, combined.y, combined.z) == pytest.approx((direct.x, direct.y, direct.z))


# --------------------------------------------------------------- MotionPlan

def test_motion_plan_state_at_returns_all_parts():
    wheel = Rotation(axis=(0, 1, 0), origin=Point3(0, 0, 0), rpm=30.0)
    fragment = Linear(axis=(1, 0, 0), distance=500, duration=2)
    plan = MotionPlan(motions={"wheel": wheel, "fragment": fragment})

    state = plan.state_at(1.0)

    assert set(state.keys()) == {"wheel", "fragment"}
    wheel_result = state["wheel"].apply(Point3(0, 0, 0))
    assert (wheel_result.x, wheel_result.y, wheel_result.z) == pytest.approx((0, 0, 0))
    assert state["fragment"].apply(Point3(0, 0, 0)).x == pytest.approx(250)


# ------------------------------------------------------- exploded_view_motion_plan

def test_exploded_view_first_layer_never_moves():
    plan = exploded_view_motion_plan(
        [("Тиньк", 15.0), ("Цегла", 250.0), ("Утеплювач", 100.0)],
        direction=(1, 0, 0),
        gap_mm=50.0,
    )
    first = plan.motions["0:Тиньк"]
    assert first.at(0.0).translation == pytest.approx((0, 0, 0))
    assert first.at(first.duration).translation == pytest.approx((0, 0, 0))


def test_exploded_view_uniform_gap_regardless_of_layer_thickness():
    # Товщини навмисно дуже різні (100 / 500 / 100) — перевіряємо, що
    # проміжок між сусідами в розібраному стані все одно рівно gap_mm.
    layers = [("A", 100.0), ("B", 500.0), ("C", 100.0)]
    gap_mm = 50.0
    plan = exploded_view_motion_plan(layers, direction=(1, 0, 0), gap_mm=gap_mm, duration=2.0)

    # зібрані (t=0) ліві межі шарів, з кумулятивних товщин
    assembled_left_edge = [0.0, 100.0, 600.0]
    thickness = [100.0, 500.0, 100.0]

    exploded_left_edge = []
    for i, (name, _) in enumerate(layers):
        displacement = plan.motions[f"{i}:{name}"].at(2.0).translation[0]
        exploded_left_edge.append(assembled_left_edge[i] + displacement)

    for i in range(len(layers) - 1):
        gap = exploded_left_edge[i + 1] - (exploded_left_edge[i] + thickness[i])
        assert gap == pytest.approx(gap_mm)


def test_exploded_view_duplicate_names_get_distinct_index_prefixed_keys():
    plan = exploded_view_motion_plan(
        [("Цегла", 120.0), ("Утеплювач", 100.0), ("Цегла", 120.0)],
        direction=(0, 0, 1),
        gap_mm=40.0,
    )
    assert set(plan.motions.keys()) == {"0:Цегла", "1:Утеплювач", "2:Цегла"}
    assert plan.motions["0:Цегла"].at(1.0).translation != plan.motions["2:Цегла"].at(1.0).translation


def test_exploded_view_rejects_empty_layers():
    with pytest.raises(ValueError):
        exploded_view_motion_plan([], direction=(1, 0, 0), gap_mm=50.0)


def test_exploded_view_rejects_non_positive_thickness():
    with pytest.raises(ValueError):
        exploded_view_motion_plan([("A", 0.0)], direction=(1, 0, 0), gap_mm=50.0)


def test_exploded_view_rejects_negative_gap():
    with pytest.raises(ValueError):
        exploded_view_motion_plan([("A", 10.0), ("B", 10.0)], direction=(1, 0, 0), gap_mm=-5.0)
