"""База матеріалів: сховище записів + пошук і фільтр за властивостями."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field

from .material_spec import MaterialCategory, MaterialSpec


@dataclass
class MaterialDatabase:
    """Сховище матеріалів модуля 7: список записів, унікальних за назвою
    (назва — це і є "ключ", за яким на базу посилаються стіни/плитка/
    дорожки — див. `MaterialSpec.to_core_material`)."""

    materials: list[MaterialSpec] = field(default_factory=list)

    def __post_init__(self) -> None:
        names = [m.name for m in self.materials]
        duplicates = sorted({n for n in names if names.count(n) > 1})
        if duplicates:
            raise ValueError(f"Дублікати назв матеріалів у базі: {', '.join(duplicates)}")

    def add(self, material: MaterialSpec) -> None:
        """Додає матеріал у базу; помилка, якщо назва вже зайнята."""
        if self.find_by_name(material.name) is not None:
            raise ValueError(f"Матеріал з назвою «{material.name}» вже є в базі")
        self.materials.append(material)

    def find_by_name(self, name: str) -> MaterialSpec | None:
        """Пошук за точною назвою — саме так `Wall.material.name` (модуль 1)
        зв'язується з повним записом бази."""
        for material in self.materials:
            if material.name == name:
                return material
        return None

    def by_category(self, category: MaterialCategory) -> list[MaterialSpec]:
        return [m for m in self.materials if m.category is category]

    def filter(self, predicate: Callable[[MaterialSpec], bool]) -> list[MaterialSpec]:
        """Довільний фільтр за предикатом `MaterialSpec -> bool`."""
        return [m for m in self.materials if predicate(m)]

    # --- готові фільтри за поширеними властивостями ---

    def where_thermal_conductivity_below(self, max_w_mk: float) -> list[MaterialSpec]:
        """Теплопровідність менша за X, Вт/(м·К) — напр. для підбору утеплювача."""
        return self.filter(
            lambda m: m.thermal_conductivity_w_mk is not None and m.thermal_conductivity_w_mk < max_w_mk
        )

    def where_compressive_strength_above(self, min_mpa: float) -> list[MaterialSpec]:
        """Міцність на стиск більша за Y, МПа."""
        return self.filter(
            lambda m: m.compressive_strength_mpa is not None and m.compressive_strength_mpa > min_mpa
        )

    def where_frost_resistant(self) -> list[MaterialSpec]:
        return self.filter(lambda m: m.frost_resistant is True)

    def where_water_resistant(self) -> list[MaterialSpec]:
        return self.filter(lambda m: m.water_resistant is True)

    def where_outdoor_suitable(self) -> list[MaterialSpec]:
        return self.filter(lambda m: m.outdoor_suitable is True)
