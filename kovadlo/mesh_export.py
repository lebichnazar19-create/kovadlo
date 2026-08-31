"""
Проста сітка (mesh) і експорт у формат Wavefront OBJ (модуль 10).

Знадобиться для рендеру пізніше — тут лише дані (вершини й трикутники)
і текстовий серіалізатор, без жодної графіки.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .geometry3d import Face, Point3
from .roof3d import Roof
from .slab3d import Slab
from .wall3d import Wall3D

MM_PER_M = 1000.0


@dataclass
class Mesh:
    """Проста сітка: список вершин + список трикутників (індекси вершин, з 0)."""

    vertices: list[Point3] = field(default_factory=list)
    triangles: list[tuple[int, int, int]] = field(default_factory=list)

    def add_face(self, face: Face) -> None:
        """Додає плоску грань як віяло трикутників (fan triangulation) —
        коректно для опуклих граней, якими є всі грані цього модуля
        (прямокутники стін/плит і схилів даху)."""
        start_index = len(self.vertices)
        self.vertices.extend(face.points)
        for i in range(1, len(face.points) - 1):
            self.triangles.append((start_index, start_index + i, start_index + i + 1))

    def add_faces(self, faces: list[Face]) -> None:
        for face in faces:
            self.add_face(face)

    @property
    def vertex_count(self) -> int:
        return len(self.vertices)

    @property
    def triangle_count(self) -> int:
        return len(self.triangles)

    def to_obj(self) -> str:
        """Текст у форматі Wavefront OBJ: вершини (`v`) переведені з мм
        у метри (звичний масштаб світу для 3D-інструментів), грані (`f`)
        як трикутники з 1-індексацією, якої вимагає формат OBJ."""
        lines = ["# Ковадло — модуль 10, експорт сітки (мм -> м)"]
        for vertex in self.vertices:
            lines.append(f"v {vertex.x / MM_PER_M:.6f} {vertex.y / MM_PER_M:.6f} {vertex.z / MM_PER_M:.6f}")
        for a, b, c in self.triangles:
            lines.append(f"f {a + 1} {b + 1} {c + 1}")
        return "\n".join(lines) + "\n"


def build_room_mesh(walls3d: list[Wall3D], slabs: list[Slab] | None = None, roof: Roof | None = None) -> Mesh:
    """Складає сітку кімнати з бічних граней стін, граней плит
    (перекриття/підлоги) і схилів даху — зручний "все разом" будівник
    поверх окремих сутностей модуля 10."""
    mesh = Mesh()
    for wall3d in walls3d:
        mesh.add_faces(list(wall3d.side_faces()))
    for slab in slabs or []:
        mesh.add_faces([slab.bottom_face(), slab.top_face()])
    if roof is not None:
        mesh.add_faces(roof.faces)
    return mesh
