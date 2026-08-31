import pytest

from kovadlo.opening import Opening, OpeningKind


def test_window_area_hand_calculation():
    window = Opening(OpeningKind.WINDOW, offset_mm=500, sill_height_mm=900, width_mm=1200, height_mm=1400, name="Вікно 1")
    assert window.area_mm2 == pytest.approx(1200 * 1400)
    assert window.area_m2 == pytest.approx(1.68)
    assert window.label() == "Вікно 1"


def test_door_default_label_uses_kind():
    door = Opening(OpeningKind.DOOR, offset_mm=0, sill_height_mm=0, width_mm=900, height_mm=2000)
    assert door.area_m2 == pytest.approx(1.8)
    assert door.label() == "двері"


def test_opening_rejects_non_positive_size():
    with pytest.raises(ValueError):
        Opening(OpeningKind.WINDOW, offset_mm=0, sill_height_mm=0, width_mm=0, height_mm=1000)
    with pytest.raises(ValueError):
        Opening(OpeningKind.WINDOW, offset_mm=0, sill_height_mm=0, width_mm=1000, height_mm=0)


def test_opening_rejects_negative_offset_or_sill():
    with pytest.raises(ValueError):
        Opening(OpeningKind.WINDOW, offset_mm=-1, sill_height_mm=0, width_mm=1000, height_mm=1000)
    with pytest.raises(ValueError):
        Opening(OpeningKind.WINDOW, offset_mm=0, sill_height_mm=-1, width_mm=1000, height_mm=1000)
