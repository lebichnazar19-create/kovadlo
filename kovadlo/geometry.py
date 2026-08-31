"""
Базова геометрія: точка на плані, прив'язка кутів (snap) і розрахунки
площі/периметра полігонального контуру.

Система координат — план "згори": X, Z у міліметрах (Y лишається для
висоти й тут не бере участі, оскільки контур і кут — це план поверху).
"""

from __future__ import annotations

import math
from dataclasses import dataclass

MM_PER_M = 1_000.0
MM2_PER_M2 = 1_000_000.0


@dataclass(frozen=True)
class Point:
    """Точка на плані, координати в міліметрах."""

    x: float
    z: float

    def distance_to(self, other: "Point") -> float:
        """Відстань до іншої точки, мм."""
        return math.hypot(other.x - self.x, other.z - self.z)

    def angle_to(self, other: "Point") -> float:
        """Кут напрямку від self до other, градуси в діапазоні [0, 360)."""
        return math.degrees(math.atan2(other.z - self.z, other.x - self.x)) % 360.0


def snap_angle(angle_degrees: float, step: float = 15.0) -> float:
    """Приводить кут до найближчого значення, кратного `step` градусів.

    Результат завжди в діапазоні [0, 360).
    """
    if step <= 0:
        raise ValueError("Крок прив'язки (step) має бути додатним")
    return round(angle_degrees / step) * step % 360.0


def snap_point(origin: Point, target: Point, step: float = 15.0) -> Point:
    """Прив'язує напрямок з `origin` на `target` до кратного `step` градусів,
    зберігаючи відстань між точками незмінною.

    Використовується під час малювання стіни: користувач клацає приблизну
    точку, а кут до неї "прилипає" до кроку сітки кутів (типово 15°).
    """
    distance = origin.distance_to(target)
    if distance == 0:
        return origin
    angle = origin.angle_to(target)
    snapped = math.radians(snap_angle(angle, step))
    return Point(
        origin.x + distance * math.cos(snapped),
        origin.z + distance * math.sin(snapped),
    )


def polygon_area(points: list[Point]) -> float:
    """Площа замкненого полігонального контуру (формула Гаусса/shoelace), мм².

    Контур замикається автоматично — останню точку з'єднано з першою,
    додавати першу точку в кінець списку не потрібно.
    """
    n = len(points)
    if n < 3:
        return 0.0
    total = 0.0
    for i in range(n):
        p1 = points[i]
        p2 = points[(i + 1) % n]
        total += p1.x * p2.z - p2.x * p1.z
    return abs(total) / 2.0


def polygon_perimeter(points: list[Point]) -> float:
    """Периметр замкненого полігонального контуру, мм."""
    n = len(points)
    if n < 2:
        return 0.0
    return sum(points[i].distance_to(points[(i + 1) % n]) for i in range(n))


def rotate_point(point: Point, angle_degrees: float, origin: Point | None = None) -> Point:
    """Повертає точку навколо `origin` (за замовчуванням — початок координат)
    проти годинникової стрілки на `angle_degrees` градусів."""
    if origin is None:
        origin = Point(0.0, 0.0)
    angle = math.radians(angle_degrees)
    dx = point.x - origin.x
    dz = point.z - origin.z
    cos_a, sin_a = math.cos(angle), math.sin(angle)
    return Point(
        origin.x + dx * cos_a - dz * sin_a,
        origin.z + dx * sin_a + dz * cos_a,
    )


def point_in_polygon(point: Point, polygon: list[Point]) -> bool:
    """Перевіряє, чи лежить точка всередині замкненого полігону (алгоритм
    променя/ray casting). Контур замикається автоматично."""
    n = len(polygon)
    inside = False
    x, z = point.x, point.z
    for i in range(n):
        x1, z1 = polygon[i].x, polygon[i].z
        x2, z2 = polygon[(i + 1) % n].x, polygon[(i + 1) % n].z
        if (z1 > z) != (z2 > z):
            x_intersect = x1 + (z - z1) * (x2 - x1) / (z2 - z1)
            if x < x_intersect:
                inside = not inside
    return inside


def _ensure_ccw(points: list[Point]) -> list[Point]:
    """Повертає точки в порядку проти годинникової стрілки (для shoelace-подібних алгоритмів)."""
    signed_area2 = sum(
        points[i].x * points[(i + 1) % len(points)].z - points[(i + 1) % len(points)].x * points[i].z
        for i in range(len(points))
    )
    return points if signed_area2 > 0 else list(reversed(points))


def _segment_intersection(a: Point, b: Point, p1: Point, p2: Point) -> Point:
    """Точка перетину прямої a-b з прямою p1-p2 (стандартна формула перетину прямих)."""
    x1, y1 = a.x, a.z
    x2, y2 = b.x, b.z
    x3, y3 = p1.x, p1.z
    x4, y4 = p2.x, p2.z
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) < 1e-9:
        return p2
    det_ab = x1 * y2 - y1 * x2
    det_p = x3 * y4 - y3 * x4
    px = (det_ab * (x3 - x4) - (x1 - x2) * det_p) / denom
    pz = (det_ab * (y3 - y4) - (y1 - y2) * det_p) / denom
    return Point(px, pz)


def clip_convex_polygon(subject: list[Point], window: list[Point]) -> list[Point]:
    """Перетин двох опуклих полігонів (алгоритм Сазерленда-Ходжмена).

    Повертає точки полігону перетину; порожній список, якщо перетину
    немає. Порядок обходу вхідних полігонів довільний — усередині
    приводиться до проти-годинникового.
    """
    subject_ccw = _ensure_ccw(list(subject))
    window_ccw = _ensure_ccw(list(window))

    output = subject_ccw
    n = len(window_ccw)
    for i in range(n):
        if not output:
            break
        edge_a = window_ccw[i]
        edge_b = window_ccw[(i + 1) % n]
        input_list = output
        output = []
        m = len(input_list)
        for j in range(m):
            current = input_list[j]
            previous = input_list[j - 1]
            cross_current = (edge_b.x - edge_a.x) * (current.z - edge_a.z) - (edge_b.z - edge_a.z) * (
                current.x - edge_a.x
            )
            cross_previous = (edge_b.x - edge_a.x) * (previous.z - edge_a.z) - (edge_b.z - edge_a.z) * (
                previous.x - edge_a.x
            )
            current_inside = cross_current >= -1e-9
            previous_inside = cross_previous >= -1e-9
            if current_inside:
                if not previous_inside:
                    output.append(_segment_intersection(edge_a, edge_b, previous, current))
                output.append(current)
            elif previous_inside:
                output.append(_segment_intersection(edge_a, edge_b, previous, current))
    return output


@dataclass(frozen=True)
class Rect:
    """Прямокутна зона в мм-координатах (сторони паралельні осям)."""

    x0: float
    z0: float
    x1: float
    z1: float

    @property
    def width(self) -> float:
        return self.x1 - self.x0

    @property
    def height(self) -> float:
        return self.z1 - self.z0

    @property
    def area(self) -> float:
        return self.width * self.height

    def corners(self) -> list[Point]:
        """Кути прямокутника проти годинникової стрілки."""
        return [
            Point(self.x0, self.z0),
            Point(self.x1, self.z0),
            Point(self.x1, self.z1),
            Point(self.x0, self.z1),
        ]


def _is_rectilinear(points: list[Point]) -> bool:
    n = len(points)
    for i in range(n):
        p1, p2 = points[i], points[(i + 1) % n]
        if p1.x != p2.x and p1.z != p2.z:
            return False
    return True


def decompose_rectilinear_polygon(points: list[Point]) -> list[Rect]:
    """Розкладає ортогональний (прямокутний) контур на прямокутники.

    Проста, але точна декомпозиція: будує сітку з усіх унікальних X і Z
    координат вершин контуру і залишає ті комірки сітки, центр яких
    лежить усередині контуру. Декомпозиція не обов'язково мінімальна за
    кількістю прямокутників (може розбити суцільну ділянку на кілька),
    зате завжди коректна і покриває контур точно, без залишку.

    Підтримує лише контури, всі ребра яких горизонтальні або
    вертикальні (як у типового плану поверху) — інакше піднімає
    ValueError, оскільки довільний полігон неможливо точно розкласти на
    прямокутники.
    """
    if len(points) < 4:
        raise ValueError("Ортогональний контур має містити щонайменше 4 точки")
    if not _is_rectilinear(points):
        raise ValueError(
            "Декомпозиція на прямокутники підтримує лише ортогональні контури "
            "(усі ребра горизонтальні або вертикальні)"
        )

    xs = sorted({p.x for p in points})
    zs = sorted({p.z for p in points})
    rects: list[Rect] = []
    for i in range(len(xs) - 1):
        x0, x1 = xs[i], xs[i + 1]
        for j in range(len(zs) - 1):
            z0, z1 = zs[j], zs[j + 1]
            center = Point((x0 + x1) / 2, (z0 + z1) / 2)
            if point_in_polygon(center, points):
                rects.append(Rect(x0, z0, x1, z1))
    return rects
