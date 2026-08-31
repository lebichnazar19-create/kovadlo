from kovadlo.ventilation_norms import (
    AIR_CHANGES_PER_HOUR,
    MINIMUM_EXHAUST_M3_H,
    STANDARD_FANS,
    STANDARD_ROUND_DUCT_DIAMETERS_MM,
    VentilatedRoomKind,
)


def test_wet_rooms_have_fixed_minimum_exhaust():
    assert MINIMUM_EXHAUST_M3_H[VentilatedRoomKind.KITCHEN] == 50.0
    assert MINIMUM_EXHAUST_M3_H[VentilatedRoomKind.TOILET] == 30.0


def test_dry_rooms_use_air_change_rate_instead():
    assert VentilatedRoomKind.BEDROOM in AIR_CHANGES_PER_HOUR
    assert VentilatedRoomKind.BEDROOM not in MINIMUM_EXHAUST_M3_H


def test_standard_diameters_are_sorted_ascending():
    assert STANDARD_ROUND_DUCT_DIAMETERS_MM == sorted(STANDARD_ROUND_DUCT_DIAMETERS_MM)


def test_standard_fans_sorted_by_capability():
    flows = [f[0] for f in STANDARD_FANS]
    assert flows == sorted(flows)
