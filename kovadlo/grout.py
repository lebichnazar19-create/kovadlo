"""Фуга — шов між плитками."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Grout:
    """Фуга: ширина шва в міліметрах + колір."""

    width_mm: float
    color: str = ""

    def __post_init__(self) -> None:
        if self.width_mm < 0:
            raise ValueError("Ширина фуги не може бути від'ємною")
