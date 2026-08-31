"""
Пожежна безпека (8.5): датчики як точки, автоматична розстановка по
контуру кімнати, довжина шлейфу, зв'язок з проводкою модуля 4.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .electrical_point import ConsumptionPoint, PointKind
from .fire_safety_norms import COVERAGE_AREA_M2, MAX_SPACING_M, WALL_CLEARANCE_M, DetectorKind
from .geometry import MM_PER_M, Point, polygon_perimeter
from .room import Room


@dataclass
class FireDetector:
    """Пожежний датчик як точка на плані."""

    name: str
    kind: DetectorKind
    position: Point

    def to_consumption_point(self, power_w: float = 0.5) -> ConsumptionPoint:
        """Місток до модуля 4. У модулі 4 немає окремого типу точки
        "датчик" (`PointKind`: SOCKET/SWITCH/LIGHT/STOVE/BOILER/PANEL), а
        ядро модуля 4 змінювати не можна — тому використовуємо
        `PointKind.SWITCH` як найближчий за суттю (малопотужний
        сигнальний пристрій, не силове навантаження)."""
        return ConsumptionPoint(name=self.name, kind=PointKind.SWITCH, position=self.position, power_w=power_w)


def detectors_needed(kind: DetectorKind, area_m2: float, perimeter_m: float) -> int:
    """Кількість датчиків: не менше, ніж треба для покриття площі, і не
    менше, ніж треба, щоб дотримати максимальну відстань між датчиками
    вздовж периметра."""
    if area_m2 <= 0:
        raise ValueError("Площа приміщення має бути додатною")
    by_area = math.ceil(area_m2 / COVERAGE_AREA_M2[kind])
    by_spacing = math.ceil(perimeter_m / MAX_SPACING_M[kind]) if perimeter_m > 0 else 1
    return max(by_area, by_spacing, 1)


def _point_at_arc_length(contour: list[Point], target_arc_mm: float) -> tuple[Point, Point, Point]:
    """Точка на контурі на відстані `target_arc_mm` уздовж периметра
    (від першої вершини), плюс кінці ребра, на якому вона лежить."""
    n = len(contour)
    remaining = target_arc_mm
    for i in range(n):
        a, b = contour[i], contour[(i + 1) % n]
        seg_len = a.distance_to(b)
        if remaining <= seg_len or i == n - 1:
            t = 0.0 if seg_len == 0 else max(0.0, min(1.0, remaining / seg_len))
            point = Point(a.x + (b.x - a.x) * t, a.z + (b.z - a.z) * t)
            return point, a, b
        remaining -= seg_len
    return contour[0], contour[0], contour[1 % n]


def place_detectors_along_contour(contour: list[Point], count: int, *, wall_clearance_m: float) -> list[Point]:
    """Рівномірно розставляє `count` точок уздовж периметра контуру
    (мм, той самий контур, що й у `Room`), кожну зсунуто всередину
    контуру на `wall_clearance_m` (мінімальний відступ від стіни)."""
    if count <= 0:
        raise ValueError("Кількість датчиків має бути додатною")
    perimeter = polygon_perimeter(contour)
    if perimeter <= 0:
        raise ValueError("Контур кімнати має ненульовий периметр")

    centroid = Point(sum(p.x for p in contour) / len(contour), sum(p.z for p in contour) / len(contour))
    clearance_mm = wall_clearance_m * MM_PER_M

    positions: list[Point] = []
    for i in range(count):
        target_arc = perimeter * (i + 0.5) / count
        point, edge_start, edge_end = _point_at_arc_length(contour, target_arc)

        dx, dz = edge_end.x - edge_start.x, edge_end.z - edge_start.z
        length = math.hypot(dx, dz) or 1.0
        nx, nz = -dz / length, dx / length

        to_centroid_x, to_centroid_z = centroid.x - point.x, centroid.z - point.z
        if nx * to_centroid_x + nz * to_centroid_z < 0:
            nx, nz = -nx, -nz  # обираємо нормаль, спрямовану всередину контуру

        positions.append(Point(point.x + nx * clearance_mm, point.z + nz * clearance_mm))
    return positions


def auto_place_detectors(room: Room, kind: DetectorKind, *, wall_clearance_m: float | None = None) -> list[FireDetector]:
    """Автоматична розстановка датчиків заданого типу по контуру кімнати."""
    clearance = WALL_CLEARANCE_M[kind] if wall_clearance_m is None else wall_clearance_m
    perimeter_m = room.perimeter_mm / MM_PER_M
    count = detectors_needed(kind, room.floor_area_m2, perimeter_m)
    positions = place_detectors_along_contour(room.contour, count, wall_clearance_m=clearance)
    return [
        FireDetector(name=f"{kind.value.capitalize()} датчик {i + 1}", kind=kind, position=position)
        for i, position in enumerate(positions)
    ]


def loop_length_m(panel_position: Point, detector_positions: list[Point]) -> float:
    """Довжина шлейфу (петлі) від щитка через усі датчики й назад до
    щитка — типова топологія пожежного шлейфу (на відміну від
    радіальних "домашніх" ланцюгів модуля 4)."""
    if not detector_positions:
        return 0.0
    points = [panel_position, *detector_positions, panel_position]
    return sum(points[i].distance_to(points[i + 1]) for i in range(len(points) - 1)) / MM_PER_M
