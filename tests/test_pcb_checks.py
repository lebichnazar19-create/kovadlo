import pytest

from kovadlo.geometry import Point
from kovadlo.pcb_component import Component, ComponentKind, Unit
from kovadlo.pcb_footprints import two_pin_footprint
from kovadlo.pcb_board import Board, Placement, Track, Via
from kovadlo.pcb_checks import clearance_violations, unrouted_connections
from kovadlo.pcb_netlist import Net, NetKind, Netlist, PinRef
from kovadlo.pcb_norms import Layer


def _resistor(ref: str, spacing: float = 5.0) -> Component:
    return Component(ref, "Резистор", ComponentKind.RESISTOR, two_pin_footprint("THT-2", spacing=spacing), 220, Unit.OHM)


def _board_with_two_resistors() -> tuple[Board, Component, Component]:
    r1, r2 = _resistor("R1"), _resistor("R2")
    board = Board(contour=[Point(-5, -5), Point(30, -5), Point(30, 10), Point(-5, 10)])
    board.placements["R1"] = Placement(component=r1, position=Point(0, 0))
    board.placements["R2"] = Placement(component=r2, position=Point(20, 0))
    return board, r1, r2


# ---------------------------------------------------------------------------
# Ratsnest
# ---------------------------------------------------------------------------


def test_ratsnest_reports_gap_when_no_track_drawn():
    board, r1, r2 = _board_with_two_resistors()
    nl = Netlist(components={"R1": r1, "R2": r2}, nets=[Net("SIG", pins=[PinRef("R1", 2), PinRef("R2", 1)])])
    gaps = unrouted_connections(nl, board)
    assert len(gaps) == 1
    assert gaps[0].net == "SIG"


def test_ratsnest_clear_after_direct_track():
    board, r1, r2 = _board_with_two_resistors()
    nl = Netlist(components={"R1": r1, "R2": r2}, nets=[Net("SIG", pins=[PinRef("R1", 2), PinRef("R2", 1)])])
    p1 = board.placements["R1"].pin_position(2)
    p2 = board.placements["R2"].pin_position(1)
    board.tracks.append(Track(points=[p1, p2], width_mm=0.4, layer=Layer.TOP, net="SIG"))
    assert unrouted_connections(nl, board) == []


def test_ratsnest_connected_via_intermediate_bend_point():
    board, r1, r2 = _board_with_two_resistors()
    nl = Netlist(components={"R1": r1, "R2": r2}, nets=[Net("SIG", pins=[PinRef("R1", 2), PinRef("R2", 1)])])
    p1 = board.placements["R1"].pin_position(2)
    p2 = board.placements["R2"].pin_position(1)
    bend = Point((p1.x + p2.x) / 2, p1.z + 5)
    board.tracks.append(Track(points=[p1, bend, p2], width_mm=0.4, layer=Layer.TOP, net="SIG"))
    assert unrouted_connections(nl, board) == []


def test_ratsnest_requires_via_to_bridge_layers():
    board, r1, r2 = _board_with_two_resistors()
    nl = Netlist(components={"R1": r1, "R2": r2}, nets=[Net("SIG", pins=[PinRef("R1", 2), PinRef("R2", 1)])])
    p1 = board.placements["R1"].pin_position(2)
    p2 = board.placements["R2"].pin_position(1)
    mid = Point((p1.x + p2.x) / 2, p1.z)

    # доріжка на ВЕРХНЬОМУ шарі до середини, і ОКРЕМА доріжка на НИЖНЬОМУ
    # шарі від тієї самої середини далі — без via це не одне з'єднання
    board.tracks.append(Track(points=[p1, mid], width_mm=0.4, layer=Layer.TOP, net="SIG"))
    board.tracks.append(Track(points=[mid, p2], width_mm=0.4, layer=Layer.BOTTOM, net="SIG"))
    gaps = unrouted_connections(nl, board)
    assert len(gaps) == 1

    # додаємо перехідний отвір саме в точці стику — тепер з'єднання ціле
    board.vias.append(Via(position=mid, net="SIG", drill_diameter_mm=0.3, pad_diameter_mm=0.6))
    assert unrouted_connections(nl, board) == []


def test_ratsnest_skips_unplaced_components():
    r1, r2 = _resistor("R1"), _resistor("R2")
    board = Board(contour=[Point(-5, -5), Point(30, -5), Point(30, 10), Point(-5, 10)])
    board.placements["R1"] = Placement(component=r1, position=Point(0, 0))
    # R2 навмисно НЕ розміщений на платі
    nl = Netlist(components={"R1": r1, "R2": r2}, nets=[Net("SIG", pins=[PinRef("R1", 2), PinRef("R2", 1)])])
    assert unrouted_connections(nl, board) == []


def test_ratsnest_three_pin_net_partial_connection():
    r1, r2, r3 = _resistor("R1"), _resistor("R2"), _resistor("R3")
    board = Board(contour=[Point(-5, -5), Point(50, -5), Point(50, 10), Point(-5, 10)])
    board.placements["R1"] = Placement(component=r1, position=Point(0, 0))
    board.placements["R2"] = Placement(component=r2, position=Point(20, 0))
    board.placements["R3"] = Placement(component=r3, position=Point(40, 0))
    nl = Netlist(
        components={"R1": r1, "R2": r2, "R3": r3},
        nets=[Net("SIG", pins=[PinRef("R1", 2), PinRef("R2", 1), PinRef("R3", 1)])],
    )
    # з'єднуємо тільки R1-R2, R3 лишається "висіти"
    p1 = board.placements["R1"].pin_position(2)
    p2 = board.placements["R2"].pin_position(1)
    board.tracks.append(Track(points=[p1, p2], width_mm=0.4, layer=Layer.TOP, net="SIG"))
    gaps = unrouted_connections(nl, board)
    assert len(gaps) == 1
    assert gaps[0].pin_b == PinRef("R3", 1)


# ---------------------------------------------------------------------------
# Зазори
# ---------------------------------------------------------------------------


def test_clearance_violation_for_close_parallel_tracks():
    board, r1, r2 = _board_with_two_resistors()
    board.tracks.append(Track(points=[Point(0, 0), Point(20, 0)], width_mm=0.3, layer=Layer.TOP, net="A"))
    board.tracks.append(Track(points=[Point(0, 0.05), Point(20, 0.05)], width_mm=0.3, layer=Layer.TOP, net="B"))
    nl = Netlist(
        components={"R1": r1, "R2": r2},
        nets=[
            Net("A", pins=[PinRef("R1", 1)], voltage_v=5.0),
            Net("B", pins=[PinRef("R2", 1)], voltage_v=0.0),
        ],
    )
    violations = clearance_violations(board, nl)
    assert len(violations) == 1
    assert violations[0].distance_mm == pytest.approx(0.05, abs=1e-6)
    assert violations[0].required_mm == pytest.approx(0.10)


def test_no_clearance_violation_when_far_enough_apart():
    board, r1, r2 = _board_with_two_resistors()
    board.tracks.append(Track(points=[Point(0, 0), Point(20, 0)], width_mm=0.3, layer=Layer.TOP, net="A"))
    board.tracks.append(Track(points=[Point(0, 5), Point(20, 5)], width_mm=0.3, layer=Layer.TOP, net="B"))
    nl = Netlist(
        components={"R1": r1, "R2": r2},
        nets=[Net("A", pins=[PinRef("R1", 1)], voltage_v=5.0), Net("B", pins=[PinRef("R2", 1)], voltage_v=0.0)],
    )
    assert clearance_violations(board, nl) == []


def test_clearance_ignores_tracks_of_same_net():
    board, r1, r2 = _board_with_two_resistors()
    board.tracks.append(Track(points=[Point(0, 0), Point(20, 0)], width_mm=0.3, layer=Layer.TOP, net="A"))
    board.tracks.append(Track(points=[Point(0, 0.01), Point(20, 0.01)], width_mm=0.3, layer=Layer.TOP, net="A"))
    nl = Netlist(components={"R1": r1, "R2": r2}, nets=[Net("A", pins=[PinRef("R1", 1)])])
    assert clearance_violations(board, nl) == []


def test_clearance_ignores_tracks_on_different_layers():
    board, r1, r2 = _board_with_two_resistors()
    board.tracks.append(Track(points=[Point(0, 0), Point(20, 0)], width_mm=0.3, layer=Layer.TOP, net="A"))
    board.tracks.append(Track(points=[Point(0, 0.01), Point(20, 0.01)], width_mm=0.3, layer=Layer.BOTTOM, net="B"))
    nl = Netlist(
        components={"R1": r1, "R2": r2},
        nets=[Net("A", pins=[PinRef("R1", 1)]), Net("B", pins=[PinRef("R2", 1)])],
    )
    assert clearance_violations(board, nl) == []


def test_clearance_uses_default_voltage_when_net_voltage_unknown():
    board, r1, r2 = _board_with_two_resistors()
    board.tracks.append(Track(points=[Point(0, 0), Point(20, 0)], width_mm=0.3, layer=Layer.TOP, net="A"))
    board.tracks.append(Track(points=[Point(0, 0.05), Point(20, 0.05)], width_mm=0.3, layer=Layer.TOP, net="B"))
    nl = Netlist(components={"R1": r1, "R2": r2}, nets=[Net("A", pins=[PinRef("R1", 1)]), Net("B", pins=[PinRef("R2", 1)])])
    violations = clearance_violations(board, nl, default_voltage_v=24.0)
    assert len(violations) == 1
    assert violations[0].required_mm == pytest.approx(0.10)  # <=30В у таблиці
