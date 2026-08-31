import pytest

from kovadlo.geometry import Point
from kovadlo.layout import RowOffset, TileLayout


def test_layout_defaults():
    layout = TileLayout()
    assert layout.start == Point(0.0, 0.0)
    assert layout.row_offset is RowOffset.NONE
    assert layout.angle == 0.0


def test_layout_rejects_invalid_angle():
    with pytest.raises(ValueError):
        TileLayout(angle=30)


def test_row_offset_fractions():
    assert RowOffset.NONE.value == 0.0
    assert RowOffset.HALF.value == 0.5
    assert RowOffset.THIRD.value == pytest.approx(1 / 3)
