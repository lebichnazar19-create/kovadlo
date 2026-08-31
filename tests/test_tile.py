import pytest

from kovadlo.tile import Tile


def test_tile_basic():
    tile = Tile(width=600, height=600, name="Керамограніт", color="сірий")
    assert tile.area_mm2 == pytest.approx(360_000.0)


def test_tile_rejects_non_positive_size():
    with pytest.raises(ValueError):
        Tile(width=0, height=600)
    with pytest.raises(ValueError):
        Tile(width=600, height=-1)
