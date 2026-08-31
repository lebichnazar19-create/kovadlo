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
from web.tiling_render import render_tile_placements

BRICK = Material(name="цегла", density_kg_m3=1800)


def _rectangle_surface(width: float, height: float) -> Surface:
    return Surface(contour=[Point(0, 0), Point(width, 0), Point(width, height), Point(0, height)])


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


@pytest.mark.parametrize(
    "surface_factory,angle,row_offset",
    [
        (lambda: _rectangle_surface(3700, 2450), 0.0, RowOffset.NONE),
        (lambda: _rectangle_surface(3700, 2450), 0.0, RowOffset.HALF),
        (lambda: _rectangle_surface(3700, 2450), 45.0, RowOffset.THIRD),
        (lambda: Surface.from_room_floor(_l_shaped_room()), 0.0, RowOffset.NONE),
        (lambda: Surface.from_room_floor(_l_shaped_room()), 45.0, RowOffset.HALF),
    ],
)
def test_render_totals_match_calculate_tiling(surface_factory, angle, row_offset):
    """Рендер-прохід модуля 3 (позиції для canvas) має рахувати РІВНО ту ж
    кількість цілих і підрізаних плиток — і ті самі розміри підрізок — що
    й офіційний підрахунок ядра `calculate_tiling`. Це головна гарантія,
    що дублювання математики сітки (потрібне лише для рендерингу позицій)
    не розійшлося з ядром."""
    surface = surface_factory()
    tile = Tile(width=600, height=450)
    grout = Grout(width_mm=2.0)
    layout = TileLayout(start=Point(10, -25), row_offset=row_offset, angle=angle)

    result = calculate_tiling(surface, tile, grout, layout, tiles_per_package=1)
    placements = render_tile_placements(surface, tile, grout, layout)

    whole_placements = [p for p in placements if p.kind == "whole"]
    cut_placements = [p for p in placements if p.kind == "cut"]

    assert len(whole_placements) == result.whole_tiles_count
    assert len(cut_placements) == result.cuts_count

    rendered_summary: dict[tuple[float, float], int] = {}
    for p in cut_placements:
        key = (round(p.cut_width_mm, 2), round(p.cut_height_mm, 2))
        rendered_summary[key] = rendered_summary.get(key, 0) + 1

    assert rendered_summary == result.cuts_summary()


def test_render_placement_polygons_are_closed_and_non_degenerate():
    surface = _rectangle_surface(1300, 700)
    tile = Tile(width=600, height=600)
    grout = Grout(width_mm=2.0)
    layout = TileLayout()

    placements = render_tile_placements(surface, tile, grout, layout)
    assert len(placements) > 0
    for piece in placements:
        assert len(piece.points) >= 3
        assert polygon_area(piece.points) > 0


def test_render_whole_tile_label_is_empty_and_cut_label_has_size():
    surface = _rectangle_surface(1000, 600)
    tile = Tile(width=600, height=600)
    grout = Grout(width_mm=0)
    layout = TileLayout()

    placements = render_tile_placements(surface, tile, grout, layout)
    whole = [p for p in placements if p.kind == "whole"]
    cuts = [p for p in placements if p.kind == "cut"]

    assert len(whole) == 1
    assert whole[0].label == ""
    assert len(cuts) == 1
    assert cuts[0].label == "400x600"


def test_render_diagonal_cut_pieces_can_be_non_rectangular():
    """При куті 45° крайній шматок плитки не мусить бути прямокутником —
    рендер має повертати справжній контур (тут — щонайменше 3 вершини,
    які не утворюють прямокутник біля межі поверхні)."""
    surface = _rectangle_surface(1000, 1000)
    tile = Tile(width=600, height=600)
    grout = Grout(width_mm=0)
    layout = TileLayout(start=Point(0, 0), angle=45.0)

    placements = render_tile_placements(surface, tile, grout, layout)
    cuts = [p for p in placements if p.kind == "cut"]
    assert len(cuts) > 0
    # хоч один зі шматків підрізки — не чотирикутник (трикутник/п'ятикутник тощо)
    assert any(len(p.points) != 4 for p in cuts)
