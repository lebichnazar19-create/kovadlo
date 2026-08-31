"""
Матеріал бази даних (модуль 7): назва, категорія, фізичні й практичні
властивості, орієнтовна ціна.

Це наскрізна сутність — нею користуються стіни (модуль 1), плитка й
фуга (модуль 2), електропроводка (модуль 4), плати (модуль 6). Оскільки
ядро модулів 1-6 переписувати не можна, а `Wall.material` уже має тип
`kovadlo.materials.Material` (лише назва + густина), прив'язка
реалізована як ПОСИЛАННЯ ЗА ІМЕНЕМ: `MaterialSpec.to_core_material()`
дає сумісний з ядром об'єкт, а `MaterialDatabase.find_by_name(...)`
(див. `material_database.py`) повертає повний запис назад за тим самим
іменем — без додавання нових полів у наявні класи модулів 1-6.

**УВАГА — важливе застереження:** усі числові фізичні властивості й
ціни нижче (і в `material_seed.py`) — це орієнтовні довідкові значення
з поширених джерел (EN-стандарти на матеріали, каталоги виробників,
довідники будівельника), НЕ дослівна виписка з чинної норми чи
конкретного сертифіката якості. Перед реальним застосуванням звірте
значення з технічним листом (TDS/karta techniczna) конкретного продукту
й чинними нормами (EN 206, EN 1996, PN-EN 998-2 тощо).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .materials import Material


class MaterialCategory(Enum):
    """Категорія матеріалу (перша версія бази)."""

    CONCRETE = "бетони й розчини"
    GYPSUM = "гіпс і сухі суміші"
    TILE_ADHESIVE = "клеї для плитки"
    GROUT = "фуги"
    METAL = "метали"
    INSULATION = "ізоляція й утеплення"
    CONDUCTOR = "провідники"


@dataclass(frozen=True)
class Coverage:
    """Витрата матеріалу на одиницю площі/об'єму."""

    value: float
    unit: str  # напр. "кг/м²", "л/м²", "кг/м³"
    note: str = ""  # умови, за яких дана витрата (напр. "шар 3 мм")

    def __str__(self) -> str:
        base = f"{self.value:g} {self.unit}"
        return f"{base} ({self.note})" if self.note else base


@dataclass(frozen=True)
class PriceInfo:
    """Ціна матеріалу — ОРІЄНТОВНА, змінюється з часом і регіоном.

    `unit` — за що вказана ціна: "кг" | "м2" | "м3" | "упаковка".
    """

    price_pln: float
    unit: str
    date: str  # напр. "2026-08"
    region: str = "Польща"
    note: str = ""
    reference_thickness_mm: float | None = None  # для unit="м2" листових/плитних матеріалів

    def __post_init__(self) -> None:
        if self.price_pln < 0:
            raise ValueError("Ціна не може бути від'ємною")

    def __str__(self) -> str:
        return f"{self.price_pln:.2f} зл/{self.unit} (орієнтовно, {self.region}, {self.date})"


@dataclass
class MaterialSpec:
    """Повний запис матеріалу в базі модуля 7.

    Усі фізичні поля — `None`, якщо властивість не застосовна чи не
    відома для цього матеріалу (напр. міцність на розтяг для сипучої
    теплоізоляції не має сенсу).
    """

    name: str
    category: MaterialCategory
    designation: str = ""  # стандартне позначення: клас/марка, напр. "C25/30", "S235JR"

    # --- фізичні властивості (орієнтовні, див. застереження в docstring модуля) ---
    density_kg_m3: float | None = None
    compressive_strength_mpa: float | None = None
    tensile_strength_mpa: float | None = None
    thermal_conductivity_w_mk: float | None = None
    electrical_resistivity_ohm_m: float | None = None
    thermal_expansion_1_per_k: float | None = None
    melting_point_c: float | None = None

    # --- практичні властивості ---
    application: str = ""  # сфера застосування, вільний текст
    outdoor_suitable: bool | None = None  # придатний для вулиці (не лише приміщення)
    frost_resistant: bool | None = None
    water_resistant: bool | None = None
    coverage: Coverage | None = None

    # --- ціна й походження значень ---
    prices: list[PriceInfo] = field(default_factory=list)
    source_note: str = ""  # джерело орієнтовних значень, напр. "EN 206 / каталог виробника"

    def to_core_material(self) -> Material:
        """Місток до `kovadlo.materials.Material` (модуль 1) — саме цей
        тип приймає `Wall.material`. Пов'язати стіну з цим записом бази —
        означає побудувати її матеріал через цей метод (ім'я збігається,
        і за ним `MaterialDatabase.find_by_name` знайде запис назад)."""
        return Material(name=self.name, density_kg_m3=self.density_kg_m3)

    def price_per(self, unit: str) -> PriceInfo | None:
        """Ціна за вказану одиницю ("кг"/"м2"/"м3"/"упаковка"), якщо є."""
        for price in self.prices:
            if price.unit == unit:
                return price
        return None

    def summary_line(self) -> str:
        """Один рядок для списків/звітів: назва, позначення, категорія."""
        designation = f" ({self.designation})" if self.designation else ""
        return f"{self.name}{designation} — {self.category.value}"
