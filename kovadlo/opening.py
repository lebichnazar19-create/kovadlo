"""Отвори у стіні: вікно і двері (модуль 10)."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from .geometry import MM2_PER_M2


class OpeningKind(Enum):
    """Тип отвору в стіні."""

    WINDOW = "вікно"
    DOOR = "двері"


@dataclass(frozen=True)
class Opening:
    """Прямокутний виріз у стіні.

    `offset_mm` — відстань уздовж стіни від точки `start` до лівого
    краю отвору; `sill_height_mm` — висота нижнього краю над підлогою
    (0 для дверей, типово 900 для вікна); `width_mm`/`height_mm` —
    розміри отвору. Належність отвору конкретній стіні й перевірка, що
    він у неї вписується, — на рівні `Wall3D` (`wall3d.py`), бо саме
    там відомі довжина й висота стіни.
    """

    kind: OpeningKind
    offset_mm: float
    sill_height_mm: float
    width_mm: float
    height_mm: float
    name: str = ""

    def __post_init__(self) -> None:
        if self.width_mm <= 0 or self.height_mm <= 0:
            raise ValueError("Розміри отвору мають бути додатними")
        if self.offset_mm < 0 or self.sill_height_mm < 0:
            raise ValueError("Зсув уздовж стіни й висота підвіконня не можуть бути від'ємними")

    @property
    def area_mm2(self) -> float:
        return self.width_mm * self.height_mm

    @property
    def area_m2(self) -> float:
        return self.area_mm2 / MM2_PER_M2

    def label(self) -> str:
        return self.name or self.kind.value
