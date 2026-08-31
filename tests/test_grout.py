import pytest

from kovadlo.grout import Grout


def test_grout_basic():
    grout = Grout(width_mm=2.0, color="сірий")
    assert grout.width_mm == 2.0


def test_grout_rejects_negative_width():
    with pytest.raises(ValueError):
        Grout(width_mm=-1.0)
