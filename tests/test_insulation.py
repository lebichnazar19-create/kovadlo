import pytest

from kovadlo.insulation import (
    RSE_WALL_M2K_W,
    RSI_WALL_M2K_W,
    WT2021_MAX_U_WALL_W_M2K,
    WallLayer,
    check_against_wt2021,
    condensation_risk_warnings,
    dew_point_c,
    insulation_cost_per_m2,
    layer_interface_temperatures_c,
    required_insulation_thickness_m,
    wall_thermal_resistance_m2k_w,
    wall_u_value_w_m2k,
)
from kovadlo.material_seed import build_default_database
from kovadlo.material_spec import MaterialCategory, MaterialSpec, PriceInfo


def _material(name: str, conductivity: float) -> MaterialSpec:
    return MaterialSpec(name=name, category=MaterialCategory.INSULATION, thermal_conductivity_w_mk=conductivity)


def test_wall_layer_rejects_non_positive_thickness():
    with pytest.raises(ValueError):
        WallLayer(_material("X", 0.04), thickness_m=0)


def test_wall_layer_requires_known_conductivity():
    material = MaterialSpec(name="X", category=MaterialCategory.METAL)
    with pytest.raises(ValueError):
        WallLayer(material, thickness_m=0.1)


def test_layer_resistance_hand_calculation():
    layer = WallLayer(_material("Бетон", 1.8), thickness_m=0.2)
    assert layer.thermal_resistance_m2k_w == pytest.approx(0.2 / 1.8)


def test_wall_resistance_and_u_value_hand_calculation():
    """Бетон 200мм, λ=1.8: R = 0.13 + 0.2/1.8 + 0.04 = 0.28111 м²·К/Вт
    U = 1/0.28111 = 3.5573 Вт/(м²·К)."""
    layers = [WallLayer(_material("Бетон", 1.8), thickness_m=0.2)]
    r = wall_thermal_resistance_m2k_w(layers)
    assert r == pytest.approx(RSI_WALL_M2K_W + 0.2 / 1.8 + RSE_WALL_M2K_W)
    assert wall_u_value_w_m2k(layers) == pytest.approx(1 / r)
    assert wall_u_value_w_m2k(layers) == pytest.approx(3.5573, abs=1e-3)


def test_bare_concrete_wall_fails_wt2021():
    layers = [WallLayer(_material("Бетон", 1.8), thickness_m=0.2)]
    check = check_against_wt2021(layers)
    assert check.meets_norm is False
    assert check.max_u_value_w_m2k == WT2021_MAX_U_WALL_W_M2K


def test_required_insulation_thickness_hand_calculation():
    """base_r = 0.13+0.04+0.2/1.8 = 0.28111; target_r=1/0.2=5.0
    needed_r = 4.71889; thickness = 4.71889*0.038 = 0.17932 м (179.3 мм)."""
    base = [WallLayer(_material("Бетон", 1.8), thickness_m=0.2)]
    wool = _material("Вата", 0.038)
    thickness = required_insulation_thickness_m(base, wool)
    assert thickness == pytest.approx(0.179317, abs=1e-5)

    # додавши цю товщину, стіна має точно (з похибкою округлення) відповідати нормі
    full = base + [WallLayer(wool, thickness_m=thickness)]
    assert wall_u_value_w_m2k(full) == pytest.approx(WT2021_MAX_U_WALL_W_M2K)
    assert check_against_wt2021(full).meets_norm is True


def test_required_insulation_thickness_raises_when_base_already_meets_norm():
    great_insulator = [WallLayer(_material("PIR", 0.023), thickness_m=0.3)]
    with pytest.raises(ValueError):
        required_insulation_thickness_m(great_insulator, _material("Вата", 0.038))


def test_insulation_cost_per_m2_uses_module7_pricing():
    db = build_default_database()
    wool = db.find_by_name("Мінеральна вата (кам'яна)")
    cost = insulation_cost_per_m2(wool, thickness_m=0.095)
    assert cost == pytest.approx(22.8, abs=0.01)  # 24 зл/м2 при 100мм -> 24*0.95


def test_dew_point_hand_verified_reference_point():
    # 20°C, 50% RH: формула Магнуса, a=17.27, b=237.7
    # alpha = ln(0.5) + 17.27*20/(237.7+20); Tdp = 237.7*alpha/(17.27-alpha)
    import math

    a, b = 17.27, 237.7
    alpha = math.log(0.5) + (a * 20.0) / (b + 20.0)
    expected = (b * alpha) / (a - alpha)
    assert dew_point_c(20.0, 50.0) == pytest.approx(expected)
    assert dew_point_c(20.0, 50.0) == pytest.approx(9.25, abs=0.05)


def test_dew_point_rises_with_humidity():
    assert dew_point_c(20.0, 80.0) > dew_point_c(20.0, 30.0)


def test_layer_interface_temperatures_endpoints():
    layers = [WallLayer(_material("Бетон", 1.8), thickness_m=0.2)]
    temps = layer_interface_temperatures_c(layers, indoor_temp_c=20.0, outdoor_temp_c=-20.0)
    assert len(temps) == 2  # Rsi -> межа після єдиного шару
    assert temps[0] < 20.0  # внутрішня поверхня трохи холодніша за повітря
    assert temps[-1] > -20.0  # зовнішня поверхня трохи тепліша за вулицю


def test_condensation_warning_triggers_for_cold_uninsulated_wall():
    layers = [WallLayer(_material("Бетон", 1.8), thickness_m=0.2)]
    warnings = condensation_risk_warnings(
        layers, indoor_temp_c=20.0, indoor_relative_humidity_percent=60.0, outdoor_temp_c=-20.0
    )
    assert len(warnings) > 0


def test_no_condensation_warning_for_well_insulated_wall():
    db = build_default_database()
    wool = db.find_by_name("Мінеральна вата (кам'яна)")
    concrete = db.find_by_name("Бетон C25/30")
    layers = [WallLayer(concrete, thickness_m=0.2), WallLayer(wool, thickness_m=0.2)]
    warnings = condensation_risk_warnings(
        layers, indoor_temp_c=20.0, indoor_relative_humidity_percent=50.0, outdoor_temp_c=-20.0
    )
    assert warnings == []
