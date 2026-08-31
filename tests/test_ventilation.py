import math

import pytest

from kovadlo.geometry import Point
from kovadlo.ventilation import (
    Duct,
    DuctShape,
    air_velocity_m_s,
    build_duct,
    pressure_loss_pa,
    required_airflow_m3_h,
    select_fan,
    select_round_duct_diameter_mm,
)
from kovadlo.ventilation_norms import VentilatedRoomKind


def test_required_airflow_kitchen_is_fixed_value():
    assert required_airflow_m3_h(VentilatedRoomKind.KITCHEN, volume_m3=32.4) == 50.0


def test_required_airflow_bedroom_uses_ach_times_volume():
    # 0.5 крат/год * 40 м³ = 20 м³/год
    assert required_airflow_m3_h(VentilatedRoomKind.BEDROOM, volume_m3=40.0) == pytest.approx(20.0)


def test_duct_requires_shape_specific_dimensions():
    with pytest.raises(ValueError):
        Duct(points=[Point(0, 0), Point(1000, 0)], shape=DuctShape.ROUND)
    with pytest.raises(ValueError):
        Duct(points=[Point(0, 0), Point(1000, 0)], shape=DuctShape.RECTANGULAR, width_mm=200)


def test_round_duct_cross_section_and_hydraulic_diameter():
    duct = Duct(points=[Point(0, 0), Point(1000, 0)], shape=DuctShape.ROUND, diameter_mm=100)
    expected_area = math.pi * (0.05) ** 2
    assert duct.cross_section_area_m2() == pytest.approx(expected_area)
    assert duct.hydraulic_diameter_m() == pytest.approx(0.1)


def test_rectangular_duct_hydraulic_diameter_hand_calculation():
    # a=0.2м, b=0.1м -> D_h = 4*(0.02)/(2*0.3) = 0.08/0.6 = 0.1333 м
    duct = Duct(points=[Point(0, 0), Point(1000, 0)], shape=DuctShape.RECTANGULAR, width_mm=200, height_mm=100)
    assert duct.hydraulic_diameter_m() == pytest.approx(0.08 / 0.6)


def test_build_duct_snaps_to_90_degrees():
    duct = build_duct(Point(0, 0), [Point(1005, 995)], DuctShape.ROUND, diameter_mm=100, snap_step=90.0)
    assert duct.points[1].x == pytest.approx(duct.points[0].x, abs=1e-6) or duct.points[1].z == pytest.approx(
        duct.points[0].z, abs=1e-6
    )


def test_air_velocity_hand_calculation():
    # v = (50/3600)/0.005 = 2.778 м/с
    v = air_velocity_m_s(50.0, 0.005)
    assert v == pytest.approx((50.0 / 3600) / 0.005)


def test_select_round_duct_diameter_hand_verified():
    """Витрата 50 м³/год: d=80мм дає v≈2.76м/с (<=4м/с) — має обратись
    саме 80мм, найменший у стандартному ряду, що задовольняє межу."""
    diameter = select_round_duct_diameter_mm(50.0)
    assert diameter == 80.0
    area = math.pi * (0.08 / 2) ** 2
    v = air_velocity_m_s(50.0, area)
    assert v == pytest.approx(2.7632, abs=1e-3)
    assert v <= 4.0


def test_pressure_loss_hand_calculation():
    """L=10м, d=80мм (D_h=0.08м), v≈2.763м/с:
    Δp = 0.02*(10/0.08)*(1.2*2.763²/2) ≈ 11.45 Па
    """
    duct = Duct(points=[Point(0, 0), Point(0, 5000), Point(5000, 5000)], shape=DuctShape.ROUND, diameter_mm=80)
    dp = pressure_loss_pa(duct, airflow_m3_h=50.0)
    assert dp == pytest.approx(11.45, abs=0.02)


def test_select_fan_hand_verified():
    name, max_flow, max_pressure = select_fan(required_flow_m3_h=50.0, required_pressure_pa=11.45)
    assert max_flow == 60.0
    assert max_pressure == 80.0


def test_select_fan_raises_when_nothing_fits():
    with pytest.raises(ValueError):
        select_fan(required_flow_m3_h=10_000.0, required_pressure_pa=10.0)


def test_select_round_duct_diameter_raises_when_airflow_too_high():
    with pytest.raises(ValueError):
        select_round_duct_diameter_mm(1_000_000.0)
