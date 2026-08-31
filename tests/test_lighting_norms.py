from kovadlo.lighting_norms import DEFAULT_MAINTENANCE_FACTOR, DEFAULT_UTILIZATION_FACTOR, RECOMMENDED_LUX, RoomPurpose


def test_every_room_purpose_has_recommended_lux():
    for purpose in RoomPurpose:
        assert purpose in RECOMMENDED_LUX
        assert RECOMMENDED_LUX[purpose] > 0


def test_office_recommended_level_matches_well_known_en12464_reference():
    # 500 лк для офісної роботи — найпоширеніше цитоване значення EN 12464-1
    assert RECOMMENDED_LUX[RoomPurpose.OFFICE] == 500.0


def test_default_factors_are_valid_fractions():
    assert 0 < DEFAULT_UTILIZATION_FACTOR <= 1
    assert 0 < DEFAULT_MAINTENANCE_FACTOR <= 1
