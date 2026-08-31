import pytest

from kovadlo.geometry import Point
from kovadlo.pcb_component import Component, ComponentKind, Footprint, Pin, Unit


def _two_pin_footprint() -> Footprint:
    return Footprint(name="THT-2", pins=[Pin(1, "1", Point(0, 0)), Pin(2, "2", Point(5.0, 0))])


def test_footprint_pin_count_and_lookup():
    fp = _two_pin_footprint()
    assert fp.pin_count == 2
    assert fp.pin(2).position == Point(5.0, 0)


def test_footprint_rejects_empty_pins():
    with pytest.raises(ValueError):
        Footprint(name="X", pins=[])


def test_footprint_rejects_duplicate_pin_numbers():
    with pytest.raises(ValueError):
        Footprint(name="X", pins=[Pin(1, "a", Point(0, 0)), Pin(1, "b", Point(1, 0))])


def test_footprint_pin_lookup_missing_raises():
    fp = _two_pin_footprint()
    with pytest.raises(KeyError):
        fp.pin(99)


def test_component_pin_count_matches_footprint():
    c = Component("R1", "Резистор", ComponentKind.RESISTOR, _two_pin_footprint(), value=220, unit=Unit.OHM)
    assert c.pin_count == 2


def test_component_requires_value_and_unit_together():
    with pytest.raises(ValueError):
        Component("R1", "Резистор", ComponentKind.RESISTOR, _two_pin_footprint(), value=220, unit=None)
    with pytest.raises(ValueError):
        Component("R1", "Резистор", ComponentKind.RESISTOR, _two_pin_footprint(), value=None, unit=Unit.OHM)


def test_component_without_value_is_allowed():
    c = Component("U1", "Мікросхема", ComponentKind.IC, _two_pin_footprint())
    assert c.value_str() == "—"


@pytest.mark.parametrize(
    "value,unit,expected",
    [
        (220, Unit.OHM, "220 Ом"),
        (4700, Unit.OHM, "4.7 кОм"),
        (1_000_000, Unit.OHM, "1 МОм"),
        (1000, Unit.OHM, "1 кОм"),
        (100e-9, Unit.FARAD, "100 нФ"),
        (10e-6, Unit.FARAD, "10 мкФ"),
        (5.0, Unit.VOLT, "5 В"),
        (0.02, Unit.AMPERE, "20 мА"),
        (0, Unit.OHM, "0 Ом"),
    ],
)
def test_value_str_formats_with_si_prefix(value, unit, expected):
    c = Component("X1", "Компонент", ComponentKind.RESISTOR, _two_pin_footprint(), value=value, unit=unit)
    assert c.value_str() == expected
