import pytest

from kovadlo.pcb_footprints import (
    connector_footprint,
    dip_footprint,
    soic_footprint,
    to92_footprint,
    two_pin_footprint,
)


def test_dip8_pin_count_and_name():
    fp = dip_footprint(8)
    assert fp.name == "DIP-8"
    assert fp.pin_count == 8


def test_dip8_standard_pitch_and_row_spacing():
    fp = dip_footprint(8)
    assert fp.pin(1).position.x == pytest.approx(0.0)
    assert fp.pin(2).position.x == pytest.approx(2.54)
    assert fp.pin(1).position.z == pytest.approx(0.0)
    assert fp.pin(5).position.z == pytest.approx(7.62)


def test_dip_numbering_is_counterclockwise_standard():
    """Стандартна DIP-нумерація: вивід N навпроти виводу (pin_count/2 + 1 - N)
    по протилежному ряду — тобто pin4 навпроти pin5, pin1 навпроти pin8."""
    fp = dip_footprint(8)
    assert fp.pin(4).position.x == pytest.approx(fp.pin(5).position.x)
    assert fp.pin(1).position.x == pytest.approx(fp.pin(8).position.x)
    assert fp.pin(1).position.z != fp.pin(8).position.z  # різні ряди


def test_dip_rejects_odd_pin_count():
    with pytest.raises(ValueError):
        dip_footprint(7)


def test_soic8_uses_finer_pitch_than_dip8():
    dip = dip_footprint(8)
    soic = soic_footprint(8)
    assert soic.name == "SOIC-8"
    assert soic.pin(2).position.x < dip.pin(2).position.x
    # та сама (проти годинникова) нумерація, лише дрібніший крок
    assert soic.pin(4).position.x == pytest.approx(soic.pin(5).position.x)


def test_two_pin_footprint_spacing():
    fp = two_pin_footprint("0805", spacing=2.0)
    assert fp.pin_count == 2
    assert fp.pin(1).position.x == pytest.approx(0.0)
    assert fp.pin(2).position.x == pytest.approx(2.0)


def test_connector_footprint_row_of_pins():
    fp = connector_footprint(4, pitch=2.54)
    assert fp.pin_count == 4
    assert fp.pin(4).position.x == pytest.approx(3 * 2.54)


def test_connector_requires_at_least_one_pin():
    with pytest.raises(ValueError):
        connector_footprint(0)


def test_to92_has_three_pins_named_ebc():
    fp = to92_footprint()
    assert fp.pin_count == 3
    assert [p.name for p in sorted(fp.pins, key=lambda p: p.number)] == ["E", "B", "C"]
