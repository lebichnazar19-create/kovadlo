"""
Тривимірна геометрія (модуль 10): точка в просторі й плоска грань.

Система координат узгоджена з планом модуля 1: x, z — та сама
горизонтальна площина (план), y — висота (вертикальна вісь), додана
цим модулем. Усі координати — міліметри, як і в усьому проєкті.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry import MM2_PER_M2, Point


@dataclass(frozen=True)
class Point3:
    """Точка в тривимірному просторі, мм. x, z — план (модуль 1), y — висота."""

    x: float
    y: float
    z: float

    @classmethod
    def from_plan(cls, point: Point, height: float) -> "Point3":
        """Будує Point3 з плоскої точки модуля 1 на заданій висоті `height`."""
        return cls(x=point.x, y=height, z=point.z)

    def to_plan(self) -> Point:
        """Проєкція на план (модуль 1) — висота губиться."""
        return Point(self.x, self.z)

    def distance_to(self, other: "Point3") -> float:
        return math.sqrt((other.x - self.x) ** 2 + (other.y - self.y) ** 2 + (other.z - self.z) ** 2)


@dataclass
class Face:
    """Плоска грань: упорядкований список вершин у 3D (мм).

    Площа рахується за формулою Ньюелла для довільного плоского
    полігону в просторі (через модуль нормалі-суми векторних добутків
    послідовних вершин) — коректно для НЕ обов'язково горизонтальних чи
    вертикальних граней (напр., схилів даху)."""

    points: list[Point3]

    def __post_init__(self) -> None:
        if len(self.points) < 3:
            raise ValueError("Грань має містити щонайменше 3 точки")

    @property
    def area_mm2(self) -> float:
        n = len(self.points)
        nx = ny = nz = 0.0
        for i in range(n):
            a, b = self.points[i], self.points[(i + 1) % n]
            nx += a.y * b.z - a.z * b.y
            ny += a.z * b.x - a.x * b.z
            nz += a.x * b.y - a.y * b.x
        return 0.5 * math.sqrt(nx * nx + ny * ny + nz * nz)

    @property
    def area_m2(self) -> float:
        return self.area_mm2 / MM2_PER_M2
