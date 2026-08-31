"""
Датчики (модуль 13): тип, робочий діапазон, напруга живлення, тип
виходу, струм споживання; зв'язок з електропроводкою (модуль 4).

Той самий підхід, що й у модулі 12 для двигуна (`motor.to_consumption_point`):
у `PointKind` (модуль 4, ядро) немає окремого типу "датчик" — ядро
незмінне, тож датчик стає точкою споживання типу `PointKind.SOCKET` з
реальною потужністю з паспортних напруги й струму.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .electrical_point import ConsumptionPoint, PointKind
from .geometry import Point


class SensorKind(Enum):
    """Тип датчика."""

    LIMIT_SWITCH = "кінцевий вимикач"
    BUTTON = "кнопка"
    MOTION = "датчик руху"
    DISTANCE = "датчик відстані"
    TEMPERATURE = "датчик температури"
    PHOTOCELL = "фотоелемент"
    ENCODER = "енкодер"


class OutputType(Enum):
    """Тип виходу датчика."""

    DIGITAL = "цифровий"
    ANALOG = "аналоговий"


@dataclass(kw_only=True)
class Sensor:
    """Датчик: тип, діапазон (якщо застосовний), електричні параметри.

    `range_min`/`range_max` — робочий діапазон у власних одиницях
    датчика (`unit`, напр. "мм" для дальноміра, "°C" для термодатчика);
    `None` для датчиків без вимірюваного діапазону (кнопка, кінцевик —
    лише "натиснуто"/"ні").
    """

    name: str
    kind: SensorKind
    output_type: OutputType
    voltage_v: float
    current_a: float
    range_min: float | None = None
    range_max: float | None = None
    unit: str = ""

    def __post_init__(self) -> None:
        if self.voltage_v <= 0:
            raise ValueError("Напруга живлення датчика має бути додатною")
        if self.current_a < 0:
            raise ValueError("Струм споживання не може бути від'ємним")
        if self.range_min is not None and self.range_max is not None and self.range_min > self.range_max:
            raise ValueError("range_min не може бути більшим за range_max")

    @property
    def power_w(self) -> float:
        """Споживана потужність, Вт: P = U·I."""
        return self.voltage_v * self.current_a

    def to_consumption_point(self, position: Point, name: str | None = None) -> ConsumptionPoint:
        """Місток до модуля 4: датчик — точка споживання з реальною
        потужністю (`PointKind.SOCKET` — найближчий наявний тип, ядро
        модуля 4 незмінне, див. докстрінг модуля)."""
        return ConsumptionPoint(name=name or self.name, kind=PointKind.SOCKET, position=position, power_w=self.power_w)
