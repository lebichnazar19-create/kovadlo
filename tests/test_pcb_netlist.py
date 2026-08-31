import pytest

from kovadlo.pcb_component import Component, ComponentKind, Unit
from kovadlo.pcb_footprints import two_pin_footprint
from kovadlo.pcb_netlist import Net, NetKind, Netlist, PinRef


def _resistor(ref: str) -> Component:
    return Component(ref, "Резистор", ComponentKind.RESISTOR, two_pin_footprint("THT-2"), 220, Unit.OHM)


def test_netlist_rejects_reference_to_unknown_component():
    with pytest.raises(ValueError):
        Netlist(components={"R1": _resistor("R1")}, nets=[Net("N1", pins=[PinRef("R2", 1)])])


def test_netlist_rejects_reference_to_unknown_pin_number():
    with pytest.raises(ValueError):
        Netlist(components={"R1": _resistor("R1")}, nets=[Net("N1", pins=[PinRef("R1", 99)])])


def test_net_requires_at_least_one_pin():
    with pytest.raises(ValueError):
        Net("N1", pins=[])


def test_all_pin_refs_lists_every_physical_pin():
    nl = Netlist(components={"R1": _resistor("R1"), "R2": _resistor("R2")}, nets=[])
    refs = nl.all_pin_refs()
    assert len(refs) == 4  # два виводи на кожен з двох резисторів
    assert PinRef("R1", 1) in refs
    assert PinRef("R2", 2) in refs


def test_dangling_pins_lists_unconnected_pins():
    nl = Netlist(
        components={"R1": _resistor("R1"), "R2": _resistor("R2")},
        nets=[Net("SIG", pins=[PinRef("R1", 2), PinRef("R2", 1)])],
    )
    dangling = nl.dangling_pins()
    assert set(dangling) == {PinRef("R1", 1), PinRef("R2", 2)}


def test_no_dangling_pins_when_fully_connected():
    nl = Netlist(
        components={"R1": _resistor("R1"), "R2": _resistor("R2")},
        nets=[
            Net("SIG", pins=[PinRef("R1", 2), PinRef("R2", 1)]),
            Net("VCC", NetKind.POWER, pins=[PinRef("R1", 1)]),
            Net("GND", NetKind.GROUND, pins=[PinRef("R2", 2)]),
        ],
    )
    assert nl.dangling_pins() == []


def test_short_circuit_detected_when_pin_in_two_nets():
    nl = Netlist(
        components={"R1": _resistor("R1")},
        nets=[
            Net("A", pins=[PinRef("R1", 1)]),
            Net("B", pins=[PinRef("R1", 1)]),
        ],
    )
    shorts = nl.short_circuits()
    assert len(shorts) == 1
    assert shorts[0].pin == PinRef("R1", 1)
    assert set(shorts[0].nets) == {"A", "B"}


def test_power_ground_short_flagged_specifically():
    nl = Netlist(
        components={"R1": _resistor("R1")},
        nets=[
            Net("VCC", NetKind.POWER, pins=[PinRef("R1", 1)]),
            Net("GND", NetKind.GROUND, pins=[PinRef("R1", 1)]),
        ],
    )
    assert len(nl.short_circuits()) == 1
    pg = nl.power_ground_shorts()
    assert len(pg) == 1
    assert pg[0].pin == PinRef("R1", 1)


def test_short_between_two_signal_nets_is_not_a_power_ground_short():
    nl = Netlist(
        components={"R1": _resistor("R1")},
        nets=[
            Net("SIG_A", NetKind.SIGNAL, pins=[PinRef("R1", 1)]),
            Net("SIG_B", NetKind.SIGNAL, pins=[PinRef("R1", 1)]),
        ],
    )
    assert len(nl.short_circuits()) == 1
    assert nl.power_ground_shorts() == []


def test_net_of_returns_all_nets_containing_pin():
    nl = Netlist(
        components={"R1": _resistor("R1")},
        nets=[Net("A", pins=[PinRef("R1", 1)]), Net("B", pins=[PinRef("R1", 1)])],
    )
    nets = nl.net_of(PinRef("R1", 1))
    assert {n.name for n in nets} == {"A", "B"}
