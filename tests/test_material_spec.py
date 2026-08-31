import pytest

from kovadlo.material_spec import Coverage, MaterialCategory, MaterialSpec, PriceInfo
from kovadlo.materials import Material


def test_to_core_material_bridges_name_and_density():
    spec = MaterialSpec(name="Бетон C25/30", category=MaterialCategory.CONCRETE, density_kg_m3=2400)
    core = spec.to_core_material()
    assert isinstance(core, Material)
    assert core.name == "Бетон C25/30"
    assert core.density_kg_m3 == 2400


def test_price_per_returns_matching_unit_or_none():
    spec = MaterialSpec(
        name="X",
        category=MaterialCategory.METAL,
        prices=[PriceInfo(price_pln=10, unit="кг", date="2026-08"), PriceInfo(price_pln=100, unit="м2", date="2026-08")],
    )
    assert spec.price_per("кг").price_pln == 10
    assert spec.price_per("м2").price_pln == 100
    assert spec.price_per("м3") is None


def test_price_info_rejects_negative_price():
    with pytest.raises(ValueError):
        PriceInfo(price_pln=-1, unit="кг", date="2026-08")


def test_summary_line_includes_designation_and_category():
    spec = MaterialSpec(name="Сталь S235JR", category=MaterialCategory.METAL, designation="S235JR")
    line = spec.summary_line()
    assert "Сталь S235JR" in line
    assert "S235JR" in line
    assert "метали" in line


def test_summary_line_without_designation():
    spec = MaterialSpec(name="XPS", category=MaterialCategory.INSULATION)
    assert spec.summary_line() == "XPS — ізоляція й утеплення"


def test_coverage_str_includes_note_when_present():
    cov = Coverage(value=1.3, unit="кг/м²", note="шар 1 мм")
    assert str(cov) == "1.3 кг/м² (шар 1 мм)"
    cov_no_note = Coverage(value=1.3, unit="кг/м²")
    assert str(cov_no_note) == "1.3 кг/м²"


def test_material_without_physical_properties_defaults_to_none():
    spec = MaterialSpec(name="Роз'єм", category=MaterialCategory.METAL)
    assert spec.thermal_conductivity_w_mk is None
    assert spec.compressive_strength_mpa is None
    assert spec.prices == []
