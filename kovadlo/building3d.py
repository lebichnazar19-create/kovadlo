"""Будівля (модуль 10): список поверхів, перевірка збігу контурів між ними."""

from __future__ import annotations

from dataclasses import dataclass, field

from .geometry import Point


@dataclass
class Storey:
    """Поверх будівлі: контур (модуль 1) і висота, мм."""

    name: str
    contour: list[Point]
    height_mm: float

    def __post_init__(self) -> None:
        if len(self.contour) < 3:
            raise ValueError("Контур поверху має містити щонайменше 3 точки")
        if self.height_mm <= 0:
            raise ValueError("Висота поверху має бути додатною")


def contours_match(a: list[Point], b: list[Point], tolerance_mm: float = 1.0) -> bool:
    """Чи збігаються два контури геометрично — та сама форма з
    точністю до `tolerance_mm`, можливо з іншої стартової вершини й
    напрямку обходу (за годинниковою/проти)."""
    if len(a) != len(b):
        return False
    n = len(a)
    for offset in range(n):
        for use_reversed in (False, True):
            sequence = list(reversed(b)) if use_reversed else b
            rotated = sequence[offset:] + sequence[:offset]
            if all(p.distance_to(q) <= tolerance_mm for p, q in zip(a, rotated)):
                return True
    return False


@dataclass
class Building:
    """Будівля: список поверхів знизу вгору."""

    storeys: list[Storey] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.storeys:
            raise ValueError("Будівля має містити хоча б один поверх")

    @property
    def total_height_mm(self) -> float:
        return sum(storey.height_mm for storey in self.storeys)

    def base_elevation_mm(self, index: int) -> float:
        """Висота підлоги поверху `index` над рівнем підлоги першого поверху."""
        if index < 0 or index >= len(self.storeys):
            raise IndexError(f"Немає поверху з індексом {index}")
        return sum(storey.height_mm for storey in self.storeys[:index])

    def contour_mismatches(self, tolerance_mm: float = 1.0) -> list[tuple[int, int]]:
        """Пари індексів СУСІДНІХ поверхів, чиї контури НЕ збігаються."""
        mismatches = []
        for i in range(len(self.storeys) - 1):
            if not contours_match(self.storeys[i].contour, self.storeys[i + 1].contour, tolerance_mm):
                mismatches.append((i, i + 1))
        return mismatches

    def contours_all_match(self, tolerance_mm: float = 1.0) -> bool:
        return not self.contour_mismatches(tolerance_mm)
