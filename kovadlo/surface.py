"""Поверхня для покриття плиткою: підлога кімнати або окрема стіна."""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import MM2_PER_M2, Point, Rect, decompose_rectilinear_polygon, polygon_area
from .room import Room
from .wall import Wall


@dataclass
class Surface:
    """Поверхня в локальних (u, v) мм-координатах — ортогональний контур.

    Береться з модуля 1: підлога кімнати (контур кімнати як є) або
    окрема стіна (розгорнута в прямокутник довжина x висота).
    """

    contour: list[Point]
    name: str = ""

    @classmethod
    def from_room_floor(cls, room: Room) -> "Surface":
        """Поверхня — підлога кімнати (той самий контур, що й у Room)."""
        name = f"підлога кімнати «{room.name}»" if room.name else "підлога"
        return cls(contour=list(room.contour), name=name)

    @classmethod
    def from_wall(cls, wall: Wall, name: str = "") -> "Surface":
        """Поверхня — стіна, розгорнута в прямокутник: u вздовж довжини
        стіни, v вздовж висоти, (0,0) — один із нижніх кутів."""
        length = wall.length_mm
        height = wall.height
        contour = [Point(0, 0), Point(length, 0), Point(length, height), Point(0, height)]
        return cls(contour=contour, name=name or "стіна")

    @property
    def area_mm2(self) -> float:
        return polygon_area(self.contour)

    @property
    def area_m2(self) -> float:
        return self.area_mm2 / MM2_PER_M2

    def rectangles(self) -> list[Rect]:
        """Розкладає поверхню на прямокутні зони для розрахунку розкладки плитки."""
        return decompose_rectilinear_polygon(self.contour)
