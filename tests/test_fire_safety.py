import math

import pytest

from kovadlo.fire_safety import (
    FireDetector,
    auto_place_detectors,
    detectors_needed,
    loop_length_m,
    place_detectors_along_contour,
)
from kovadlo.fire_safety_norms import DetectorKind
from kovadlo.geometry import Point
from kovadlo.materials import Material
from kovadlo.room import Room


def test_detectors_needed_by_area_small_room():
    # 20 м² / 40 м²/датчик = ceil(0.5) = 1; periметр малий, spacing не критичний
    count = detectors_needed(DetectorKind.SMOKE, area_m2=20.0, perimeter_m=18.0)
    assert count == max(1, math.ceil(18.0 / 9.0))  # spacing домінує: ceil(18/9)=2


def test_detectors_needed_by_spacing_dominates_for_long_narrow_room():
    # довга вузька кімната: площа мала, але периметр великий -> spacing домінує
    count = detectors_needed(DetectorKind.SMOKE, area_m2=15.0, perimeter_m=40.0)
    assert count == math.ceil(40.0 / 9.0)


def test_detectors_needed_rejects_non_positive_area():
    with pytest.raises(ValueError):
        detectors_needed(DetectorKind.SMOKE, area_m2=0, perimeter_m=10.0)


def test_place_detectors_along_contour_rectangle_hand_verified():
    """Прямокутник 6000×5000 мм, 3 датчики, відступ 0.5 м (500мм).

    Периметр = 22000мм. Точки на дузі (i+0.5)/3*22000:
      i=0: 3666.67мм -> на нижньому ребрі (0,0)-(6000,0) -> (3666.67, 0) -> +500 по Z -> (3666.67, 500)
      i=1: 11000мм -> на правому ребрі (6000,0)-(6000,5000) -> (6000,5000) -> -500 по X -> (5500, 5000)
      i=2: 18333.33мм -> на верхньому/лівому ребрах -> (0, 3666.67) -> +500 по X -> (500, 3666.67)
    """
    contour = [Point(0, 0), Point(6000, 0), Point(6000, 5000), Point(0, 5000)]
    positions = place_detectors_along_contour(contour, count=3, wall_clearance_m=0.5)
    assert len(positions) == 3

    assert positions[0].x == pytest.approx(3666.6667, abs=1e-2)
    assert positions[0].z == pytest.approx(500.0, abs=1e-6)

    assert positions[1].x == pytest.approx(5500.0, abs=1e-6)
    assert positions[1].z == pytest.approx(5000.0, abs=1e-6)

    assert positions[2].x == pytest.approx(500.0, abs=1e-6)
    assert positions[2].z == pytest.approx(3666.6667, abs=1e-2)


def test_place_detectors_rejects_non_positive_count():
    with pytest.raises(ValueError):
        place_detectors_along_contour([Point(0, 0), Point(1, 0), Point(1, 1)], count=0, wall_clearance_m=0.5)


def test_auto_place_detectors_on_room_hand_verified():
    """Кімната 6×5 м (30 м², периметр 22 м): за площею треба 1 датчик,
    за відстанню (22/9=2.44) — 3, отже розставляється 3."""
    room = Room.from_contour(
        [Point(0, 0), Point(6000, 0), Point(6000, 5000), Point(0, 5000)],
        height=2700,
        thickness=200,
        material=Material("цегла", 1800),
        name="Вітальня",
    )
    detectors = auto_place_detectors(room, DetectorKind.SMOKE)
    assert len(detectors) == 3
    assert all(isinstance(d, FireDetector) for d in detectors)
    assert all(d.kind is DetectorKind.SMOKE for d in detectors)


def test_detector_to_consumption_point_uses_switch_kind():
    """У модулі 4 немає типу "датчик" — використовується PointKind.SWITCH
    як найближчий за суттю малопотужний сигнальний пристрій."""
    from kovadlo.electrical_point import PointKind

    detector = FireDetector("Димовий датчик 1", DetectorKind.SMOKE, Point(1000, 1000))
    point = detector.to_consumption_point()
    assert point.kind is PointKind.SWITCH
    assert point.power_w == pytest.approx(0.5)
    assert point.position == Point(1000, 1000)


def test_loop_length_hand_verified():
    """Панель (0,0) -> (3000,0) -> (3000,4000) -> назад до (0,0):
    3000 + 4000 + 5000(гіпотенуза 3-4-5) = 12000 мм = 12 м."""
    panel = Point(0, 0)
    detectors = [Point(3000, 0), Point(3000, 4000)]
    length = loop_length_m(panel, detectors)
    assert length == pytest.approx(12.0)


def test_loop_length_empty_detectors_is_zero():
    assert loop_length_m(Point(0, 0), []) == 0.0
