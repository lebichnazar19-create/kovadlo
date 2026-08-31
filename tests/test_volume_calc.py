import pytest

from kovadlo.geometry import Point
from kovadlo.insulation import WallLayer
from kovadlo.material_seed import build_default_database
from kovadlo.materials import Material
from kovadlo.opening import Opening, OpeningKind
from kovadlo.room import Room
from kovadlo.volume_calc import (
    exterior_envelope_area_m2,
    room_volume_m3,
    wall_material_costs_pln,
    wall_material_volumes_m3,
)
from kovadlo.wall3d import Wall3D

DB = build_default_database()
CONCRETE = DB.find_by_name("Бетон C25/30")
WOOL = DB.find_by_name("Мінеральна вата (кам'яна)")


def _room(thickness: float = 380.0) -> Room:
    return Room.from_contour(
        [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)],
        height=2700,
        thickness=thickness,
        material=Material("стіна", 2000),
        name="Кухня",
    )


# ---------------------------------------------------------------------------
# Об'єм кімнати (контрольний сценарій із завдання)
# ---------------------------------------------------------------------------


def test_room_volume_hand_verified():
    """4×3 м, висота 2.7 м -> об'єм = 12 × 2.7 = 32.4 м³."""
    room = _room()
    assert room_volume_m3(room) == pytest.approx(32.4)


def test_room_volume_requires_walls():
    room = _room()
    room.walls = []
    with pytest.raises(ValueError):
        room_volume_m3(room)


# ---------------------------------------------------------------------------
# Площа зовнішніх огороджень з вікнами
# ---------------------------------------------------------------------------


def test_envelope_area_subtracts_window_hand_verified():
    """Одна стіна з вікном 1.2×1.4 м, решта без отворів: різниця між
    валовою сумою (37.8 м²) і чистою (envelope) має дорівнювати площі вікна."""
    room = _room()
    window = Opening(OpeningKind.WINDOW, offset_mm=1500, sill_height_mm=900, width_mm=1200, height_mm=1400)
    walls3d = [Wall3D(wall=w, openings=[window] if i == 0 else []) for i, w in enumerate(room.walls)]

    gross_total = sum(w.area_m2 for w in room.walls)
    envelope = exterior_envelope_area_m2(walls3d)
    assert gross_total - envelope == pytest.approx(window.area_m2)
    assert envelope == pytest.approx(gross_total - 1.68)


def test_envelope_area_with_no_openings_equals_gross():
    room = _room()
    walls3d = [Wall3D(wall=w) for w in room.walls]
    gross_total = sum(w.area_m2 for w in room.walls)
    assert exterior_envelope_area_m2(walls3d) == pytest.approx(gross_total)


# ---------------------------------------------------------------------------
# Об'єм і вартість матеріалів (контрольний сценарій: скільки бетону в стінах)
# ---------------------------------------------------------------------------


def test_wall_material_volumes_hand_verified():
    """Кімната 4×3м, товщина стін 380мм = бетон 200мм + вата 180мм.
    Периметр = 2*(4+3) = 14 м, висота 2.7 м -> валова площа стін = 37.8 м².
    Об'єм бетону = 37.8 × 0.2 = 7.56 м³; вати = 37.8 × 0.18 = 6.804 м³.
    """
    room = _room(thickness=380.0)
    walls3d = [Wall3D(wall=w, layers=[WallLayer(CONCRETE, 0.2), WallLayer(WOOL, 0.18)]) for w in room.walls]

    volumes = wall_material_volumes_m3(walls3d)
    assert volumes["Бетон C25/30"] == pytest.approx(37.8 * 0.2)
    assert volumes["Мінеральна вата (кам'яна)"] == pytest.approx(37.8 * 0.18)


def test_wall_material_costs_concrete_hand_verified():
    """Бетон C25/30 у базі модуля 7 коштує 460 зл/м³ (орієнтовно).
    Об'єм бетону в стінах = 7.56 м³ -> вартість = 7.56 × 460 = 3477.6 зл.
    """
    room = _room(thickness=380.0)
    walls3d = [Wall3D(wall=w, layers=[WallLayer(CONCRETE, 0.2), WallLayer(WOOL, 0.18)]) for w in room.walls]

    costs = wall_material_costs_pln(walls3d)
    price_per_m3 = CONCRETE.price_per("м3").price_pln
    assert price_per_m3 == pytest.approx(460.0)
    expected_cost = 37.8 * 0.2 * price_per_m3
    assert costs["Бетон C25/30"] == pytest.approx(expected_cost)


def test_wall_material_volumes_and_costs_reduced_by_openings():
    room = _room(thickness=380.0)
    window = Opening(OpeningKind.WINDOW, offset_mm=1500, sill_height_mm=900, width_mm=1200, height_mm=1400)
    walls3d = [
        Wall3D(wall=w, layers=[WallLayer(CONCRETE, 0.2), WallLayer(WOOL, 0.18)], openings=[window] if i == 0 else [])
        for i, w in enumerate(room.walls)
    ]
    no_window_walls3d = [Wall3D(wall=w, layers=[WallLayer(CONCRETE, 0.2), WallLayer(WOOL, 0.18)]) for w in room.walls]

    volumes_with_window = wall_material_volumes_m3(walls3d)
    volumes_without = wall_material_volumes_m3(no_window_walls3d)
    assert volumes_with_window["Бетон C25/30"] < volumes_without["Бетон C25/30"]
    assert volumes_without["Бетон C25/30"] - volumes_with_window["Бетон C25/30"] == pytest.approx(0.2 * 1.68)

    costs_with_window = wall_material_costs_pln(walls3d)
    costs_without = wall_material_costs_pln(no_window_walls3d)
    assert costs_with_window["Бетон C25/30"] < costs_without["Бетон C25/30"]
