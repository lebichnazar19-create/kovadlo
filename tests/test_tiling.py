import math

import pytest

from kovadlo.geometry import Point, polygon_area
from kovadlo.grout import Grout
from kovadlo.layout import RowOffset, TileLayout
from kovadlo.materials import Material
from kovadlo.room import Room
from kovadlo.surface import Surface
from kovadlo.tile import Tile
from kovadlo.tiling import calculate_tiling
from kovadlo.wall import Wall

BRICK = Material(name="цегла", density_kg_m3=1800)


def _rectangle_surface(width: float, height: float) -> Surface:
    return Surface(contour=[Point(0, 0), Point(width, 0), Point(width, height), Point(0, height)])


# ---------------------------------------------------------------------------
# Прості прямокутні поверхні — результат легко перевірити вручну.
# ---------------------------------------------------------------------------


def test_exact_fit_no_grout_gives_no_cuts():
    surface = _rectangle_surface(1200, 1200)
    tile = Tile(width=600, height=600)
    grout = Grout(width_mm=0)
    layout = TileLayout()

    result = calculate_tiling(surface, tile, grout, layout, tiles_per_package=1)

    assert result.whole_tiles_count == 4
    assert result.cuts_count == 0
    assert result.total_tiles_needed == 4


def test_partial_column_produces_expected_cut():
    surface = _rectangle_surface(1000, 600)
    tile = Tile(width=600, height=600)
    grout = Grout(width_mm=0)
    layout = TileLayout()

    result = calculate_tiling(surface, tile, grout, layout, tiles_per_package=1)

    assert result.whole_tiles_count == 1
    assert result.cuts_count == 1
    assert result.cuts[0].width_mm == pytest.approx(400.0)
    assert result.cuts[0].height_mm == pytest.approx(600.0)


@pytest.mark.parametrize("row_offset", [RowOffset.NONE, RowOffset.HALF, RowOffset.THIRD])
def test_coverage_is_conserved_when_grout_is_zero_and_angle_zero(row_offset):
    """При куті 0° розмір підрізки — це точний прямокутний шматок, тож без
    фуги сума площ усіх шматків (цілих + підрізок) має точно дорівнювати
    площі поверхні, незалежно від зсуву рядів чи стартової точки."""
    surface = _rectangle_surface(3700, 2450)
    tile = Tile(width=600, height=450)
    grout = Grout(width_mm=0)
    layout = TileLayout(start=Point(37, -18), row_offset=row_offset, angle=0.0)

    result = calculate_tiling(surface, tile, grout, layout, tiles_per_package=1)

    whole_area = result.whole_tiles_count * tile.area_mm2
    cuts_area = sum(cut.area_mm2 for cut in result.cuts)
    assert whole_area + cuts_area == pytest.approx(surface.area_mm2, rel=1e-9)


@pytest.mark.parametrize("row_offset", [RowOffset.NONE, RowOffset.HALF, RowOffset.THIRD])
def test_diagonal_layout_never_underestimates_material(row_offset):
    """При куті 45° підрізка при непрямокутних (трикутних/шестикутних)
    крайових шматках рахується як розмір заготовки-прямокутника, з якої
    вирізають потрібну форму — тому сумарна площа заготовок (цілі +
    підрізки) має бути НЕ МЕНШОЮ за площу поверхні (запас на різ), а не
    рівною їй."""
    surface = _rectangle_surface(3700, 2450)
    tile = Tile(width=600, height=450)
    grout = Grout(width_mm=0)
    layout = TileLayout(start=Point(37, -18), row_offset=row_offset, angle=45.0)

    result = calculate_tiling(surface, tile, grout, layout, tiles_per_package=1)

    whole_area = result.whole_tiles_count * tile.area_mm2
    cuts_area = sum(cut.area_mm2 for cut in result.cuts)
    assert whole_area + cuts_area >= surface.area_mm2 - 1e-6


# ---------------------------------------------------------------------------
# Кімната з виступом (L-подібна форма), плитка 600x600, фуга 2 мм.
# Значення нижче вирахувані вручну (див. опис у README) і слугують
# регресійним контролем точності алгоритму.
# ---------------------------------------------------------------------------


def _l_shaped_room() -> Room:
    contour = [
        Point(0, 0),
        Point(4000, 0),
        Point(4000, 2000),
        Point(5500, 2000),
        Point(5500, 3000),
        Point(0, 3000),
    ]
    walls = [
        Wall.create(
            start=contour[i],
            end=contour[(i + 1) % len(contour)],
            height=2700,
            thickness=200,
            material=BRICK,
        )
        for i in range(len(contour))
    ]
    return Room(contour=contour, walls=walls, name="Кімната з виступом")


def test_l_shaped_room_floor_area_sanity():
    room = _l_shaped_room()
    assert polygon_area(room.contour) == pytest.approx(13_500_000.0)


def test_l_shaped_room_tiling_matches_hand_calculation():
    room = _l_shaped_room()
    surface = Surface.from_room_floor(room)
    tile = Tile(width=600, height=600, name="Керамограніт", color="сірий")
    grout = Grout(width_mm=2.0, color="сірий")
    layout = TileLayout(start=Point(0, 0), row_offset=RowOffset.NONE, angle=0)

    result = calculate_tiling(surface, tile, grout, layout, tiles_per_package=4)

    assert result.whole_tiles_count == 18
    assert result.cuts_count == 32
    assert result.total_tiles_needed == 50

    expected_cuts = {
        (600.0, 194.0): 6,
        (388.0, 600.0): 3,
        (388.0, 194.0): 1,
        (600.0, 406.0): 8,
        (600.0, 592.0): 8,
        (388.0, 406.0): 1,
        (388.0, 592.0): 1,
        (212.0, 406.0): 1,
        (212.0, 592.0): 1,
        (82.0, 406.0): 1,
        (82.0, 592.0): 1,
    }
    assert result.cuts_summary() == expected_cuts

    assert result.packages_needed == math.ceil(50 / 4)
    assert result.reserve_tiles == math.ceil(50 * 0.10)
    assert result.total_tiles_with_reserve == 50 + 5

    expected_grout_area_m2 = 103_704 / 1_000_000
    assert result.grout_area_m2 == pytest.approx(expected_grout_area_m2, rel=1e-6)


def test_l_shaped_room_tiling_packages_and_reserve_are_separate_numbers():
    room = _l_shaped_room()
    surface = Surface.from_room_floor(room)
    tile = Tile(width=600, height=600)
    grout = Grout(width_mm=2.0)
    layout = TileLayout()

    result = calculate_tiling(surface, tile, grout, layout, tiles_per_package=10, waste_fraction=0.10)

    # запас — окреме число, воно НЕ додається автоматично до total_tiles_needed
    assert result.total_tiles_needed == 50
    assert result.packages_needed == 5  # 50 / 10, без запасу
    assert result.reserve_tiles == 5  # 10% від 50, окремо
