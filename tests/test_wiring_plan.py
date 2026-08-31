import pytest

from kovadlo.cable_route import CableRoute
from kovadlo.electrical_group import Group
from kovadlo.electrical_norms import PhaseType
from kovadlo.electrical_point import ConsumptionPoint, PointKind
from kovadlo.geometry import Point
from kovadlo.wiring_plan import WiringPlan, format_wiring_report


def _route(*points: tuple[float, float]) -> CableRoute:
    return CableRoute(points=[Point(x, z) for x, z in points])


def _panel() -> ConsumptionPoint:
    return ConsumptionPoint(name="Щиток", kind=PointKind.PANEL, position=Point(100, 2900))


def test_plan_requires_panel_kind():
    not_a_panel = ConsumptionPoint(name="Х", kind=PointKind.SOCKET, position=Point(0, 0))
    socket = ConsumptionPoint(name="Р1", kind=PointKind.SOCKET, position=Point(1000, 1000))
    group = Group(
        name="Розетки", phase=PhaseType.SINGLE, points=[socket], routes={"Р1": _route((0, 0), (1000, 1000))}
    )
    with pytest.raises(ValueError):
        WiringPlan(panel=not_a_panel, groups=[group])


def test_plan_requires_at_least_one_group():
    with pytest.raises(ValueError):
        WiringPlan(panel=_panel(), groups=[])


def test_plan_calculations_return_one_result_per_group():
    socket = ConsumptionPoint(name="Р1", kind=PointKind.SOCKET, position=Point(2000, 3000))
    light = ConsumptionPoint(name="Св1", kind=PointKind.LIGHT, position=Point(2000, 1500))
    sockets_group = Group(
        name="Розетки",
        phase=PhaseType.SINGLE,
        points=[socket],
        routes={"Р1": _route((100, 2900), (100, 3000), (2000, 3000))},
        min_cross_section_mm2=2.5,
    )
    lighting_group = Group(
        name="Освітлення",
        phase=PhaseType.SINGLE,
        points=[light],
        routes={"Св1": _route((100, 2900), (100, 1500), (2000, 1500))},
    )
    plan = WiringPlan(panel=_panel(), groups=[sockets_group, lighting_group])

    calcs = plan.calculations()
    assert len(calcs) == 2
    assert {c.group_name for c in calcs} == {"Розетки", "Освітлення"}


def test_report_contains_group_and_spec_sections():
    socket = ConsumptionPoint(name="Р1", kind=PointKind.SOCKET, position=Point(2000, 3000))
    group = Group(
        name="Розетки",
        phase=PhaseType.SINGLE,
        points=[socket],
        routes={"Р1": _route((100, 2900), (100, 3000), (2000, 3000))},
        min_cross_section_mm2=2.5,
    )
    plan = WiringPlan(panel=_panel(), groups=[group])
    report = format_wiring_report(plan)

    assert "Щиток «Щиток»" in report
    assert "Група «Розетки»" in report
    assert "Розетка" not in report  # виводиться kind.value, тобто "розетка" з малої
    assert "розетка" in report
    assert "Автоматичний вимикач" in report
    assert "ПЗВ" in report
    assert "Специфікація кабелів на закупівлю" in report
    assert "Разом кабелю за перерізом" in report
    assert "Р1" in report


def test_report_cable_spec_totals_match_group_lengths():
    s1 = ConsumptionPoint(name="Р1", kind=PointKind.SOCKET, position=Point(2000, 3000))
    s2 = ConsumptionPoint(name="Р2", kind=PointKind.SOCKET, position=Point(4000, 3000))
    routes = {
        "Р1": _route((100, 2900), (100, 3000), (2000, 3000)),
        "Р2": _route((100, 2900), (100, 3000), (4000, 3000)),
    }
    group = Group(
        name="Розетки", phase=PhaseType.SINGLE, points=[s1, s2], routes=routes, min_cross_section_mm2=2.5
    )
    plan = WiringPlan(panel=_panel(), groups=[group])

    calc = plan.calculations()[0]
    report = format_wiring_report(plan)

    # довжина кожного кабелю в специфікації включно із запасом на підключення
    for point_name, route in group.routes.items():
        expected_len = route.length_m + group.connection_allowance_m
        assert f"{expected_len:.2f}" in report

    # сума за перерізом дорівнює total_cable_length_m групи (лиш одна група -> один переріз)
    assert f"{calc.cross_section_mm2:.1f} мм²: {group.total_cable_length_m:.2f} м" in report


def test_report_multiple_groups_different_phases():
    socket = ConsumptionPoint(name="Р1", kind=PointKind.SOCKET, position=Point(2000, 3000))
    stove = ConsumptionPoint(name="Плита", kind=PointKind.STOVE, position=Point(3900, 3000))
    sockets_group = Group(
        name="Розетки",
        phase=PhaseType.SINGLE,
        points=[socket],
        routes={"Р1": _route((100, 2900), (100, 3000), (2000, 3000))},
        min_cross_section_mm2=2.5,
    )
    stove_group = Group(
        name="Плита",
        phase=PhaseType.THREE,
        points=[stove],
        routes={"Плита": _route((100, 2900), (100, 3000), (3900, 3000))},
        min_cross_section_mm2=6.0,
    )
    plan = WiringPlan(panel=_panel(), groups=[sockets_group, stove_group])
    report = format_wiring_report(plan)

    assert "однофазна" in report
    assert "трифазна" in report
    assert "400" in report
    assert "230" in report
