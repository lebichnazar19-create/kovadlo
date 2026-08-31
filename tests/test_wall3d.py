import pytest

from kovadlo.geometry import Point
from kovadlo.insulation import WallLayer
from kovadlo.material_seed import build_default_database
from kovadlo.materials import Material
from kovadlo.opening import Opening, OpeningKind
from kovadlo.wall import Wall
from kovadlo.wall3d import Wall3D

DB = build_default_database()
CONCRETE = DB.find_by_name("Бетон C25/30")
WOOL = DB.find_by_name("Мінеральна вата (кам'яна)")


def _wall(thickness=380.0, length=4000.0, height=2700.0) -> Wall:
    return Wall.create(start=Point(0, 0), end=Point(length, 0), height=height, thickness=thickness, material=Material("стіна", 2000))


def test_gross_area_matches_module1():
    wall3d = Wall3D(wall=_wall())
    assert wall3d.gross_area_m2 == pytest.approx(4.0 * 2.7)
    assert wall3d.openings_area_m2 == 0.0
    assert wall3d.net_area_m2 == wall3d.gross_area_m2


def test_wall_area_with_window_hand_verified():
    """Контрольний сценарій із завдання: площа стіни з вікном.

    Стіна 4×2.7 м (gross = 10.8 м²), вікно 1.2×1.4 м (= 1.68 м²).
    Чиста площа = 10.8 - 1.68 = 9.12 м².
    """
    window = Opening(OpeningKind.WINDOW, offset_mm=1500, sill_height_mm=900, width_mm=1200, height_mm=1400)
    wall3d = Wall3D(wall=_wall(), openings=[window])
    assert wall3d.gross_area_m2 == pytest.approx(10.8)
    assert wall3d.openings_area_m2 == pytest.approx(1.68)
    assert wall3d.net_area_m2 == pytest.approx(9.12)


def test_multiple_openings_subtract_cumulatively():
    window = Opening(OpeningKind.WINDOW, offset_mm=500, sill_height_mm=900, width_mm=1000, height_mm=1200)
    door = Opening(OpeningKind.DOOR, offset_mm=2000, sill_height_mm=0, width_mm=900, height_mm=2000)
    wall3d = Wall3D(wall=_wall(), openings=[window, door])
    expected_net = 10.8 - (1.0 * 1.2) - (0.9 * 2.0)
    assert wall3d.net_area_m2 == pytest.approx(expected_net)


def test_opening_beyond_wall_length_rejected():
    bad = Opening(OpeningKind.DOOR, offset_mm=3500, sill_height_mm=0, width_mm=900, height_mm=2000)
    with pytest.raises(ValueError):
        Wall3D(wall=_wall(), openings=[bad])


def test_opening_beyond_wall_height_rejected():
    bad = Opening(OpeningKind.WINDOW, offset_mm=0, sill_height_mm=2000, width_mm=900, height_mm=1000)
    with pytest.raises(ValueError):
        Wall3D(wall=_wall(), openings=[bad])


def test_layers_must_sum_to_wall_thickness():
    with pytest.raises(ValueError):
        Wall3D(wall=_wall(thickness=380.0), layers=[WallLayer(CONCRETE, 0.1)])  # 100мм != 380мм


def test_layers_matching_thickness_accepted():
    wall3d = Wall3D(wall=_wall(thickness=380.0), layers=[WallLayer(CONCRETE, 0.2), WallLayer(WOOL, 0.18)])
    assert len(wall3d.layers) == 2


def test_material_volumes_hand_verified():
    """Стіна 4×2.7 м, товщина 380мм = бетон 200мм + вата 180мм, без отворів.
    Об'єм бетону = 10.8 м² × 0.2 м = 2.16 м³; вати = 10.8 × 0.18 = 1.944 м³.
    """
    wall3d = Wall3D(wall=_wall(thickness=380.0), layers=[WallLayer(CONCRETE, 0.2), WallLayer(WOOL, 0.18)])
    volumes = wall3d.material_volumes_m3()
    assert volumes["Бетон C25/30"] == pytest.approx(2.16)
    assert volumes["Мінеральна вата (кам'яна)"] == pytest.approx(1.944)


def test_material_volumes_reduced_by_openings():
    """Той самий шаровий пиріг, але з вікном 1.2×1.4 м: чиста площа
    9.12 м² -> об'єм бетону = 9.12×0.2 = 1.824 м³ (отвір наскрізний,
    зменшує об'єм КОЖНОГО шару)."""
    window = Opening(OpeningKind.WINDOW, offset_mm=1500, sill_height_mm=900, width_mm=1200, height_mm=1400)
    wall3d = Wall3D(wall=_wall(thickness=380.0), layers=[WallLayer(CONCRETE, 0.2), WallLayer(WOOL, 0.18)], openings=[window])
    volumes = wall3d.material_volumes_m3()
    assert volumes["Бетон C25/30"] == pytest.approx(9.12 * 0.2)
    assert volumes["Мінеральна вата (кам'яна)"] == pytest.approx(9.12 * 0.18)


def test_side_faces_are_symmetric_around_centerline():
    wall3d = Wall3D(wall=_wall(thickness=380.0))
    face_a, face_b = wall3d.side_faces()
    # обидві грані мають ту саму (валову) площу, що й сама стіна
    assert face_a.area_m2 == pytest.approx(wall3d.gross_area_m2)
    assert face_b.area_m2 == pytest.approx(wall3d.gross_area_m2)
    # зсунуті симетрично: сума z-координат = 0 (стіна вздовж осі x, z=0)
    assert face_a.points[0].z == pytest.approx(-face_b.points[0].z)


def test_inner_outer_faces_pick_side_closer_to_centroid():
    wall3d = Wall3D(wall=_wall(thickness=380.0))  # стіна вздовж (0,0)-(4000,0)
    centroid_inside_room = Point(2000, 1500)  # кімната "вище" стіни (z>0)
    inner, outer = wall3d.inner_outer_faces(centroid_inside_room)
    assert inner.points[0].z > 0
    assert outer.points[0].z < 0
