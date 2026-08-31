"""
Порівняння матеріалів за ціною й властивостями на одиницю задачі.

Головний практичний приклад — теплотехнічний розрахунок: скільки має
бути завтовшки шар матеріалу, щоб дати потрібний опір теплопередачі
R = d / λ (спрощено, лише сам шар, без опорів тепловіддачі на
поверхнях — orientовний інженерний розрахунок для порівняння
матеріалів, не повний розрахунок за EN ISO 6946), і скільки це
орієнтовно коштує на 1 м² стіни.
"""

from __future__ import annotations

from dataclasses import dataclass

from .material_spec import MaterialSpec

MM_PER_M = 1000.0


@dataclass
class ThermalLayerOption:
    """Варіант шару матеріалу, що дає потрібний опір теплопередачі."""

    material: MaterialSpec
    required_resistance_m2k_w: float
    thickness_m: float
    cost_per_m2_pln: float | None
    cost_note: str

    @property
    def thickness_mm(self) -> float:
        return self.thickness_m * MM_PER_M


def thermal_layer_option(material: MaterialSpec, required_resistance_m2k_w: float) -> ThermalLayerOption:
    """Товщина й орієнтовна ціна за м² шару з `material`, що дає
    потрібний опір теплопередачі `required_resistance_m2k_w` (R = d/λ,
    звідси d = R·λ)."""
    if required_resistance_m2k_w <= 0:
        raise ValueError("Потрібний опір теплопередачі має бути додатним")
    if material.thermal_conductivity_w_mk is None:
        raise ValueError(f"У матеріалу «{material.name}» не задана теплопровідність")

    thickness_m = required_resistance_m2k_w * material.thermal_conductivity_w_mk
    cost, note = _cost_per_m2(material, thickness_m)

    return ThermalLayerOption(
        material=material,
        required_resistance_m2k_w=required_resistance_m2k_w,
        thickness_m=thickness_m,
        cost_per_m2_pln=cost,
        cost_note=note,
    )


def _cost_per_m2(material: MaterialSpec, thickness_m: float) -> tuple[float | None, str]:
    """Орієнтовна ціна за 1 м² шару заданої товщини — з тієї ціни
    матеріалу (за м³, за кг чи за м² при відомій довідковій товщині),
    яку вдається однозначно перерахувати."""
    price_m3 = material.price_per("м3")
    if price_m3 is not None:
        cost = price_m3.price_pln * thickness_m
        return cost, f"з ціни {price_m3}"

    price_kg = material.price_per("кг")
    if price_kg is not None and material.density_kg_m3 is not None:
        mass_per_m2 = thickness_m * material.density_kg_m3
        cost = price_kg.price_pln * mass_per_m2
        return cost, f"з ціни {price_kg}, маса шару {mass_per_m2:.2f} кг/м²"

    price_m2 = material.price_per("м2")
    if price_m2 is not None and price_m2.reference_thickness_mm:
        scale = (thickness_m * MM_PER_M) / price_m2.reference_thickness_mm
        cost = price_m2.price_pln * scale
        return cost, f"з ціни {price_m2}, масштабовано з {price_m2.reference_thickness_mm:g} мм"

    if price_m2 is not None:
        return price_m2.price_pln, f"з ціни {price_m2} (довідкова товщина невідома — без масштабування)"

    return None, "у матеріалу немає ціни за м³, кг чи м², з якої можна порахувати вартість шару"


@dataclass
class ThermalComparison:
    """Порівняння двох матеріалів для однакової задачі (опір теплопередачі)."""

    option_a: ThermalLayerOption
    option_b: ThermalLayerOption

    @property
    def cheaper(self) -> ThermalLayerOption | None:
        """Дешевший варіант на 1 м², якщо ціну відомо для обох."""
        a, b = self.option_a.cost_per_m2_pln, self.option_b.cost_per_m2_pln
        if a is None or b is None:
            return None
        return self.option_a if a <= b else self.option_b

    def __str__(self) -> str:
        lines = [
            f"Потрібний опір теплопередачі: {self.option_a.required_resistance_m2k_w:g} м²·К/Вт",
            f"  {self.option_a.material.name}: товщина {self.option_a.thickness_mm:.0f} мм, "
            f"{_cost_str(self.option_a)}",
            f"  {self.option_b.material.name}: товщина {self.option_b.thickness_mm:.0f} мм, "
            f"{_cost_str(self.option_b)}",
        ]
        cheaper = self.cheaper
        if cheaper is not None:
            lines.append(f"  Дешевше: {cheaper.material.name}")
        return "\n".join(lines)


def _cost_str(option: ThermalLayerOption) -> str:
    if option.cost_per_m2_pln is None:
        return "ціна невідома"
    return f"≈{option.cost_per_m2_pln:.2f} зл/м² ({option.cost_note})"


def conductor_resistance_ohm(material: MaterialSpec, length_m: float, cross_section_mm2: float) -> float:
    """Опір провідника (дорожки, кабельної жили) довжиною `length_m` і
    перерізом `cross_section_mm2` з матеріалу бази — R = ρ·L/A.

    Використовує `MaterialSpec.electrical_resistivity_ohm_m` (категорія
    "провідники"/"метали"); саме так дорожка (модуль 6) чи кабель
    (модуль 4) "посилаються" на базу матеріалів — вибором запису й
    підстановкою його опору в цю формулу, а не через нове поле в
    ядрових класах.
    """
    if length_m <= 0 or cross_section_mm2 <= 0:
        raise ValueError("Довжина й переріз мають бути додатними")
    if material.electrical_resistivity_ohm_m is None:
        raise ValueError(f"У матеріалу «{material.name}» не задано питомий електричний опір")
    resistivity_ohm_mm2_per_m = material.electrical_resistivity_ohm_m * 1e6  # Ом·м -> Ом·мм²/м
    return resistivity_ohm_mm2_per_m * length_m / cross_section_mm2


def compare_for_thermal_resistance(
    material_a: MaterialSpec, material_b: MaterialSpec, required_resistance_m2k_w: float
) -> ThermalComparison:
    """Порівнює два матеріали за товщиною й орієнтовною ціною за 1 м²
    шару, що дає той самий потрібний опір теплопередачі."""
    return ThermalComparison(
        option_a=thermal_layer_option(material_a, required_resistance_m2k_w),
        option_b=thermal_layer_option(material_b, required_resistance_m2k_w),
    )
