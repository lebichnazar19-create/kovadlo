"""
Фабрики стандартних посадкових місць (footprint) — готують `Footprint` з
координатами виводів за типовими промисловими кроками, щоб не рахувати
їх вручну для кожного компонента.
"""

from __future__ import annotations

from .geometry import Point
from .pcb_component import Footprint, Pin

# Стандартні кроки (pitch) у мм — типові промислові значення.
DIP_PITCH_MM = 2.54  # крок виводів DIP (0.1")
DIP_ROW_SPACING_MM = 7.62  # відстань між рядами DIP-8...DIP-16 (0.3")
SOIC_PITCH_MM = 1.27  # крок виводів SOIC (0.05")
SOIC_ROW_SPACING_MM = 5.30  # типова відстань між рядами SOIC (JEDEC MS-012)
THT_RESISTOR_SPACING_MM = 10.0  # типова відстань між виводами THT-резистора (1/4 Вт)
CONNECTOR_PITCH_MM = 2.54  # типовий крок однорядного роз'єму (0.1")


def dip_footprint(pin_count: int, *, pitch: float = DIP_PITCH_MM, row_spacing: float = DIP_ROW_SPACING_MM) -> Footprint:
    """DIP-корпус: два ряди виводів, нумерація проти годинникової стрілки
    від верхнього лівого виводу (як на реальній мікросхемі, якщо дивитись
    зверху, виїмка/ключ — зліва).

    Ряд 1 (виводи 1..pin_count/2) — знизу зліва направо;
    ряд 2 (виводи pin_count/2+1..pin_count) — згори справа наліво.
    """
    if pin_count < 2 or pin_count % 2 != 0:
        raise ValueError("Кількість виводів DIP-корпусу має бути парною і не меншою за 2")
    half = pin_count // 2
    pins: list[Pin] = []
    for i in range(half):
        pins.append(Pin(number=i + 1, name=f"P{i + 1}", position=Point(i * pitch, 0.0)))
    for i in range(half):
        pin_number = pin_count - i
        x = i * pitch
        pins.append(Pin(number=pin_number, name=f"P{pin_number}", position=Point(x, row_spacing)))
    return Footprint(name=f"DIP-{pin_count}", pins=pins)


def soic_footprint(
    pin_count: int, *, pitch: float = SOIC_PITCH_MM, row_spacing: float = SOIC_ROW_SPACING_MM
) -> Footprint:
    """SOIC-корпус: та сама нумерація, що й DIP, лише з дрібнішим кроком
    (SMD-монтаж)."""
    if pin_count < 2 or pin_count % 2 != 0:
        raise ValueError("Кількість виводів SOIC-корпусу має бути парною і не меншою за 2")
    half = pin_count // 2
    pins: list[Pin] = []
    for i in range(half):
        pins.append(Pin(number=i + 1, name=f"P{i + 1}", position=Point(i * pitch, 0.0)))
    for i in range(half):
        pin_number = pin_count - i
        x = i * pitch
        pins.append(Pin(number=pin_number, name=f"P{pin_number}", position=Point(x, row_spacing)))
    return Footprint(name=f"SOIC-{pin_count}", pins=pins)


def two_pin_footprint(name: str, *, spacing: float = THT_RESISTOR_SPACING_MM) -> Footprint:
    """Двовивідний THT-компонент (резистор, конденсатор, діод, світлодіод):
    виводи 1 і 2 на відстані `spacing` уздовж осі X.

    Для полярних компонентів (діод, світлодіод, електролітичний
    конденсатор) вивід 1 — анод/позитивний, вивід 2 — катод/негативний
    за домовленістю цього модуля.
    """
    return Footprint(
        name=name,
        pins=[
            Pin(number=1, name="1", position=Point(0.0, 0.0)),
            Pin(number=2, name="2", position=Point(spacing, 0.0)),
        ],
    )


def connector_footprint(pin_count: int, *, pitch: float = CONNECTOR_PITCH_MM) -> Footprint:
    """Однорядний роз'єм з `pin_count` виводами вздовж осі X."""
    if pin_count < 1:
        raise ValueError("Роз'єм має містити хоча б один вивід")
    pins = [Pin(number=i + 1, name=f"P{i + 1}", position=Point(i * pitch, 0.0)) for i in range(pin_count)]
    return Footprint(name=f"CONN-{pin_count}", pins=pins)


def to92_footprint(*, spacing: float = 2.54) -> Footprint:
    """Транзистор у корпусі TO-92: три виводи в один ряд (E, B, C)."""
    return Footprint(
        name="TO-92",
        pins=[
            Pin(number=1, name="E", position=Point(0.0, 0.0)),
            Pin(number=2, name="B", position=Point(spacing, 0.0)),
            Pin(number=3, name="C", position=Point(2 * spacing, 0.0)),
        ],
    )
