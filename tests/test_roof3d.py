import math

import pytest

from kovadlo.geometry import Point, polygon_area
from kovadlo.roof3d import RoofType, build_gable_roof, build_shed_roof

RECT = [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)]
FOOTPRINT_M2 = polygon_area(RECT) / 1_000_000  # 12.0


def test_shed_roof_rejects_non_rectangular_contour():
    l_shape = [Point(0, 0), Point(4000, 0), Point(4000, 2000), Point(5500, 2000), Point(5500, 3000), Point(0, 3000)]
    with pytest.raises(ValueError):
        build_shed_roof(l_shape, base_height_mm=2700, slope_deg=30)


def test_roof_rejects_invalid_slope():
    with pytest.raises(ValueError):
        build_shed_roof(RECT, base_height_mm=2700, slope_deg=0)
    with pytest.raises(ValueError):
        build_shed_roof(RECT, base_height_mm=2700, slope_deg=90)


@pytest.mark.parametrize("low_side", ["south", "north", "west", "east"])
def test_shed_roof_area_matches_footprint_over_cosine(low_side):
    """Інваріант, перевірений вручну: площа схилу = площа контуру / cos(кута),
    незалежно від того, з якого боку карниз."""
    slope = 30.0
    roof = build_shed_roof(RECT, base_height_mm=2700, slope_deg=slope, low_side=low_side)
    expected = FOOTPRINT_M2 / math.cos(math.radians(slope))
    assert roof.area_m2 == pytest.approx(expected)
    assert roof.roof_type is RoofType.SHED
    assert len(roof.faces) == 1


def test_shed_roof_rise_hand_calculation():
    # карниз південь/північ: прогін = 3000мм (по Z) -> rise = 3000*tan(30°)
    roof = build_shed_roof(RECT, base_height_mm=2700, slope_deg=30.0, low_side="south")
    assert roof.ridge_rise_mm == pytest.approx(3000 * math.tan(math.radians(30.0)))

    # карниз захід/схід: прогін = 4000мм (по X)
    roof_we = build_shed_roof(RECT, base_height_mm=2700, slope_deg=30.0, low_side="west")
    assert roof_we.ridge_rise_mm == pytest.approx(4000 * math.tan(math.radians(30.0)))


@pytest.mark.parametrize("ridge_along", ["x", "z"])
def test_gable_roof_area_matches_footprint_over_cosine(ridge_along):
    slope = 30.0
    roof = build_gable_roof(RECT, base_height_mm=2700, slope_deg=slope, ridge_along=ridge_along)
    expected = FOOTPRINT_M2 / math.cos(math.radians(slope))
    assert roof.area_m2 == pytest.approx(expected)
    assert roof.roof_type is RoofType.GABLE
    assert len(roof.faces) == 2


def test_gable_roof_rise_is_half_the_shed_rise():
    """Гребінь двосхилого — посередині прогону, тож підйом гребеня вдвічі
    менший за підйом карниза-до-карниза еквівалентного односхилого."""
    slope = 30.0
    gable = build_gable_roof(RECT, base_height_mm=2700, slope_deg=slope, ridge_along="x")
    shed = build_shed_roof(RECT, base_height_mm=2700, slope_deg=slope, low_side="south")
    assert gable.ridge_rise_mm == pytest.approx(shed.ridge_rise_mm / 2)


def test_gable_roof_unknown_axis_rejected():
    with pytest.raises(ValueError):
        build_gable_roof(RECT, base_height_mm=2700, slope_deg=30, ridge_along="y")
