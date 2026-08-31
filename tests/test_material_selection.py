import pytest

from kovadlo.material_database import MaterialDatabase
from kovadlo.material_seed import build_default_database
from kovadlo.material_selection import (
    SelectionCriteria,
    select_materials,
    select_tile_adhesive_for_balcony,
)
from kovadlo.material_spec import MaterialCategory, MaterialSpec


def test_select_by_category_only_returns_all_of_category():
    db = build_default_database()
    result = select_materials(db, SelectionCriteria(category=MaterialCategory.GROUT))
    assert len(result) == len(db.by_category(MaterialCategory.GROUT))


def test_select_requires_frost_and_water_resistance():
    db = MaterialDatabase(
        materials=[
            MaterialSpec("A", MaterialCategory.TILE_ADHESIVE, frost_resistant=True, water_resistant=True),
            MaterialSpec("B", MaterialCategory.TILE_ADHESIVE, frost_resistant=True, water_resistant=False),
            MaterialSpec("C", MaterialCategory.TILE_ADHESIVE, frost_resistant=False, water_resistant=True),
        ]
    )
    result = select_materials(
        db, SelectionCriteria(require_frost_resistant=True, require_water_resistant=True)
    )
    assert [r.material.name for r in result] == ["A"]


def test_select_outdoor_true_excludes_indoor_only():
    db = MaterialDatabase(
        materials=[
            MaterialSpec("Зовнішній", MaterialCategory.TILE_ADHESIVE, outdoor_suitable=True),
            MaterialSpec("Внутрішній", MaterialCategory.TILE_ADHESIVE, outdoor_suitable=False),
        ]
    )
    result = select_materials(db, SelectionCriteria(outdoor=True))
    assert [r.material.name for r in result] == ["Зовнішній"]


def test_select_min_compressive_strength():
    db = MaterialDatabase(
        materials=[
            MaterialSpec("Міцний", MaterialCategory.CONCRETE, compressive_strength_mpa=30),
            MaterialSpec("Слабкий", MaterialCategory.CONCRETE, compressive_strength_mpa=10),
            MaterialSpec("Невідомо", MaterialCategory.CONCRETE),
        ]
    )
    result = select_materials(db, SelectionCriteria(min_compressive_strength_mpa=20))
    assert [r.material.name for r in result] == ["Міцний"]


def test_select_max_thermal_conductivity():
    db = MaterialDatabase(
        materials=[
            MaterialSpec("Добрий", MaterialCategory.INSULATION, thermal_conductivity_w_mk=0.02),
            MaterialSpec("Гірший", MaterialCategory.INSULATION, thermal_conductivity_w_mk=0.05),
        ]
    )
    result = select_materials(db, SelectionCriteria(max_thermal_conductivity_w_mk=0.03))
    assert [r.material.name for r in result] == ["Добрий"]


def test_result_reasons_mention_matched_criteria():
    db = MaterialDatabase(
        materials=[MaterialSpec("A", MaterialCategory.CONCRETE, compressive_strength_mpa=30)]
    )
    result = select_materials(db, SelectionCriteria(min_compressive_strength_mpa=20))
    assert len(result) == 1
    assert any("міцність" in reason for reason in result[0].reasons)


# ---------------------------------------------------------------------------
# Контрольний сценарій із завдання: вибір клею для балкона
# ---------------------------------------------------------------------------


def test_tile_adhesive_for_balcony_hand_verified():
    """Балкон — вулиця, морозостійкість і водостійкість обов'язкові.

    У сід-даних (`material_seed.py`) три клеї: C1T (не морозостійкий,
    не для вулиці), C2TE S1 і C2S2 (обидва морозостійкі, водостійкі,
    для вулиці) — тож правильна відповідь: рівно ці два, C1T відсіяний.
    """
    db = build_default_database()
    result = select_tile_adhesive_for_balcony(db)
    names = {r.material.name for r in result}
    assert names == {"Клей плитковий C2TE S1", "Клей плитковий C2S2"}
    assert "Клей плитковий C1T" not in names

    for r in result:
        assert r.material.outdoor_suitable is True
        assert r.material.frost_resistant is True
        assert r.material.water_resistant is True
