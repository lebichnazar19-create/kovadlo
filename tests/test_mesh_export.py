import pytest

from kovadlo.geometry import Point
from kovadlo.geometry3d import Face, Point3
from kovadlo.materials import Material
from kovadlo.mesh_export import Mesh, build_room_mesh
from kovadlo.roof3d import build_gable_roof
from kovadlo.room import Room
from kovadlo.slab3d import Slab
from kovadlo.wall3d import Wall3D


def test_add_face_triangulates_quad_as_fan():
    mesh = Mesh()
    face = Face(points=[Point3(0, 0, 0), Point3(1, 0, 0), Point3(1, 1, 0), Point3(0, 1, 0)])
    mesh.add_face(face)
    assert mesh.vertex_count == 4
    assert mesh.triangle_count == 2
    assert mesh.triangles == [(0, 1, 2), (0, 2, 3)]


def test_add_faces_accumulates_indices_correctly():
    mesh = Mesh()
    face1 = Face(points=[Point3(0, 0, 0), Point3(1, 0, 0), Point3(1, 1, 0), Point3(0, 1, 0)])
    face2 = Face(points=[Point3(0, 0, 1), Point3(1, 0, 1), Point3(1, 1, 1), Point3(0, 1, 1)])
    mesh.add_faces([face1, face2])
    assert mesh.vertex_count == 8
    assert mesh.triangle_count == 4
    # друга грань має індекси, зсунуті на 4 (кількість вершин першої)
    assert mesh.triangles[2] == (4, 5, 6)
    assert mesh.triangles[3] == (4, 6, 7)


def test_to_obj_converts_mm_to_meters_and_uses_1_indexed_faces():
    mesh = Mesh()
    mesh.add_face(Face(points=[Point3(0, 0, 0), Point3(1000, 0, 0), Point3(1000, 1000, 0), Point3(0, 1000, 0)]))
    text = mesh.to_obj()
    lines = text.splitlines()
    assert lines[0].startswith("#")
    v_lines = [l for l in lines if l.startswith("v ")]
    f_lines = [l for l in lines if l.startswith("f ")]
    assert len(v_lines) == 4
    assert len(f_lines) == 2
    assert v_lines[1] == "v 1.000000 0.000000 0.000000"  # 1000 мм -> 1.0 м
    assert f_lines[0] == "f 1 2 3"  # 1-індексація OBJ


def test_build_room_mesh_vertex_and_triangle_counts_hand_verified():
    """Прямокутна кімната (4 стіни), підлога, двосхилий дах:
    вершини = 4 стіни × 2 бічні грані × 4 точки = 32
            + підлога (низ+верх) × 4 точки = 8
            + дах: 2 схили × 4 точки = 8
            = 48 вершин; трикутників = (4*2 + 1*2 + 2) граней × 2 = 24."""
    room = Room.from_contour(
        [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)],
        height=2700,
        thickness=200,
        material=Material("стіна", 2000),
    )
    walls3d = [Wall3D(wall=w) for w in room.walls]
    floor = Slab(contour=room.contour, base_height_mm=0, thickness_mm=200)
    roof = build_gable_roof(room.contour, base_height_mm=2700, slope_deg=30)

    mesh = build_room_mesh(walls3d, slabs=[floor], roof=roof)
    assert mesh.vertex_count == 48
    assert mesh.triangle_count == 24


def test_build_room_mesh_without_slabs_or_roof():
    room = Room.from_contour(
        [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)],
        height=2700,
        thickness=200,
        material=Material("стіна", 2000),
    )
    walls3d = [Wall3D(wall=w) for w in room.walls]
    mesh = build_room_mesh(walls3d)
    assert mesh.vertex_count == 4 * 2 * 4  # 4 стіни × 2 грані × 4 точки
    assert mesh.triangle_count == 16
