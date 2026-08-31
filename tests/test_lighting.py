import pytest

from kovadlo.cable_route import build_route
from kovadlo.geometry import Point
from kovadlo.lighting import (
    FixtureKind,
    LightFixture,
    fixtures_needed,
    illuminance_lux,
    lighting_group,
    plan_lighting,
    required_luminous_flux_lm,
)
from kovadlo.lighting_norms import RoomPurpose


def test_fixture_rejects_non_positive_flux_or_power():
    with pytest.raises(ValueError):
        LightFixture("Св1", FixtureKind.CEILING, Point(0, 0), luminous_flux_lm=0, power_w=8)
    with pytest.raises(ValueError):
        LightFixture("Св1", FixtureKind.CEILING, Point(0, 0), luminous_flux_lm=800, power_w=0)


def test_luminous_efficacy():
    fixture = LightFixture("Св1", FixtureKind.CEILING, Point(0, 0), luminous_flux_lm=800, power_w=8)
    assert fixture.luminous_efficacy_lm_per_w == pytest.approx(100.0)


def test_to_consumption_point_bridges_to_module4():
    fixture = LightFixture("Св1", FixtureKind.CEILING, Point(1000, 500), luminous_flux_lm=800, power_w=8)
    point = fixture.to_consumption_point()
    assert point.name == "Св1"
    assert point.power_w == 8
    assert point.position == Point(1000, 500)


def test_illuminance_hand_calculation():
    # E = Φ·UF·MF/S = 8000*0.5*0.8/10 = 320 лк
    e = illuminance_lux(8000, 10, utilization_factor=0.5, maintenance_factor=0.8)
    assert e == pytest.approx(320.0)


def test_required_flux_is_inverse_of_illuminance():
    flux = required_luminous_flux_lm(320, 10, utilization_factor=0.5, maintenance_factor=0.8)
    assert flux == pytest.approx(8000.0)


def test_fixtures_needed_rounds_up():
    assert fixtures_needed(required_flux_lm=9000, fixture_flux_lm=806) == 12  # ceil(9000/806)=12


def test_plan_lighting_kitchen_hand_verified():
    """Кухня 12 м², світильник 806 лм/8Вт.

    required_flux = 300*12/(0.5*0.8) = 9000 лм
    count = ceil(9000/806) = 12
    achieved = 12*806*0.5*0.8/12 = 806*0.4 = 322.4 лк
    """
    plan = plan_lighting(area_m2=12, purpose=RoomPurpose.KITCHEN, fixture_flux_lm=806, fixture_power_w=8)
    assert plan.target_lux == 300.0
    assert plan.fixtures_count == 12
    assert plan.achieved_lux == pytest.approx(322.4)
    assert plan.total_power_w == pytest.approx(96.0)
    assert plan.meets_target is True


def test_lighting_group_totals_match_fixtures():
    f1 = LightFixture("Св1", FixtureKind.CEILING, Point(0, 0), luminous_flux_lm=800, power_w=8)
    f2 = LightFixture("Св2", FixtureKind.CEILING, Point(2000, 0), luminous_flux_lm=800, power_w=8)
    routes = {
        "Св1": build_route(Point(0, 0), [Point(0, 0)], snap=False),
        "Св2": build_route(Point(0, 0), [Point(2000, 0)], snap=False),
    }
    group = lighting_group([f1, f2], routes)
    assert group.total_power_w == pytest.approx(16.0)
