import pytest

from kovadlo.pcb_norms import (
    COPPER_RESISTIVITY_OHM_MM2_PER_M,
    IPC2221_EXPONENT_AREA,
    IPC2221_EXPONENT_DELTA_T,
    IPC2221_K_EXTERNAL,
    MIN_TRACK_WIDTH_MM,
    min_clearance_mm,
    required_cross_section_mil2,
    required_track_width_mm,
    track_cross_section_mm2,
    track_resistance_ohm,
    track_voltage_drop_v,
)


def test_required_cross_section_matches_ipc2221_formula_directly():
    """A = (I / (k·ΔT^0.44))^(1/0.725) — рахуємо очікуване значення тим
    самим виразом незалежно від функції, щоб перевірити структуру формули."""
    current, delta_t = 2.0, 20.0
    expected = (current / (IPC2221_K_EXTERNAL * delta_t**IPC2221_EXPONENT_DELTA_T)) ** (1 / IPC2221_EXPONENT_AREA)
    assert required_cross_section_mil2(current, temperature_rise_c=delta_t) == pytest.approx(expected)


def test_required_cross_section_rejects_non_positive_inputs():
    with pytest.raises(ValueError):
        required_cross_section_mil2(0, temperature_rise_c=10)
    with pytest.raises(ValueError):
        required_cross_section_mil2(1, temperature_rise_c=0)


def test_required_track_width_hand_calculation_1a_10c():
    # A = (1 / (0.048 * 10^0.44))^(1/0.725) ≈ 16.31 mil²
    # товщина 35 мкм = 35/25.4 ≈ 1.378 mil -> ширина ≈ 16.31/1.378 ≈ 11.84 mil ≈ 0.3006 мм
    width = required_track_width_mm(1.0, temperature_rise_c=10.0)
    assert width == pytest.approx(0.3006, abs=2e-3)


def test_required_track_width_respects_manufacturing_minimum():
    tiny_current = 1e-6
    width = required_track_width_mm(tiny_current, temperature_rise_c=10.0)
    assert width == MIN_TRACK_WIDTH_MM


def test_wider_track_needed_for_higher_current():
    w_small = required_track_width_mm(0.3, temperature_rise_c=10.0)
    w_large = required_track_width_mm(3.0, temperature_rise_c=10.0)
    assert w_large > w_small


def test_track_cross_section_is_width_times_thickness():
    # 1 мм ширини, 35 мкм = 0.035 мм товщини -> 0.035 мм²
    assert track_cross_section_mm2(1.0, copper_thickness_um=35.0) == pytest.approx(0.035)


def test_track_resistance_hand_calculation():
    # R = ρ·L/A; L=0.1 м, A=0.5мм*0.035мм=0.0175 мм² -> R = 0.018*0.1/0.0175
    expected = COPPER_RESISTIVITY_OHM_MM2_PER_M * 0.1 / (0.5 * 0.035)
    r = track_resistance_ohm(length_mm=100, width_mm=0.5, copper_thickness_um=35.0)
    assert r == pytest.approx(expected)
    assert r == pytest.approx(0.1029, abs=1e-3)


def test_track_resistance_rejects_non_positive_geometry():
    with pytest.raises(ValueError):
        track_resistance_ohm(length_mm=10, width_mm=0)


def test_track_voltage_drop_is_current_times_resistance():
    r = track_resistance_ohm(length_mm=100, width_mm=0.5)
    drop = track_voltage_drop_v(2.0, length_mm=100, width_mm=0.5)
    assert drop == pytest.approx(2.0 * r)


@pytest.mark.parametrize(
    "voltage,expected",
    [(10, 0.10), (15, 0.10), (24, 0.10), (50, 0.13), (100, 0.13), (200, 0.80), (250, 0.80)],
)
def test_min_clearance_table_lookup(voltage, expected):
    assert min_clearance_mm(voltage) == pytest.approx(expected)


def test_min_clearance_uses_absolute_voltage():
    assert min_clearance_mm(-24) == min_clearance_mm(24)


def test_min_clearance_raises_above_table_range():
    with pytest.raises(ValueError):
        min_clearance_mm(10_000)
