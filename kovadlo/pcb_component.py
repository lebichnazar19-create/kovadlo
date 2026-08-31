"""
Електронний компонент: назва, тип, номінал, посадкове місце (footprint).

Це базова "картка деталі" модуля 6 — сама по собі вона не описує ні схему
(див. `pcb_netlist.py`), ні плату (див. `pcb_board.py`), а лише те, що
це за компонент і де на ньому фізично розташовані виводи.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .geometry import Point


class ComponentKind(Enum):
    """Тип електронного компонента."""

    RESISTOR = "резистор"
    CAPACITOR = "конденсатор"
    DIODE = "діод"
    TRANSISTOR = "транзистор"
    IC = "мікросхема"
    CONNECTOR = "роз'єм"
    LED = "світлодіод"


class Unit(Enum):
    """Одиниця номіналу компонента."""

    OHM = "Ом"
    FARAD = "Ф"
    VOLT = "В"
    AMPERE = "А"


@dataclass(frozen=True)
class Pin:
    """Вивід компонента: номер, назва, позиція відносно посадкового місця, мм."""

    number: int
    name: str
    position: Point


@dataclass
class Footprint:
    """Посадкове місце компонента: назва (напр. "DIP-8", "0805") і
    координати кожного виводу відносно локального початку координат
    компонента (0, 0) — до розміщення на платі й повороту."""

    name: str
    pins: list[Pin] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.pins:
            raise ValueError("Посадкове місце має містити хоча б один вивід")
        numbers = [p.number for p in self.pins]
        if len(set(numbers)) != len(numbers):
            raise ValueError("Номери виводів посадкового місця мають бути унікальними")

    @property
    def pin_count(self) -> int:
        return len(self.pins)

    def pin(self, number: int) -> Pin:
        for p in self.pins:
            if p.number == number:
                return p
        raise KeyError(f"Немає виводу №{number} у посадковому місці «{self.name}»")


@dataclass
class Component:
    """Електронний компонент: назва, тип, номінал, посадкове місце.

    `value`/`unit` — номінал (Ом/Ф/В/А); для компонентів без єдиного
    номіналу (мікросхема, роз'єм, транзистор) лишаються `None`.
    """

    reference: str  # позначення на схемі/платі, напр. "R1", "U1"
    name: str
    kind: ComponentKind
    footprint: Footprint
    value: float | None = None
    unit: Unit | None = None

    def __post_init__(self) -> None:
        if (self.value is None) != (self.unit is None):
            raise ValueError("value і unit мають бути задані разом або обидва відсутні")

    @property
    def pin_count(self) -> int:
        return self.footprint.pin_count

    def value_str(self) -> str:
        """Номінал у зручному вигляді з SI-префіксом, напр. "4.7 кОм", "100 нФ"."""
        if self.value is None or self.unit is None:
            return "—"
        number, prefix = _split_value(self.value)
        return f"{number} {prefix}{self.unit.value}"


# SI-префікси від більшого до меншого — перший поріг, якому задовольняє
# величина, визначає її запис (стандартна "інженерна" форма запису).
_SI_PREFIXES: list[tuple[float, str]] = [
    (1e9, "Г"),
    (1e6, "М"),
    (1e3, "к"),
    (1.0, ""),
    (1e-3, "м"),
    (1e-6, "мк"),
    (1e-9, "н"),
    (1e-12, "п"),
]


def _split_value(value: float) -> tuple[str, str]:
    """Розкладає число на (мантиса_як_рядок, SI-префікс)."""
    if value == 0:
        return "0", ""
    magnitude = abs(value)
    for threshold, prefix in _SI_PREFIXES:
        if magnitude >= threshold:
            return f"{value / threshold:g}", prefix
    return f"{value:g}", ""
