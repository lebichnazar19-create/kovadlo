"""Підбір матеріалу під задачу: умови -> підхожі матеріали з обґрунтуванням."""

from __future__ import annotations

from dataclasses import dataclass

from .material_database import MaterialDatabase
from .material_spec import MaterialCategory, MaterialSpec


@dataclass
class SelectionCriteria:
    """Умови задачі для підбору матеріалу.

    `location` — довільний опис "де" (напр. "балкон", "фундамент") —
    використовується лише як інформаційний контекст (не жорсткий
    фільтр, оскільки це вільний текст); фактичний відбір іде за рештою
    полів.
    """

    category: MaterialCategory | None = None
    location: str = ""
    outdoor: bool | None = None  # True — вулиця, False — приміщення, None — без вимоги
    require_frost_resistant: bool = False
    require_water_resistant: bool = False
    min_compressive_strength_mpa: float | None = None
    max_thermal_conductivity_w_mk: float | None = None


@dataclass
class SelectionResult:
    """Один підхожий матеріал + причини, чому він підходить під умови."""

    material: MaterialSpec
    reasons: list[str]

    def __str__(self) -> str:
        return f"{self.material.summary_line()} — " + "; ".join(self.reasons)


def select_materials(db: MaterialDatabase, criteria: SelectionCriteria) -> list[SelectionResult]:
    """Повертає матеріали бази, що задовольняють `criteria`, з переліком
    причин для кожного (для обґрунтування вибору користувачу)."""
    candidates = db.materials if criteria.category is None else db.by_category(criteria.category)
    results: list[SelectionResult] = []

    for material in candidates:
        reasons: list[str] = []
        ok = True

        if criteria.outdoor is True:
            if material.outdoor_suitable is True:
                reasons.append("придатний для вулиці")
            else:
                ok = False
        elif criteria.outdoor is False:
            reasons.append("для внутрішнього застосування")

        if criteria.require_frost_resistant:
            if material.frost_resistant is True:
                reasons.append("морозостійкий")
            else:
                ok = False

        if criteria.require_water_resistant:
            if material.water_resistant is True:
                reasons.append("водостійкий")
            else:
                ok = False

        if criteria.min_compressive_strength_mpa is not None:
            strength = material.compressive_strength_mpa
            if strength is not None and strength >= criteria.min_compressive_strength_mpa:
                reasons.append(
                    f"міцність на стиск {strength:g} МПа ≥ вимоги {criteria.min_compressive_strength_mpa:g} МПа"
                )
            else:
                ok = False

        if criteria.max_thermal_conductivity_w_mk is not None:
            conductivity = material.thermal_conductivity_w_mk
            if conductivity is not None and conductivity <= criteria.max_thermal_conductivity_w_mk:
                reasons.append(
                    f"теплопровідність {conductivity:g} Вт/(м·К) ≤ вимоги {criteria.max_thermal_conductivity_w_mk:g}"
                )
            else:
                ok = False

        if ok:
            if material.application:
                reasons.append(f"застосування виробника: {material.application}")
            if criteria.location:
                reasons.append(f"контекст задачі: «{criteria.location}»")
            results.append(SelectionResult(material=material, reasons=reasons))

    return results


def select_tile_adhesive_for_balcony(db: MaterialDatabase) -> list[SelectionResult]:
    """Приклад типової задачі: клей для плитки на балконі — вулиця,
    морозостійкість і водостійкість обов'язкові (циклічне замерзання
    вологи під плиткою — головна причина відмов клею на балконах)."""
    criteria = SelectionCriteria(
        category=MaterialCategory.TILE_ADHESIVE,
        location="балкон",
        outdoor=True,
        require_frost_resistant=True,
        require_water_resistant=True,
    )
    return select_materials(db, criteria)
