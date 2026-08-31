"""
Дах (модуль 10): односхилий і двосхилий, за кутом нахилу.

Спрощення: дах будується лише для ПРЯМОКУТНОГО контуру (footprint) —
довільні полігони (Г-подібні кімнати тощо) поза межами цього модуля,
геометрія похилої покрівлі над непрямокутним контуром істотно
складніша (вимагає розбиття на скати з ребрами/ендовами).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .geometry import Point
from .geometry3d import Face, Point3


class RoofType(Enum):
    """Тип даху."""

    SHED = "односхилий"
    GABLE = "двосхилий"


def _rectangle_bounds(contour: list[Point]) -> tuple[float, float, float, float]:
    xs = [p.x for p in contour]
    zs = [p.z for p in contour]
    return min(xs), min(zs), max(xs), max(zs)


def _is_axis_aligned_rectangle(contour: list[Point]) -> bool:
    if len(contour) != 4:
        return False
    min_x, min_z, max_x, max_z = _rectangle_bounds(contour)
    expected = {
        (round(min_x, 3), round(min_z, 3)),
        (round(max_x, 3), round(min_z, 3)),
        (round(max_x, 3), round(max_z, 3)),
        (round(min_x, 3), round(max_z, 3)),
    }
    actual = {(round(p.x, 3), round(p.z, 3)) for p in contour}
    return actual == expected


@dataclass
class Roof:
    """Дах як список плоских схилів (граней)."""

    roof_type: RoofType
    slope_deg: float
    faces: list[Face]
    ridge_rise_mm: float  # підйом гребеня над карнизом (базовою висотою), мм

    @property
    def area_m2(self) -> float:
        return sum(face.area_m2 for face in self.faces)


def _check_rectangle_and_slope(contour: list[Point], slope_deg: float) -> tuple[float, float, float, float]:
    if not _is_axis_aligned_rectangle(contour):
        raise ValueError("Дах (у цьому модулі) будується лише для прямокутного контуру, паралельного осям")
    if not (0 < slope_deg < 90):
        raise ValueError("Кут нахилу має бути в діапазоні (0, 90) градусів")
    return _rectangle_bounds(contour)


def build_shed_roof(contour: list[Point], base_height_mm: float, slope_deg: float, *, low_side: str = "south") -> Roof:
    """Односхилий дах над прямокутним контуром: один край карниз (нижче),
    протилежний — вище на `span · tan(slope_deg)`.

    `low_side` — котрий край контуру нижній: "south" (мін. z), "north"
    (макс. z), "west" (мін. x) чи "east" (макс. x); підйом — у
    протилежний бік.
    """
    min_x, min_z, max_x, max_z = _check_rectangle_and_slope(contour, slope_deg)

    if low_side in ("south", "north"):
        span_mm = max_z - min_z
    elif low_side in ("west", "east"):
        span_mm = max_x - min_x
    else:
        raise ValueError(f"Невідома сторона low_side={low_side!r} (south/north/west/east)")

    rise_mm = span_mm * math.tan(math.radians(slope_deg))
    low_y, high_y = base_height_mm, base_height_mm + rise_mm

    if low_side == "south":
        pts = [(min_x, low_y, min_z), (max_x, low_y, min_z), (max_x, high_y, max_z), (min_x, high_y, max_z)]
    elif low_side == "north":
        pts = [(min_x, high_y, min_z), (max_x, high_y, min_z), (max_x, low_y, max_z), (min_x, low_y, max_z)]
    elif low_side == "west":
        pts = [(min_x, low_y, min_z), (min_x, low_y, max_z), (max_x, high_y, max_z), (max_x, high_y, min_z)]
    else:  # east
        pts = [(max_x, low_y, min_z), (max_x, low_y, max_z), (min_x, high_y, max_z), (min_x, high_y, min_z)]

    face = Face(points=[Point3(x, y, z) for x, y, z in pts])
    return Roof(roof_type=RoofType.SHED, slope_deg=slope_deg, faces=[face], ridge_rise_mm=rise_mm)


def build_gable_roof(contour: list[Point], base_height_mm: float, slope_deg: float, *, ridge_along: str = "x") -> Roof:
    """Двосхилий дах над прямокутним контуром: гребінь посередині,
    паралельно осі `ridge_along` ("x" чи "z"), два симетричні схили від
    карнизів до гребеня."""
    min_x, min_z, max_x, max_z = _check_rectangle_and_slope(contour, slope_deg)
    low_y = base_height_mm

    if ridge_along == "x":
        half_span_mm = (max_z - min_z) / 2
        mid_z = (min_z + max_z) / 2
        rise_mm = half_span_mm * math.tan(math.radians(slope_deg))
        ridge_y = low_y + rise_mm
        face1 = Face(
            points=[
                Point3(min_x, low_y, min_z),
                Point3(max_x, low_y, min_z),
                Point3(max_x, ridge_y, mid_z),
                Point3(min_x, ridge_y, mid_z),
            ]
        )
        face2 = Face(
            points=[
                Point3(min_x, ridge_y, mid_z),
                Point3(max_x, ridge_y, mid_z),
                Point3(max_x, low_y, max_z),
                Point3(min_x, low_y, max_z),
            ]
        )
    elif ridge_along == "z":
        half_span_mm = (max_x - min_x) / 2
        mid_x = (min_x + max_x) / 2
        rise_mm = half_span_mm * math.tan(math.radians(slope_deg))
        ridge_y = low_y + rise_mm
        face1 = Face(
            points=[
                Point3(min_x, low_y, min_z),
                Point3(min_x, low_y, max_z),
                Point3(mid_x, ridge_y, max_z),
                Point3(mid_x, ridge_y, min_z),
            ]
        )
        face2 = Face(
            points=[
                Point3(mid_x, ridge_y, min_z),
                Point3(mid_x, ridge_y, max_z),
                Point3(max_x, low_y, max_z),
                Point3(max_x, low_y, min_z),
            ]
        )
    else:
        raise ValueError(f"Невідома вісь ridge_along={ridge_along!r} ('x' чи 'z')")

    return Roof(roof_type=RoofType.GABLE, slope_deg=slope_deg, faces=[face1, face2], ridge_rise_mm=rise_mm)
