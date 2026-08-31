"""Розкладка плитки: стартова точка, зсув рядів, кут."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .geometry import Point

ALLOWED_ANGLES = (0.0, 45.0)


class RowOffset(Enum):
    """Зсув кожного другого ряду плитки відносно попереднього, як частка ширини плитки."""

    NONE = 0.0
    HALF = 0.5
    THIRD = 1.0 / 3.0


@dataclass(frozen=True)
class TileLayout:
    """Розкладка плитки на поверхні.

    start      — точка (u, v) у локальних мм-координатах поверхні, де
                 починається плитка розкладки (кут першого ряду й стовпця).
    row_offset — зсув непарних рядів відносно парних (0%, 50% або 1/3).
    angle      — кут розкладки відносно осей поверхні: 0° (рівна) або
                 45° (по діагоналі).
    """

    start: Point = field(default_factory=lambda: Point(0.0, 0.0))
    row_offset: RowOffset = RowOffset.NONE
    angle: float = 0.0

    def __post_init__(self) -> None:
        if self.angle not in ALLOWED_ANGLES:
            raise ValueError(f"Кут розкладки має бути одним з {ALLOWED_ANGLES}, отримано {self.angle}")
