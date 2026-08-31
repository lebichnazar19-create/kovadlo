import pytest

from kovadlo.material_compare import (
    compare_for_thermal_resistance,
    conductor_resistance_ohm,
    thermal_layer_option,
)
from kovadlo.material_seed import build_default_database
from kovadlo.material_spec import MaterialCategory, MaterialSpec, PriceInfo

# ---------------------------------------------------------------------------
# Теплотехнічний розрахунок стіни/шару (ручна перевірка)
# ---------------------------------------------------------------------------


def test_thermal_layer_thickness_hand_calculation():
    # R = d/λ -> d = R·λ. Для λ=0.038 Вт/(м·К) і R=2.5 м²·К/Вт:
    # d = 2.5 * 0.038 = 0.095 м = 95 мм
    material = MaterialSpec(
        name="Тестова вата",
        category=MaterialCategory.INSULATION,
        thermal_conductivity_w_mk=0.038,
        prices=[PriceInfo(price_pln=24, unit="м2", date="2026-08", reference_thickness_mm=100)],
    )
    option = thermal_layer_option(material, required_resistance_m2k_w=2.5)
    assert option.thickness_m == pytest.approx(0.095)
    assert option.thickness_mm == pytest.approx(95.0)
    # ціна масштабована з опорної товщини 100 мм: 24 * (95/100) = 22.8
    assert option.cost_per_m2_pln == pytest.approx(22.8)


def test_thermal_layer_cost_from_price_per_kg_and_density():
    # d = R·λ = 2.0 * 0.8 = 1.6 м (умовно товстий шар для простоти рахунку)
    # маса на м² = 1.6 м * 1800 кг/м³ = 2880 кг/м²
    # ціна = 2880 * 0.72 зл/кг = 2073.6 зл/м²
    material = MaterialSpec(
        name="Тестовий розчин",
        category=MaterialCategory.CONCRETE,
        thermal_conductivity_w_mk=0.8,
        density_kg_m3=1800,
        prices=[PriceInfo(price_pln=0.72, unit="кг", date="2026-08")],
    )
    option = thermal_layer_option(material, required_resistance_m2k_w=2.0)
    assert option.thickness_m == pytest.approx(1.6)
    assert option.cost_per_m2_pln == pytest.approx(2880 * 0.72)


def test_thermal_layer_rejects_missing_conductivity():
    material = MaterialSpec(name="X", category=MaterialCategory.METAL)
    with pytest.raises(ValueError):
        thermal_layer_option(material, required_resistance_m2k_w=2.0)


def test_thermal_layer_rejects_non_positive_resistance():
    material = MaterialSpec(name="X", category=MaterialCategory.INSULATION, thermal_conductivity_w_mk=0.03)
    with pytest.raises(ValueError):
        thermal_layer_option(material, required_resistance_m2k_w=0)


def test_compare_mineral_wool_vs_xps_from_seed_data_hand_verified():
    """Стінне утеплення, R = 2.5 м²·К/Вт (типова вимога для стін у Польщі).

    Мін. вата λ=0.038: d=95мм, ціна = 24*(95/100)=22.8 зл/м².
    XPS λ=0.033: d=82.5мм, ціна = 28*(82.5/100)=23.1 зл/м².
    Отже дешевша — мінеральна вата.
    """
    db = build_default_database()
    wool = db.find_by_name("Мінеральна вата (кам'яна)")
    xps = db.find_by_name("XPS (екструдований пінополістирол)")

    comparison = compare_for_thermal_resistance(wool, xps, required_resistance_m2k_w=2.5)

    assert comparison.option_a.thickness_mm == pytest.approx(95.0)
    assert comparison.option_a.cost_per_m2_pln == pytest.approx(22.8)
    assert comparison.option_b.thickness_mm == pytest.approx(82.5)
    assert comparison.option_b.cost_per_m2_pln == pytest.approx(23.1)
    assert comparison.cheaper is comparison.option_a
    assert "Мінеральна вата" in str(comparison)


def test_comparison_cheaper_is_none_when_price_unknown():
    a = MaterialSpec(name="A", category=MaterialCategory.INSULATION, thermal_conductivity_w_mk=0.03)
    b = MaterialSpec(
        name="B",
        category=MaterialCategory.INSULATION,
        thermal_conductivity_w_mk=0.03,
        density_kg_m3=30,
        prices=[PriceInfo(price_pln=20, unit="кг", date="2026-08")],
    )
    comparison = compare_for_thermal_resistance(a, b, required_resistance_m2k_w=2.0)
    assert comparison.option_a.cost_per_m2_pln is None
    assert comparison.cheaper is None


# ---------------------------------------------------------------------------
# Опір мідної доріжки/жили (ручна перевірка)
# ---------------------------------------------------------------------------


def test_conductor_resistance_hand_calculation():
    # ρ = 0.02 Ом·мм²/м (умовне кругле число), L=10 м, A=2 мм² -> R = 0.02*10/2 = 0.1 Ом
    material = MaterialSpec(
        name="Умовний провідник", category=MaterialCategory.CONDUCTOR, electrical_resistivity_ohm_m=0.02e-6
    )
    r = conductor_resistance_ohm(material, length_m=10.0, cross_section_mm2=2.0)
    assert r == pytest.approx(0.1)


def test_copper_track_resistance_from_seed_database_hand_verified():
    """Опір мідної доріжки платою модуля 6: L=100 мм, ширина 0.5 мм,
    товщина міді 35 мкм (0.035 мм) — але опір рахуємо з питомого опору
    міді З БАЗИ МАТЕРІАЛІВ (категорія "провідники"), а не з внутрішньої
    константи модуля 6.

    ρ(Cu, з бази) = 1.72e-8 Ом·м = 1.72e-8 * 1e6 = 0.0172 Ом·мм²/м
    A = 0.5 * 0.035 = 0.0175 мм²
    R = 0.0172 * 0.1 / 0.0175 ≈ 0.098286 Ом ≈ 98.3 мОм

    Це трохи МЕНШЕ за результат `pcb_norms.track_resistance_ohm` для тієї
    самої геометрії (≈102.9 мОм) — модуль 6 навмисно використовує дещо
    вищий (запас на нагрів) питомий опір 0.018 Ом·мм²/м, а не "холодне"
    довідкове значення з бази. Це очікувана, а не помилкова різниця.
    """
    db = build_default_database()
    copper = db.find_by_name("Мідь (провідникова, відпалена)")
    assert copper.electrical_resistivity_ohm_m == pytest.approx(1.72e-8)

    length_m = 0.1  # 100 мм
    width_mm = 0.5
    thickness_mm = 0.035  # 35 мкм
    area_mm2 = width_mm * thickness_mm  # 0.0175 мм²

    resistance_ohm = conductor_resistance_ohm(copper, length_m=length_m, cross_section_mm2=area_mm2)

    assert resistance_ohm == pytest.approx(0.09828571428571429, rel=1e-9)

    from kovadlo.pcb_norms import track_resistance_ohm

    pcb_module_resistance = track_resistance_ohm(length_mm=100, width_mm=0.5)
    assert resistance_ohm < pcb_module_resistance  # база дає "холодніший", менший опір


def test_conductor_resistance_rejects_missing_resistivity():
    material = MaterialSpec(name="X", category=MaterialCategory.METAL)
    with pytest.raises(ValueError):
        conductor_resistance_ohm(material, length_m=1.0, cross_section_mm2=1.0)


def test_conductor_resistance_rejects_non_positive_geometry():
    material = MaterialSpec(name="X", category=MaterialCategory.CONDUCTOR, electrical_resistivity_ohm_m=1.7e-8)
    with pytest.raises(ValueError):
        conductor_resistance_ohm(material, length_m=0, cross_section_mm2=1.0)
    with pytest.raises(ValueError):
        conductor_resistance_ohm(material, length_m=1.0, cross_section_mm2=0)
