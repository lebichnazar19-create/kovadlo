import pytest

from kovadlo.climate import (
    BuildingElement,
    HeatBalance,
    select_ac_power_kw,
    select_radiator_power_w,
    transmission_heat_loss_w,
    ventilation_heat_loss_w,
)


def test_building_element_rejects_non_positive_area_or_u():
    with pytest.raises(ValueError):
        BuildingElement("Стіна", area_m2=0, u_value_w_m2k=0.2)
    with pytest.raises(ValueError):
        BuildingElement("Стіна", area_m2=10, u_value_w_m2k=0)


def test_transmission_heat_loss_hand_calculation():
    # 40*0.2*40 + 5*0.9*40 = 320 + 180 = 500 Вт
    wall = BuildingElement("Стіна", area_m2=40, u_value_w_m2k=0.2)
    window = BuildingElement("Вікно", area_m2=5, u_value_w_m2k=0.9)
    assert transmission_heat_loss_w([wall, window], delta_t_k=40.0) == pytest.approx(500.0)


def test_ventilation_heat_loss_hand_calculation():
    # 0.34 * 50 * 40 = 680 Вт
    assert ventilation_heat_loss_w(50.0, delta_t_k=40.0) == pytest.approx(680.0)


def test_heat_balance_totals_hand_verified():
    wall = BuildingElement("Стіна", area_m2=40, u_value_w_m2k=0.2)
    window = BuildingElement("Вікно", area_m2=5, u_value_w_m2k=0.9)
    balance = HeatBalance(elements=[wall, window], delta_t_k=40.0, airflow_m3_h=50.0)
    assert balance.transmission_loss_w == pytest.approx(500.0)
    assert balance.ventilation_loss_w == pytest.approx(680.0)
    assert balance.total_loss_w == pytest.approx(1180.0)


def test_select_radiator_power_hand_verified():
    # 1180 Вт -> найближчий зверху стандарт: 1250 Вт
    assert select_radiator_power_w(1180.0) == 1250.0


def test_select_ac_power_hand_verified():
    # 1180 Вт = 1.18 кВт -> найближчий зверху стандарт: 2.0 кВт
    assert select_ac_power_kw(1180.0) == 2.0


def test_select_radiator_power_raises_above_series():
    with pytest.raises(ValueError):
        select_radiator_power_w(1_000_000.0)


def test_select_ac_power_raises_above_series():
    with pytest.raises(ValueError):
        select_ac_power_kw(1_000_000.0)
