from kovadlo.fire_safety_norms import COVERAGE_AREA_M2, MAX_SPACING_M, WALL_CLEARANCE_M, DetectorKind


def test_every_detector_kind_has_full_norm_set():
    for kind in DetectorKind:
        assert kind in COVERAGE_AREA_M2
        assert kind in MAX_SPACING_M
        assert kind in WALL_CLEARANCE_M


def test_heat_detector_has_shorter_max_spacing_than_smoke():
    # теплові датчики зазвичай реагують повільніше -> ставлять густіше
    assert MAX_SPACING_M[DetectorKind.HEAT] < MAX_SPACING_M[DetectorKind.SMOKE]
