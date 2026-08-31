"""
Точні контури окремих плиток для відображення на canvas.

Це шар модуля 3 (візуалізація): він НЕ входить в ядро (модулі 1-2) і
лише читає його публічні функції — `clip_convex_polygon`, `rotate_point`,
`polygon_area`, `Surface.rectangles`. Математика сітки (крок, зсув
рядів, кут) та сама, що й у `kovadlo.tiling.calculate_tiling`, але тут
додатково повертається справжній контур КОЖНОЇ плитки — це потрібно
лише для малювання; для підрахунку в ядрі позиція не потрібна, тому
там її й немає.

Оскільки при куті 45° крайній шматок плитки може бути трикутним чи
багатокутним (не прямокутником), кожен шматок повертається як повний
контур (список точок), а не як прямокутник (u, v, ширина, висота) —
так на екрані видно справжню форму підрізки. Bounding box шматка
використовується лише для підпису розміру заготовки — так само, як і
в ядрі.

Узгодженість цього рендер-проходу з ядром перевіряється тестом
`tests/test_tiling_render.py::test_render_totals_match_calculate_tiling`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from kovadlo import Grout, Point, Rect, Surface, Tile, TileLayout
from kovadlo.geometry import clip_convex_polygon, polygon_area, rotate_point

_AREA_EPSILON_MM2 = 1e-3


@dataclass(frozen=True)
class TilePlacement:
    """Один шматок плитки (цілої чи підрізаної): контур у мм-координатах
    поверхні (u, v), готовий для малювання."""

    points: list[Point]
    kind: str  # "whole" | "cut"
    cut_width_mm: float | None = None
    cut_height_mm: float | None = None

    @property
    def label(self) -> str:
        """Підпис розміру заготовки для підрізки; порожньо для цілої плитки."""
        if self.kind != "cut" or self.cut_width_mm is None or self.cut_height_mm is None:
            return ""
        return f"{self.cut_width_mm:.0f}x{self.cut_height_mm:.0f}"


def _to_surface_frame(point: Point, start: Point, angle: float) -> Point:
    """Обертає точку назад із системи координат сітки розкладки в
    систему координат поверхні (обернене перетворення до того, що
    робить `_render_rectangle` на вході)."""
    translated = Point(point.x + start.x, point.z + start.z)
    return rotate_point(translated, angle, start)


def render_tile_placements(surface: Surface, tile: Tile, grout: Grout, layout: TileLayout) -> list[TilePlacement]:
    """Контури всіх плиток (цілих і підрізаних) по всій поверхні, у
    мм-координатах поверхні (u, v) — для малювання на canvas."""
    pitch_u = tile.width + grout.width_mm
    pitch_v = tile.height + grout.width_mm
    row_shift = layout.row_offset.value * tile.width
    tile_cell_area = tile.width * tile.height

    placements: list[TilePlacement] = []
    for rect in surface.rectangles():
        placements.extend(_render_rectangle(rect, layout, tile, pitch_u, pitch_v, row_shift, tile_cell_area))
    return placements


def _render_rectangle(
    rect: Rect,
    layout: TileLayout,
    tile: Tile,
    pitch_u: float,
    pitch_v: float,
    row_shift: float,
    tile_cell_area: float,
) -> list[TilePlacement]:
    # та сама ідея, що й у kovadlo.tiling._tile_rectangle: переводимо кути
    # зони в систему координат сітки (обертання на -angle навколо
    # стартової точки) — у ній сітка сама завжди вирівняна по осях.
    grid_corners = [rotate_point(p, -layout.angle, layout.start) for p in rect.corners()]
    local = [Point(p.x - layout.start.x, p.z - layout.start.z) for p in grid_corners]

    us = [p.x for p in local]
    vs = [p.z for p in local]
    u_min, u_max = min(us), max(us)
    v_min, v_max = min(vs), max(vs)

    j_min = math.floor(v_min / pitch_v) - 1
    j_max = math.ceil(v_max / pitch_v) + 1

    placements: list[TilePlacement] = []

    for j in range(j_min, j_max + 1):
        row_bottom_v = j * pitch_v
        shift = row_shift if (j % 2) else 0.0
        i_min = math.floor((u_min - shift) / pitch_u) - 1
        i_max = math.ceil((u_max - shift) / pitch_u) + 1
        for i in range(i_min, i_max + 1):
            col_left_u = shift + i * pitch_u
            cell = [
                Point(col_left_u, row_bottom_v),
                Point(col_left_u + tile.width, row_bottom_v),
                Point(col_left_u + tile.width, row_bottom_v + tile.height),
                Point(col_left_u, row_bottom_v + tile.height),
            ]
            piece = clip_convex_polygon(local, cell)
            if len(piece) < 3:
                continue
            area = polygon_area(piece)
            if area <= _AREA_EPSILON_MM2:
                continue

            is_whole = abs(area - tile_cell_area) <= _AREA_EPSILON_MM2
            surface_points = [_to_surface_frame(p, layout.start, layout.angle) for p in piece]

            if is_whole:
                placements.append(TilePlacement(points=surface_points, kind="whole"))
            else:
                piece_us = [p.x for p in piece]
                piece_vs = [p.z for p in piece]
                width = min(max(piece_us) - min(piece_us), tile.width)
                height = min(max(piece_vs) - min(piece_vs), tile.height)
                placements.append(
                    TilePlacement(
                        points=surface_points,
                        kind="cut",
                        cut_width_mm=round(width, 3),
                        cut_height_mm=round(height, 3),
                    )
                )

    return placements
