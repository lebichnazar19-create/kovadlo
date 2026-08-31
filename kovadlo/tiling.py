"""
Розрахунок покриття поверхні плиткою.

Підхід: поверхня розкладається (`Surface.rectangles`) на прямокутні
зони, і кожна зона накривається сіткою плитки в СПІЛЬНІЙ системі
координат розкладки (одна стартова точка, один крок сітки для всіх
зон) — так шви й малюнок лишаються суцільними на межі зон. Для кожної
комірки сітки береться точний геометричний перетин (відсікання
опуклих полігонів) із прямокутником зони: якщо перетин дорівнює цілій
комірці — це ціла плитка, інакше — підрізка.

Розмір підрізки — це bounding box перетину у власних осях плитки
(u, v), тобто розмір прямокутної заготовки, з якої вирізають потрібний
шматок. При куті 0° перетин із прямим краєм кімнати завжди сам є
прямокутником, тож це точний фінальний розмір. При куті 45° крайній
шматок може бути трикутним чи багатокутним — тоді bounding box трохи
більший за фактично потрібну форму (це нормально: реальний виріз усе
одно ріжуть із прямокутної плитки), тому сума розмірів підрізок при
45° дає невеликий, чесний запас на різ, а не точну площу покриття.

Свідоме спрощення: якщо межа між двома зонами декомпозиції не є
справжньою стіною (наприклад, внутрішній "шов" там, де контур кімнати
з виступом розбивається на прямокутники), плитка, що в реальності
могла б лягти суцільно впоперек цієї межі, тут рахується як дві
підрізки. Для прямокутних поверхонь (кімната-прямокутник, стіна) це
обмеження не проявляється, оскільки зона там одна.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .geometry import (
    MM2_PER_M2,
    Point,
    Rect,
    clip_convex_polygon,
    polygon_area,
    rotate_point,
)
from .grout import Grout
from .layout import TileLayout
from .surface import Surface
from .tile import Tile

_AREA_EPSILON_MM2 = 1e-3  # допуск на похибку округлення при порівнянні площ, мм²


@dataclass(frozen=True)
class TileCut:
    """Підрізана плитка: точний розмір шматка, що йде в справу.

    Розмір виміряний уздовж власних осей плитки (тобто саме те, що
    виставляють на плиткорізі), а не проєкція на поверхню.
    """

    width_mm: float
    height_mm: float

    @property
    def area_mm2(self) -> float:
        return self.width_mm * self.height_mm


@dataclass
class TilingResult:
    """Результат розрахунку покриття поверхні плиткою."""

    tile: Tile
    grout: Grout
    whole_tiles_count: int
    cuts: list[TileCut] = field(default_factory=list)
    tiles_per_package: int = 1
    waste_fraction: float = 0.10

    @property
    def cuts_count(self) -> int:
        return len(self.cuts)

    @property
    def total_tiles_needed(self) -> int:
        """Загальна кількість плиток з урахуванням підрізки: цілі +
        по одній плитці на кожну підрізку (заготовки з обрізків не
        переносяться між підрізками)."""
        return self.whole_tiles_count + self.cuts_count

    @property
    def packages_needed(self) -> int:
        """Кількість упаковок для total_tiles_needed (без запасу)."""
        return math.ceil(self.total_tiles_needed / self.tiles_per_package)

    @property
    def reserve_tiles(self) -> int:
        """Запас окремим числом (за замовчуванням 10%) — НЕ входить у
        total_tiles_needed чи packages_needed."""
        return math.ceil(self.total_tiles_needed * self.waste_fraction)

    @property
    def total_tiles_with_reserve(self) -> int:
        """Довідково: total_tiles_needed + reserve_tiles."""
        return self.total_tiles_needed + self.reserve_tiles

    @property
    def packages_with_reserve(self) -> int:
        """Довідково: кількість упаковок, якщо одразу закладати запас."""
        return math.ceil(self.total_tiles_with_reserve / self.tiles_per_package)

    def cuts_summary(self) -> dict[tuple[float, float], int]:
        """Групує підрізки за розміром: {(ширина, висота): кількість}."""
        summary: dict[tuple[float, float], int] = {}
        for cut in self.cuts:
            key = (round(cut.width_mm, 2), round(cut.height_mm, 2))
            summary[key] = summary.get(key, 0) + 1
        return summary

    @property
    def grout_length_mm(self) -> float:
        """Наближена сумарна довжина швів фуги.

        Метод "половина периметра на плитку": для кожної вкладеної
        плитки (цілої чи підрізаної) береться сума її ширини й висоти.
        Внутрішній шов належить одразу двом сусіднім плиткам, тому
        рахуючи по два боки з кожної це в середньому дає правильну
        сумарну довжину без побудови точної мережі стиків.
        """
        whole_contrib = self.whole_tiles_count * (self.tile.width + self.tile.height)
        cuts_contrib = sum(cut.width_mm + cut.height_mm for cut in self.cuts)
        return whole_contrib + cuts_contrib

    @property
    def grout_area_mm2(self) -> float:
        """Площа фуги для розрахунку суміші, мм²."""
        return self.grout_length_mm * self.grout.width_mm

    @property
    def grout_area_m2(self) -> float:
        return self.grout_area_mm2 / MM2_PER_M2


def calculate_tiling(
    surface: Surface,
    tile: Tile,
    grout: Grout,
    layout: TileLayout,
    *,
    tiles_per_package: int = 1,
    waste_fraction: float = 0.10,
) -> TilingResult:
    """Рахує покриття поверхні плиткою за заданою розкладкою."""
    if tiles_per_package <= 0:
        raise ValueError("Кількість плиток в упаковці має бути додатною")

    pitch_u = tile.width + grout.width_mm
    pitch_v = tile.height + grout.width_mm
    row_shift = layout.row_offset.value * tile.width
    tile_cell_area = tile.width * tile.height

    whole_count = 0
    cuts: list[TileCut] = []

    for rect in surface.rectangles():
        whole, rect_cuts = _tile_rectangle(rect, layout, tile, pitch_u, pitch_v, row_shift, tile_cell_area)
        whole_count += whole
        cuts.extend(rect_cuts)

    return TilingResult(
        tile=tile,
        grout=grout,
        whole_tiles_count=whole_count,
        cuts=cuts,
        tiles_per_package=tiles_per_package,
        waste_fraction=waste_fraction,
    )


def _tile_rectangle(
    rect: Rect,
    layout: TileLayout,
    tile: Tile,
    pitch_u: float,
    pitch_v: float,
    row_shift: float,
    tile_cell_area: float,
) -> tuple[int, list[TileCut]]:
    """Тайлить одну прямокутну зону, повертає (к-сть цілих, список підрізок)."""
    # переводимо кути зони в систему координат сітки розкладки (обертання на
    # -angle навколо стартової точки) — у цій системі сітка сама завжди
    # вирівняна по осях (u, v), незалежно від кута розкладки на поверхні.
    grid_corners = [rotate_point(p, -layout.angle, layout.start) for p in rect.corners()]
    local = [Point(p.x - layout.start.x, p.z - layout.start.z) for p in grid_corners]

    us = [p.x for p in local]
    vs = [p.z for p in local]
    u_min, u_max = min(us), max(us)
    v_min, v_max = min(vs), max(vs)

    j_min = math.floor(v_min / pitch_v) - 1
    j_max = math.ceil(v_max / pitch_v) + 1

    whole = 0
    cuts: list[TileCut] = []

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
            if abs(area - tile_cell_area) <= _AREA_EPSILON_MM2:
                whole += 1
            else:
                piece_us = [p.x for p in piece]
                piece_vs = [p.z for p in piece]
                width = min(max(piece_us) - min(piece_us), tile.width)
                height = min(max(piece_vs) - min(piece_vs), tile.height)
                cuts.append(TileCut(width_mm=round(width, 3), height_mm=round(height, 3)))

    return whole, cuts


def format_report(surface: Surface, tile: Tile, grout: Grout, layout: TileLayout, result: TilingResult) -> str:
    """Формує текстовий звіт по розрахунку покриття плиткою (без графіки)."""
    lines = [
        f"Поверхня: {surface.name}",
        f"  площа: {surface.area_m2:.2f} м²",
        f"Плитка: {tile.name or '(без назви)'} {tile.width:.0f}x{tile.height:.0f} мм, колір: {tile.color or '-'}",
        f"Фуга: {grout.width_mm:.1f} мм, колір: {grout.color or '-'}",
        (
            f"Розкладка: старт=({layout.start.x:.0f}, {layout.start.z:.0f}) мм, "
            f"зсув рядів={layout.row_offset.value * 100:.1f}%, кут={layout.angle:.0f}°"
        ),
        "",
        f"Цілих плиток:          {result.whole_tiles_count}",
        f"Підрізок:              {result.cuts_count}",
    ]
    for (width, height), count in sorted(result.cuts_summary().items(), key=lambda kv: (-kv[1], -kv[0][0])):
        lines.append(f"    {count} x {width:.0f} x {height:.0f} мм")
    lines.extend(
        [
            f"Разом плиток:          {result.total_tiles_needed}",
            f"Упаковок:              {result.packages_needed} (по {result.tiles_per_package} шт.)",
            f"Запас {result.waste_fraction * 100:.0f}% (окремим числом): {result.reserve_tiles} плиток",
            f"Площа фуги (для суміші): {result.grout_area_m2:.3f} м²",
        ]
    )
    return "\n".join(lines)
