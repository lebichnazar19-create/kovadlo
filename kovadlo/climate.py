"""
Кліматизація (8.3): тепловтрати приміщення, тепловий баланс, підбір
потужності обігріву/охолодження.

Тепловтрати через огородження — Q = U · A · ΔT (Вт), де U = 1/R
(з теплопровідності матеріалів модуля 7 і площ модуля 1/`Wall.area_m2`,
`Room.floor_area_m2`), плюс орієнтовні тепловтрати на вентиляцію
Q = c · V̇ · ΔT (пов'язує з витратою повітря з модуля 8.2).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .climate_norms import (
    AIR_VOLUMETRIC_HEAT_CAPACITY_WH_M3K,
    STANDARD_AC_POWERS_KW,
    STANDARD_RADIATOR_POWERS_W,
)


@dataclass(frozen=True)
class BuildingElement:
    """Елемент огородження (стіна/вікно/дах): площа й коефіцієнт
    теплопередачі. `u_value_w_m2k` зазвичай береться як 1/R, де R —
    сумарний опір теплопередачі шарів матеріалів (модуль 7, див.
    `insulation.py`)."""

    name: str
    area_m2: float
    u_value_w_m2k: float

    def __post_init__(self) -> None:
        if self.area_m2 <= 0:
            raise ValueError("Площа елемента має бути додатною")
        if self.u_value_w_m2k <= 0:
            raise ValueError("Коефіцієнт теплопередачі має бути додатним")

    def heat_loss_w(self, delta_t_k: float) -> float:
        return self.area_m2 * self.u_value_w_m2k * delta_t_k


def transmission_heat_loss_w(elements: list[BuildingElement], delta_t_k: float) -> float:
    """Сумарні тепловтрати трансмісією через усі елементи огородження, Вт."""
    return sum(element.heat_loss_w(delta_t_k) for element in elements)


def ventilation_heat_loss_w(airflow_m3_h: float, delta_t_k: float) -> float:
    """Тепловтрати на підігрів припливного повітря, Вт: Q = c · V̇ · ΔT."""
    if airflow_m3_h < 0:
        raise ValueError("Витрата повітря не може бути від'ємною")
    return AIR_VOLUMETRIC_HEAT_CAPACITY_WH_M3K * airflow_m3_h * delta_t_k


@dataclass
class HeatBalance:
    """Тепловий баланс приміщення: тепловтрати трансмісією + вентиляцією."""

    elements: list[BuildingElement] = field(default_factory=list)
    delta_t_k: float = 0.0
    airflow_m3_h: float = 0.0

    @property
    def transmission_loss_w(self) -> float:
        return transmission_heat_loss_w(self.elements, self.delta_t_k)

    @property
    def ventilation_loss_w(self) -> float:
        return ventilation_heat_loss_w(self.airflow_m3_h, self.delta_t_k)

    @property
    def total_loss_w(self) -> float:
        return self.transmission_loss_w + self.ventilation_loss_w


def select_radiator_power_w(required_w: float) -> float:
    """Найменша стандартна потужність радіатора, що покриває `required_w`."""
    for power in STANDARD_RADIATOR_POWERS_W:
        if power >= required_w:
            return power
    raise ValueError(
        f"Потрібна потужність {required_w:.0f} Вт перевищує найбільший стандартний "
        f"радіатор у ряду ({STANDARD_RADIATOR_POWERS_W[-1]:.0f} Вт) — потрібно кілька приладів"
    )


def select_ac_power_kw(required_w: float) -> float:
    """Найменша стандартна потужність кондиціонера, кВт, що покриває `required_w`."""
    required_kw = required_w / 1000.0
    for power in STANDARD_AC_POWERS_KW:
        if power >= required_kw:
            return power
    raise ValueError(
        f"Потрібна потужність {required_kw:.2f} кВт перевищує найбільший стандартний "
        f"кондиціонер у ряду ({STANDARD_AC_POWERS_KW[-1]:g} кВт)"
    )
