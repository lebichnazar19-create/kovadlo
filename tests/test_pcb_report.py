import pytest

from kovadlo.geometry import Point
from kovadlo.pcb_component import Component, ComponentKind, Unit
from kovadlo.pcb_footprints import two_pin_footprint
from kovadlo.pcb_board import Board, Placement, Track
from kovadlo.pcb_netlist import Net, NetKind, Netlist, PinRef
from kovadlo.pcb_norms import Layer
from kovadlo.pcb_report import format_board_report


def _resistor(ref: str, value: float = 220) -> Component:
    return Component(ref, "Резистор", ComponentKind.RESISTOR, two_pin_footprint("THT-2"), value, Unit.OHM)


def _simple_setup():
    r1, r2 = _resistor("R1"), _resistor("R2", value=470)
    board = Board(
        name="Тестова плата",
        contour=[Point(0, 0), Point(30, 0), Point(30, 20), Point(0, 20)],
    )
    board.placements["R1"] = Placement(component=r1, position=Point(5, 5))
    board.placements["R2"] = Placement(component=r2, position=Point(20, 5))
    nl = Netlist(components={"R1": r1, "R2": r2}, nets=[Net("SIG", pins=[PinRef("R1", 2), PinRef("R2", 1)])])
    return board, nl


def test_report_contains_bom_with_correct_quantities():
    board, nl = _simple_setup()
    report = format_board_report(board, nl)
    assert "Специфікація компонентів (BOM):" in report
    assert "1 x Резистор (резистор), 220 Ом, THT-2 — R1" in report
    assert "1 x Резистор (резистор), 470 Ом, THT-2 — R2" in report


def test_report_groups_identical_parts_in_bom():
    r1, r2 = _resistor("R1", value=220), _resistor("R2", value=220)
    board = Board(contour=[Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)])
    nl = Netlist(components={"R1": r1, "R2": r2}, nets=[])
    report = format_board_report(board, nl)
    assert "2 x Резистор (резистор), 220 Ом, THT-2 — R1, R2" in report


def test_report_flags_dangling_pins():
    board, nl = _simple_setup()
    report = format_board_report(board, nl)
    assert "Висячі виводи" in report
    assert "R1.1" in report
    assert "R2.2" in report


def test_report_no_dangling_pins_message_when_all_connected():
    r1 = _resistor("R1")
    board = Board(contour=[Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)])
    board.placements["R1"] = Placement(component=r1, position=Point(2, 2))
    nl = Netlist(
        components={"R1": r1},
        nets=[Net("A", NetKind.POWER, pins=[PinRef("R1", 1)]), Net("B", NetKind.GROUND, pins=[PinRef("R1", 2)])],
    )
    report = format_board_report(board, nl)
    assert "Висячих виводів немає." in report


def test_report_flags_power_ground_short():
    r1 = _resistor("R1")
    board = Board(contour=[Point(0, 0), Point(10, 0), Point(10, 10), Point(0, 10)])
    nl = Netlist(
        components={"R1": r1},
        nets=[
            Net("VCC", NetKind.POWER, pins=[PinRef("R1", 1)]),
            Net("GND", NetKind.GROUND, pins=[PinRef("R1", 1)]),
        ],
    )
    report = format_board_report(board, nl)
    assert "КОРОТКЕ ЗАМИКАННЯ живлення на землю" in report
    assert "R1.1" in report


def test_report_no_tracks_message():
    board, nl = _simple_setup()
    report = format_board_report(board, nl)
    assert "Доріжок ще немає." in report


def test_report_track_resistance_and_ipc2221_verdict():
    board, nl = _simple_setup()
    p1 = board.placements["R1"].pin_position(2)
    p2 = board.placements["R2"].pin_position(1)
    board.tracks.append(Track(points=[p1, p2], width_mm=0.3, layer=Layer.TOP, net="SIG"))

    report = format_board_report(board, nl, net_currents_a={"SIG": 0.05})
    assert "ланцюг «SIG»" in report
    assert "шар верхній" in report
    assert "OK" in report  # 0.05 А — вузька доріжка (0.3мм) цілком витримує

    report_overload = format_board_report(board, nl, net_currents_a={"SIG": 5.0})
    assert "ЗАВУЗЬКА" in report_overload


def test_report_ratsnest_all_connected_message():
    board, nl = _simple_setup()
    p1 = board.placements["R1"].pin_position(2)
    p2 = board.placements["R2"].pin_position(1)
    board.tracks.append(Track(points=[p1, p2], width_mm=0.3, layer=Layer.TOP, net="SIG"))
    report = format_board_report(board, nl)
    assert "Усі з'єднання нетлиста реалізовано доріжками." in report


def test_report_ratsnest_gap_listed():
    board, nl = _simple_setup()
    report = format_board_report(board, nl)
    assert "не з'єднано з" in report


def test_report_clearance_no_violations_message():
    board, nl = _simple_setup()
    report = format_board_report(board, nl)
    assert "Порушень мінімальних зазорів не знайдено." in report
