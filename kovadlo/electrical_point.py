"""Точка споживання електроенергії (чи щиток) на плані."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .geometry import Point


class PointKind(Enum):
    """Тип точки на плані електромережі."""

    SOCKET = "розетка"
    SWITCH = "вимикач"
    LIGHT = "світильник"
    STOVE = "плита"
    BOILER = "бойлер"
    PANEL = "щиток"
    WASHER = "пральна машина"
    DISHWASHER = "посудомийка"
    MICROWAVE = "мікрохвильовка"
    FRIDGE = "холодильник"
    OVEN = "духовка"
    AC = "кондиціонер"


# Типова потужність за замовчуванням, Вт — орієнтовні значення для
# попереднього розрахунку. Фактична потужність конкретного приладу
# завжди має пріоритет: передайте її явно в `ConsumptionPoint(power_w=...)`.
DEFAULT_POWER_W: dict[PointKind, float] = {
    PointKind.SOCKET: 100.0,  # умовне навантаження одного посадкового місця розетки
    PointKind.SWITCH: 0.0,  # комутаційний апарат — сам не споживає
    PointKind.LIGHT: 60.0,  # типовий світильник
    PointKind.STOVE: 7000.0,  # побутова електроплита/варильна поверхня
    PointKind.BOILER: 2000.0,  # побутовий водонагрівач
    PointKind.PANEL: 0.0,
    PointKind.WASHER: 2200.0,
    PointKind.DISHWASHER: 2000.0,
    PointKind.MICROWAVE: 1200.0,
    PointKind.FRIDGE: 300.0,
    PointKind.OVEN: 3500.0,
    PointKind.AC: 1500.0,  # щиток — вузол розподілу, а не споживач
}


@dataclass
class ConsumptionPoint:
    """Точка споживання (або щиток) на плані.

    `power_w=None` означає типове значення за `kind` (див. `DEFAULT_POWER_W`).
    """

    name: str
    kind: PointKind
    position: Point
    power_w: float | None = None

    def __post_init__(self) -> None:
        if self.power_w is None:
            self.power_w = DEFAULT_POWER_W[self.kind]
        if self.power_w < 0:
            raise ValueError("Потужність не може бути від'ємною")
