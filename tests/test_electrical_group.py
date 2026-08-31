import pytest

from kovadlo.cable_route import CableRoute
from kovadlo.electrical_group import Group, calculate_group
from kovadlo.electrical_norms import PhaseType
from kovadlo.electrical_point import ConsumptionPoint, PointKind
from kovadlo.geometry import Point


def _route(*points: tuple[float, float]) -> CableRoute:
    return CableRoute(points=[Point(x, z) for x, z in points])


def test_group_requires_at_least_one_point():
    with pytest.raises(ValueError):
        Group(name="Порожня", phase=PhaseType.SINGLE, points=[], routes={})


def test_group_requires_route_for_every_point():
    socket = ConsumptionPoint(name="Р1", kind=PointKind.SOCKET, position=Point(1000, 1000))
    with pytest.raises(ValueError):
        Group(name="Розетки", phase=PhaseType.SINGLE, points=[socket], routes={})


def test_group_totals_and_calculation_hand_verified():
    # три розетки по 100 Вт кожна = 300 Вт сумарно
    s1 = ConsumptionPoint(name="Р1", kind=PointKind.SOCKET, position=Point(2000, 3000))
    s2 = ConsumptionPoint(name="Р2", kind=PointKind.SOCKET, position=Point(4000, 3000))
    s3 = ConsumptionPoint(name="Р3", kind=PointKind.SOCKET, position=Point(4000, 3000))

    routes = {
        "Р1": _route((0, 0), (0, 3000), (2000, 3000)),  # 3000+2000 = 5000 мм = 5.0 м
        "Р2": _route((0, 0), (0, 3000), (4000, 3000)),  # 3000+4000 = 7000 мм = 7.0 м
        "Р3": _route((0, 0), (4000, 0), (4000, 3000)),  # 4000+3000 = 7000 мм = 7.0 м
    }

    group = Group(
        name="Розетки кухні",
        phase=PhaseType.SINGLE,
        points=[s1, s2, s3],
        routes=routes,
        connection_allowance_m=0.5,
        min_cross_section_mm2=2.5,
    )

    assert group.total_power_w == pytest.approx(300.0)
    expected_current = 300.0 / 230.0
    assert group.design_current_a == pytest.approx(expected_current)
    assert group.critical_route_length_m == pytest.approx(7.0)
    assert group.total_cable_length_m == pytest.approx((5.0 + 0.5) + (7.0 + 0.5) + (7.0 + 0.5))

    calc = calculate_group(group)
    assert calc.total_power_w == pytest.approx(300.0)
    assert calc.design_current_a == pytest.approx(expected_current)
    assert calc.breaker_rating_a == pytest.approx(6.0)  # 1.304 А -> найменший стандарт 6 А
    assert calc.cross_section_mm2 == pytest.approx(2.5)  # мінімум групи 2.5 мм², запас із головою
    expected_drop = (2 * 7.0 * expected_current * 0.0225) / 2.5 / 230.0 * 100.0
    assert calc.voltage_drop_percent == pytest.approx(expected_drop)
    assert calc.rcd_required is True
    assert "розетк" in calc.rcd_note


def test_group_three_phase_stove():
    stove = ConsumptionPoint(name="Плита", kind=PointKind.STOVE, position=Point(3900, 3000))
    routes = {"Плита": _route((0, 0), (0, 3000), (3900, 3000))}  # 3000+3900=6900мм=6.9м

    group = Group(
        name="Плита",
        phase=PhaseType.THREE,
        points=[stove],
        routes=routes,
        min_cross_section_mm2=6.0,
    )
    calc = calculate_group(group)

    assert calc.total_power_w == pytest.approx(7000.0)
    assert calc.phase is PhaseType.THREE
    assert calc.voltage_v == pytest.approx(400.0)
    assert calc.rcd_required is True
    # автомат: I = 7000/(sqrt(3)*400) ≈ 10.10 А -> найближчий стандарт зверху 16 А
    assert calc.breaker_rating_a == pytest.approx(16.0)
    assert calc.cross_section_mm2 == pytest.approx(6.0)


def test_group_lighting_only_does_not_require_rcd_by_default_rule():
    light = ConsumptionPoint(name="Св1", kind=PointKind.LIGHT, position=Point(2000, 1500))
    switch = ConsumptionPoint(name="Вим1", kind=PointKind.SWITCH, position=Point(150, 2900))
    routes = {
        "Св1": _route((100, 2900), (100, 1500), (2000, 1500)),
        "Вим1": _route((100, 2900), (150, 2900)),
    }
    group = Group(name="Освітлення", phase=PhaseType.SINGLE, points=[light, switch], routes=routes)
    calc = calculate_group(group)

    # вимикач не додає потужності
    assert calc.total_power_w == pytest.approx(light.power_w)
    assert calc.rcd_required is False
