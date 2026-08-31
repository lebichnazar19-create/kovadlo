import pytest

from kovadlo.material_database import MaterialDatabase
from kovadlo.material_spec import MaterialCategory, MaterialSpec


def _spec(name: str, **kwargs) -> MaterialSpec:
    return MaterialSpec(name=name, category=kwargs.pop("category", MaterialCategory.INSULATION), **kwargs)


def test_rejects_duplicate_names_on_construction():
    with pytest.raises(ValueError):
        MaterialDatabase(materials=[_spec("A"), _spec("A")])


def test_add_appends_and_rejects_duplicate():
    db = MaterialDatabase()
    db.add(_spec("A"))
    assert len(db.materials) == 1
    with pytest.raises(ValueError):
        db.add(_spec("A"))


def test_find_by_name():
    db = MaterialDatabase(materials=[_spec("A"), _spec("B")])
    assert db.find_by_name("B").name == "B"
    assert db.find_by_name("C") is None


def test_by_category_filters_correctly():
    db = MaterialDatabase(
        materials=[
            _spec("Вата", category=MaterialCategory.INSULATION),
            _spec("Сталь", category=MaterialCategory.METAL),
        ]
    )
    assert [m.name for m in db.by_category(MaterialCategory.METAL)] == ["Сталь"]


def test_generic_filter_with_predicate():
    db = MaterialDatabase(materials=[_spec("A", density_kg_m3=100), _spec("B", density_kg_m3=2000)])
    heavy = db.filter(lambda m: m.density_kg_m3 is not None and m.density_kg_m3 > 500)
    assert [m.name for m in heavy] == ["B"]


def test_where_thermal_conductivity_below():
    db = MaterialDatabase(
        materials=[
            _spec("Добрий утеплювач", thermal_conductivity_w_mk=0.02),
            _spec("Гірший утеплювач", thermal_conductivity_w_mk=0.05),
            _spec("Невідомо", thermal_conductivity_w_mk=None),
        ]
    )
    result = db.where_thermal_conductivity_below(0.03)
    assert [m.name for m in result] == ["Добрий утеплювач"]


def test_where_compressive_strength_above():
    db = MaterialDatabase(
        materials=[
            _spec("Міцний", category=MaterialCategory.CONCRETE, compressive_strength_mpa=40),
            _spec("Слабкий", category=MaterialCategory.CONCRETE, compressive_strength_mpa=5),
        ]
    )
    result = db.where_compressive_strength_above(20)
    assert [m.name for m in result] == ["Міцний"]


def test_where_frost_water_outdoor_flags():
    db = MaterialDatabase(
        materials=[
            _spec("Морозостійкий", frost_resistant=True, water_resistant=False, outdoor_suitable=True),
            _spec("Звичайний", frost_resistant=False, water_resistant=True, outdoor_suitable=False),
        ]
    )
    assert [m.name for m in db.where_frost_resistant()] == ["Морозостійкий"]
    assert [m.name for m in db.where_water_resistant()] == ["Звичайний"]
    assert [m.name for m in db.where_outdoor_suitable()] == ["Морозостійкий"]
