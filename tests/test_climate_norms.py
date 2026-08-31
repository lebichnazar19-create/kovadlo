from kovadlo.climate_norms import (
    DESIGN_OUTDOOR_TEMP_C,
    STANDARD_AC_POWERS_KW,
    STANDARD_RADIATOR_POWERS_W,
    ClimateZone,
)


def test_every_climate_zone_has_a_design_temperature():
    for zone in ClimateZone:
        assert zone in DESIGN_OUTDOOR_TEMP_C


def test_colder_zones_have_lower_design_temperature():
    temps = [DESIGN_OUTDOOR_TEMP_C[zone] for zone in ClimateZone]
    assert temps == sorted(temps, reverse=True)  # I (найтепліша) -> V (найхолодніша), спадно


def test_standard_power_series_are_sorted():
    assert STANDARD_RADIATOR_POWERS_W == sorted(STANDARD_RADIATOR_POWERS_W)
    assert STANDARD_AC_POWERS_KW == sorted(STANDARD_AC_POWERS_KW)
