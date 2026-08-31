"""
Плата (фізичний рівень): контур (полігон з модуля 1), розміщення
компонентів, доріжки й перехідні отвори (via).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .geometry import MM2_PER_M2, MM_PER_M, Point, polygon_area, polygon_perimeter, rotate_point, snap_point
from .pcb_component import Component
from .pcb_norms import Layer


@dataclass
class Placement:
    """Розміщення компонента на платі: посилання на компонент, координати
    (мм) і кут повороту (градуси, проти годинникової стрілки)."""

    component: Component
    position: Point
    rotation_deg: float = 0.0

    def pin_position(self, pin_number: int) -> Point:
        """Абсолютна позиція виводу на платі — локальна позиція виводу з
        посадкового місця, повернена на `rotation_deg` і зсунена в `position`."""
        local = self.component.footprint.pin(pin_number).position
        rotated = rotate_point(local, self.rotation_deg)
        return Point(self.position.x + rotated.x, self.position.z + rotated.z)


@dataclass
class Track:
    """Доріжка: полілінія (мм), ширина, шар, ланцюг (net), якому належить."""

    points: list[Point]
    width_mm: float
    layer: Layer
    net: str

    def __post_init__(self) -> None:
        if len(self.points) < 2:
            raise ValueError("Доріжка має містити щонайменше 2 точки")
        if self.width_mm <= 0:
            raise ValueError("Ширина доріжки має бути додатною")

    @property
    def length_mm(self) -> float:
        return sum(self.points[i].distance_to(self.points[i + 1]) for i in range(len(self.points) - 1))

    @property
    def length_m(self) -> float:
        return self.length_mm / MM_PER_M

    def segments(self) -> list[tuple[Point, Point]]:
        """Пари (початок, кінець) кожного відрізка полілінії доріжки."""
        return [(self.points[i], self.points[i + 1]) for i in range(len(self.points) - 1)]


def build_track(
    start: Point,
    waypoints: list[Point],
    width_mm: float,
    layer: Layer,
    net: str,
    *,
    snap: bool = True,
    snap_step: float = 45.0,
) -> Track:
    """Будує доріжку від `start` через `waypoints` до останньої точки.

    З `snap=True` (за замовчуванням) кожен відрізок прив'язується до
    кута, кратного `snap_step` градусів — 45° за замовчуванням, типовий
    кут трасування друкованих плат. Прив'язка виконується тією самою
    функцією, що й кути контуру кімнати в модулі 1
    (`kovadlo.geometry.snap_point`), лише з іншим кроком.
    """
    if not waypoints:
        raise ValueError("Потрібна хоча б одна точка призначення")
    points = [start]
    for raw in waypoints:
        points.append(snap_point(points[-1], raw, snap_step) if snap else raw)
    return Track(points=points, width_mm=width_mm, layer=layer, net=net)


@dataclass(frozen=True)
class Via:
    """Перехідний отвір між шарами: позиція, діаметри свердла й
    контактного майданчика, ланцюг."""

    position: Point
    net: str
    drill_diameter_mm: float
    pad_diameter_mm: float

    def __post_init__(self) -> None:
        if self.drill_diameter_mm <= 0 or self.pad_diameter_mm <= 0:
            raise ValueError("Діаметри перехідного отвору мають бути додатними")
        if self.pad_diameter_mm <= self.drill_diameter_mm:
            raise ValueError("Діаметр контактного майданчика має бути більшим за діаметр свердла")


@dataclass
class Board:
    """Плата: контур + розміщені компоненти + доріжки + перехідні отвори."""

    contour: list[Point]
    placements: dict[str, Placement] = field(default_factory=dict)  # Component.reference -> Placement
    tracks: list[Track] = field(default_factory=list)
    vias: list[Via] = field(default_factory=list)
    name: str = ""

    def __post_init__(self) -> None:
        if len(self.contour) < 3:
            raise ValueError("Контур плати має містити щонайменше 3 точки")

    @property
    def area_mm2(self) -> float:
        return polygon_area(self.contour)

    @property
    def area_m2(self) -> float:
        return self.area_mm2 / MM2_PER_M2

    @property
    def perimeter_mm(self) -> float:
        return polygon_perimeter(self.contour)

    def pin_position(self, reference: str, pin_number: int) -> Point:
        """Абсолютна позиція виводу компонента `reference` на платі."""
        if reference not in self.placements:
            raise KeyError(f"Немає розміщення для компонента «{reference}»")
        return self.placements[reference].pin_position(pin_number)

    def tracks_on_net(self, net: str) -> list[Track]:
        return [t for t in self.tracks if t.net == net]

    def vias_on_net(self, net: str) -> list[Via]:
        return [v for v in self.vias if v.net == net]

    @property
    def total_track_length_m(self) -> float:
        return sum(t.length_m for t in self.tracks)
