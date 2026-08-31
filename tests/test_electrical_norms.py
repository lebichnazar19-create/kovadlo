import math

import pytest

from kovadlo.electrical_norms import (
    AMPACITY_A,
    COPPER_RESISTIVITY_OHM_MM2_PER_M,
    STANDARD_BREAKER_RATINGS_A,
    STANDARD_CROSS_SECTIONS_MM2,
    PhaseType,
    calculate_current_a,
    rcd_required_for_kinds,
    select_breaker_rating_a,
    select_cross_section_mm2,
    voltage_drop_percent,
)
from kovadlo.electrical_point import PointKind

# ---------------------------------------------------------------------------
# Струм
# ---------------------------------------------------------------------------


def test_current_single_phase_round_number():
    # 2300 Вт / 230 В = рівно 10 А — зручне кругле число для перевірки формули
    assert calculate_current_a(2300.0, PhaseType.SINGLE, power_factor=1.0) == pytest.approx(10.0)


def test_current_three_phase_matches_independent_formula():
    power = 8000.0
    expected = power / (math.sqrt(3) * 400.0)
    assert calculate_current_a(power, PhaseType.THREE, power_factor=1.0) == pytest.approx(expected)


def test_current_scales_inversely_with_power_factor():
    at_pf1 = calculate_current_a(1000.0, PhaseType.SINGLE, power_factor=1.0)
    at_pf_half = calculate_current_a(1000.0, PhaseType.SINGLE, power_factor=0.5)
    assert at_pf_half == pytest.approx(at_pf1 * 2)


def test_current_rejects_non_positive_power_factor():
    with pytest.raises(ValueError):
        calculate_current_a(1000.0, PhaseType.SINGLE, power_factor=0)


# ---------------------------------------------------------------------------
# Падіння напруги — числа перевірені вручну (див. коментарі з розрахунком)
# ---------------------------------------------------------------------------


def test_voltage_drop_single_phase_hand_calculation():
    # ΔU = (2 * 20 * 10 * 0.0225) / 1.5 = 6.0 В -> 6.0/230*100 = 2.6086956...%
    drop = voltage_drop_percent(cross_section_mm2=1.5, current_a=10.0, length_m=20.0, phase=PhaseType.SINGLE)
    assert drop == pytest.approx(6.0 / 230.0 * 100.0)


def test_voltage_drop_three_phase_matches_independent_formula():
    drop = voltage_drop_percent(cross_section_mm2=6.0, current_a=20.0, length_m=15.0, phase=PhaseType.THREE)
    expected_v = (math.sqrt(3) * 15.0 * 20.0 * COPPER_RESISTIVITY_OHM_MM2_PER_M) / 6.0
    assert drop == pytest.approx(expected_v / 400.0 * 100.0)


def test_voltage_drop_rejects_non_positive_cross_section():
    with pytest.raises(ValueError):
        voltage_drop_percent(cross_section_mm2=0, current_a=10.0, length_m=10.0, phase=PhaseType.SINGLE)


# ---------------------------------------------------------------------------
# Вибір номіналу автомата
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "current,expected",
    [(1.3, 6.0), (6.0, 6.0), (6.1, 10.0), (15.9, 16.0), (16.0, 16.0), (63.5, 80.0)],
)
def test_select_breaker_rating(current, expected):
    assert select_breaker_rating_a(current) == expected


def test_select_breaker_rating_raises_above_table_maximum():
    with pytest.raises(ValueError):
        select_breaker_rating_a(STANDARD_BREAKER_RATINGS_A[-1] + 1)


# ---------------------------------------------------------------------------
# Вибір перерізу — вручну перевірені сценарії
# ---------------------------------------------------------------------------


def test_select_cross_section_picks_smallest_when_short_run():
    # струм 10 А, автомат 16 А, довжина 20 м, переріз 1.5 мм² (ампacity 17.5 >= 16):
    # ΔU = (2*20*10*0.0225)/1.5 = 6.0 В -> 2.6087% <= 3% -> має вистачити 1.5 мм²
    section = select_cross_section_mm2(
        design_current_a=10.0, breaker_rating_a=16.0, length_m=20.0, phase=PhaseType.SINGLE, min_cross_section_mm2=1.5
    )
    assert section == 1.5


def test_select_cross_section_bumps_up_for_long_run():
    # та сама схема, але траса 60 м: на 1.5 і 2.5 мм² падіння напруги вже
    # понад 3%, а на 4 мм² вкладається:
    #   S=1.5: (2*60*10*0.0225)/1.5 = 18.0 В -> 7.826%
    #   S=2.5: (2*60*10*0.0225)/2.5 = 10.8 В -> 4.696%
    #   S=4.0: (2*60*10*0.0225)/4.0 = 6.75 В -> 2.935% <= 3% OK
    section = select_cross_section_mm2(
        design_current_a=10.0, breaker_rating_a=16.0, length_m=60.0, phase=PhaseType.SINGLE, min_cross_section_mm2=1.5
    )
    assert section == 4.0


def test_select_cross_section_respects_minimum():
    # 1.5 мм² задовольнив би і струм, і падіння напруги на короткій трасі,
    # але мінімум для кола заданий 2.5 мм² -> має повернути саме 2.5
    section = select_cross_section_mm2(
        design_current_a=5.0, breaker_rating_a=6.0, length_m=5.0, phase=PhaseType.SINGLE, min_cross_section_mm2=2.5
    )
    assert section == 2.5


def test_select_cross_section_raises_when_route_too_long_for_table():
    with pytest.raises(ValueError):
        select_cross_section_mm2(
            design_current_a=10.0,
            breaker_rating_a=16.0,
            length_m=500.0,
            phase=PhaseType.SINGLE,
            min_cross_section_mm2=1.5,
        )


def test_ampacity_table_covers_every_standard_cross_section():
    for section in STANDARD_CROSS_SECTIONS_MM2:
        assert section in AMPACITY_A
        assert AMPACITY_A[section] > 0


# ---------------------------------------------------------------------------
# ПЗВ / дифавтомат
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kinds,expected",
    [
        ({PointKind.SOCKET}, True),
        ({PointKind.SOCKET, PointKind.LIGHT}, True),
        ({PointKind.BOILER}, True),
        ({PointKind.STOVE}, True),
        ({PointKind.LIGHT, PointKind.SWITCH}, False),
        ({PointKind.LIGHT}, False),
    ],
)
def test_rcd_required_for_kinds(kinds, expected):
    required, note = rcd_required_for_kinds(kinds)
    assert required is expected
    assert isinstance(note, str) and note
