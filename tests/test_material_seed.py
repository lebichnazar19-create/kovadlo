import pytest

from kovadlo.material_seed import build_default_database
from kovadlo.material_spec import MaterialCategory


def test_no_duplicate_names_in_seed_data():
    db = build_default_database()  # __post_init__ уже перевіряє дублікати, викличе тут же
    names = [m.name for m in db.materials]
    assert len(names) == len(set(names))


def test_every_required_category_has_at_least_two_entries():
    db = build_default_database()
    for category in MaterialCategory:
        entries = db.by_category(category)
        assert len(entries) >= 2, f"замало записів у категорії {category.value}"


def test_every_entry_has_source_note_and_price():
    db = build_default_database()
    for material in db.materials:
        assert material.source_note, f"немає джерела значень для {material.name}"
        assert material.prices, f"немає ціни для {material.name}"


def test_conductors_have_electrical_resistivity():
    db = build_default_database()
    for material in db.by_category(MaterialCategory.CONDUCTOR):
        assert material.electrical_resistivity_ohm_m is not None
        assert material.electrical_resistivity_ohm_m > 0


def test_insulation_entries_have_thermal_conductivity():
    db = build_default_database()
    for material in db.by_category(MaterialCategory.INSULATION):
        assert material.thermal_conductivity_w_mk is not None


def test_metals_have_thermal_conductivity_for_radiators_and_motors():
    db = build_default_database()
    for material in db.by_category(MaterialCategory.METAL):
        assert material.thermal_conductivity_w_mk is not None
    copper = db.find_by_name("Мідь (метал, Cu-ETP)")
    aluminium = db.find_by_name("Алюміній (сплав 6060, Т6)")
    steel = db.find_by_name("Сталь конструкційна S235JR")
    # мідь і алюміній — кращі провідники тепла за конструкційну сталь
    # (саме тому їх використовують для радіаторів і корпусів моторів)
    assert copper.thermal_conductivity_w_mk > steel.thermal_conductivity_w_mk
    assert aluminium.thermal_conductivity_w_mk > steel.thermal_conductivity_w_mk


def test_tile_adhesive_grades_reflect_c1_vs_c2_outdoor_capability():
    db = build_default_database()
    basic = db.find_by_name("Клей плитковий C1T")
    improved = db.find_by_name("Клей плитковий C2TE S1")
    assert basic.outdoor_suitable is False
    assert improved.outdoor_suitable is True
    assert improved.frost_resistant is True


def test_price_reference_thickness_set_for_insulation_boards():
    db = build_default_database()
    for material in db.by_category(MaterialCategory.INSULATION):
        price_m2 = material.price_per("м2")
        assert price_m2 is not None
        assert price_m2.reference_thickness_mm == 100
