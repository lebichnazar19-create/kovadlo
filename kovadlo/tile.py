"""Плитка — матеріал покриття."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Tile:
    """Плитка: розмір у міліметрах + назва і колір (для звіту/замовлення)."""

    width: float  # мм
    height: float  # мм
    name: str = ""
    color: str = ""

    def __post_init__(self) -> None:
        if self.width <= 0 or self.height <= 0:
            raise ValueError("Розміри плитки мають бути додатними")

    @property
    def area_mm2(self) -> float:
        return self.width * self.height
