"""Траса кабелю від щитка до точки споживання."""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import MM_PER_M, Point, snap_point


@dataclass
class CableRoute:
    """Полілінія траси кабелю: перша точка — щиток, остання — точка
    споживання; проміжні точки — де кабель повертає (по стінах,
    стелі чи підлозі)."""

    points: list[Point]

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("Траса кабелю має містити щонайменше 2 точки (від щитка до точки споживання)")

    @property
    def length_mm(self) -> float:
        """Довжина траси — сума довжин відрізків полілінії, мм."""
        return sum(self.points[i].distance_to(self.points[i + 1]) for i in range(len(self.points) - 1))

    @property
    def length_m(self) -> float:
        return self.length_mm / MM_PER_M


def build_route(start: Point, waypoints: list[Point], *, snap: bool = True, snap_step: float = 90.0) -> CableRoute:
    """Будує трасу від `start` (щиток) через `waypoints` до точки
    споживання (остання точка в `waypoints`).

    З `snap=True` (за замовчуванням) кожен наступний відрізок
    прив'язується до кута, кратного `snap_step` градусів — 90° за
    замовчуванням, бо траса йде по стінах/стелі/підлозі під прямим
    кутом. Прив'язка виконується тією самою функцією, що й прив'язка
    кутів контуру кімнати в модулі 1 (`kovadlo.geometry.snap_point`),
    просто з іншим кроком.
    """
    if not waypoints:
        raise ValueError("Потрібна хоча б одна точка — точка споживання")
    points = [start]
    for raw in waypoints:
        points.append(snap_point(points[-1], raw, snap_step) if snap else raw)
    return CableRoute(points=points)
