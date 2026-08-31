import pytest

from kovadlo.electrical_point import DEFAULT_POWER_W, ConsumptionPoint, PointKind
from kovadlo.geometry import Point


def test_default_power_used_when_not_specified():
    p = ConsumptionPoint(name="Світло 1", kind=PointKind.LIGHT, position=Point(0, 0))
    assert p.power_w == DEFAULT_POWER_W[PointKind.LIGHT]


def test_explicit_power_overrides_default():
    p = ConsumptionPoint(name="Світло 1", kind=PointKind.LIGHT, position=Point(0, 0), power_w=25.0)
    assert p.power_w == 25.0


def test_switch_and_panel_default_to_zero_power():
    switch = ConsumptionPoint(name="Вимикач", kind=PointKind.SWITCH, position=Point(0, 0))
    panel = ConsumptionPoint(name="Щиток", kind=PointKind.PANEL, position=Point(0, 0))
    assert switch.power_w == 0.0
    assert panel.power_w == 0.0


def test_negative_power_rejected():
    with pytest.raises(ValueError):
        ConsumptionPoint(name="X", kind=PointKind.SOCKET, position=Point(0, 0), power_w=-10)


def test_all_kinds_have_a_default_power():
    for kind in PointKind:
        assert kind in DEFAULT_POWER_W
        assert DEFAULT_POWER_W[kind] >= 0
