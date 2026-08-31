"""Перекриття і підлога (модуль 10): горизонтальна плита заданої товщини."""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import MM2_PER_M2, Point, polygon_area
from .geometry3d import Face, Point3
from .material_spec import MaterialSpec


@dataclass
class Slab:
    """Горизонтальна плита (перекриття чи підлога): контур кімнати
    (модуль 1) на базовій висоті `base_height_mm`, товщина `thickness_mm`."""

    contour: list[Point]
    base_height_mm: float
    thickness_mm: float
    material: MaterialSpec | None = None

    def __post_init__(self) -> None:
        if len(self.contour) < 3:
            raise ValueError("Контур плити має містити щонайменше 3 точки")
        if self.thickness_mm <= 0:
            raise ValueError("Товщина плити має бути додатною")

    @property
    def area_m2(self) -> float:
        return polygon_area(self.contour) / MM2_PER_M2

    @property
    def volume_m3(self) -> float:
        return self.area_m2 * (self.thickness_mm / 1000.0)

    def bottom_face(self) -> Face:
        return Face(points=[Point3.from_plan(p, self.base_height_mm) for p in self.contour])

    def top_face(self) -> Face:
        return Face(points=[Point3.from_plan(p, self.base_height_mm + self.thickness_mm) for p in self.contour])
