"""
Стіна як об'єм (модуль 10): дві бічні поверхні + товщина, шари
конструкції (модуль 8.4) як реальні шари в об'ємі, отвори (вікна/двері).

Товщина стіни модуля 1 ділиться порівну по обидва боки від осьової
лінії start-end — та сама умовність, що й у малюванні стіни в модулі 3
(`corners = start ± n·t/2, end ± n·t/2`). Тому дві бічні грані тут —
`side_faces()`, симетричні відносно центру; яка з них "внутрішня", а
яка "зовнішня" відносно кімнати, залежить від контексту (де центроїд
кімнати) — для цього є `inner_outer_faces(room_centroid)`.

Отвори НЕ вирізають літературну дірку в тривимірній сітці (це чисте
розрахункове ядро, а не CAD/BREP) — вони лише зменшують площу й об'єм
у розрахунках (`net_area_m2`, `material_volumes_m3`).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .geometry import Point
from .geometry3d import Face, Point3
from .insulation import WallLayer
from .opening import Opening
from .wall import Wall

_THICKNESS_TOLERANCE_MM = 1.0


@dataclass
class Wall3D:
    """Тривимірне представлення стіни модуля 1."""

    wall: Wall
    layers: list[WallLayer] = field(default_factory=list)
    openings: list[Opening] = field(default_factory=list)

    def __post_init__(self) -> None:
        for opening in self.openings:
            if opening.offset_mm + opening.width_mm > self.wall.length_mm + 1e-6:
                raise ValueError(f"Отвір «{opening.label()}» виходить за довжину стіни")
            if opening.sill_height_mm + opening.height_mm > self.wall.height + 1e-6:
                raise ValueError(f"Отвір «{opening.label()}» виходить за висоту стіни")
        if self.layers:
            total_layers_mm = sum(layer.thickness_m for layer in self.layers) * 1000.0
            if abs(total_layers_mm - self.wall.thickness_mm) > _THICKNESS_TOLERANCE_MM:
                raise ValueError(
                    f"Сума товщин шарів ({total_layers_mm:.1f} мм) не збігається "
                    f"з товщиною стіни ({self.wall.thickness_mm:.1f} мм)"
                )

    @property
    def openings_area_m2(self) -> float:
        return sum(opening.area_m2 for opening in self.openings)

    @property
    def gross_area_m2(self) -> float:
        """Площа стіни без урахування отворів (як у модулі 1)."""
        return self.wall.area_m2

    @property
    def net_area_m2(self) -> float:
        """Площа стіни за вирахуванням отворів — саме вона йде на плитку
        (модуль 2) чи в тепловтрати (модуль 8.3)."""
        return self.gross_area_m2 - self.openings_area_m2

    def _perpendicular(self) -> tuple[float, float]:
        start, end = self.wall.start, self.wall.end
        dx, dz = end.x - start.x, end.z - start.z
        length = (dx * dx + dz * dz) ** 0.5 or 1.0
        return -dz / length, dx / length

    def side_faces(self) -> tuple[Face, Face]:
        """Дві бічні вертикальні грані стіни (уздовж товщини), симетрично
        відносно осьової лінії start-end."""
        nx, nz = self._perpendicular()
        half = self.wall.thickness_mm / 2
        start, end = self.wall.start, self.wall.end

        side_a_start = Point(start.x + nx * half, start.z + nz * half)
        side_a_end = Point(end.x + nx * half, end.z + nz * half)
        side_b_start = Point(start.x - nx * half, start.z - nz * half)
        side_b_end = Point(end.x - nx * half, end.z - nz * half)

        face_a = Face(
            points=[
                Point3.from_plan(side_a_start, 0),
                Point3.from_plan(side_a_end, 0),
                Point3.from_plan(side_a_end, self.wall.height),
                Point3.from_plan(side_a_start, self.wall.height),
            ]
        )
        face_b = Face(
            points=[
                Point3.from_plan(side_b_start, 0),
                Point3.from_plan(side_b_end, 0),
                Point3.from_plan(side_b_end, self.wall.height),
                Point3.from_plan(side_b_start, self.wall.height),
            ]
        )
        return face_a, face_b

    def inner_outer_faces(self, room_centroid: Point) -> tuple[Face, Face]:
        """(внутрішня, зовнішня) грань відносно центроїда кімнати
        `room_centroid` — внутрішня та, чий центр ближчий до центроїда."""
        face_a, face_b = self.side_faces()

        def face_center(face: Face) -> Point:
            xs = [p.x for p in face.points]
            zs = [p.z for p in face.points]
            return Point(sum(xs) / len(xs), sum(zs) / len(zs))

        dist_a = face_center(face_a).distance_to(room_centroid)
        dist_b = face_center(face_b).distance_to(room_centroid)
        return (face_a, face_b) if dist_a <= dist_b else (face_b, face_a)

    def layer_volume_m3(self, layer: WallLayer) -> float:
        """Об'єм цього шару стіни (за вирахуванням отворів — вони йдуть
        наскрізь через усю товщину, тобто через кожен шар однаково)."""
        return self.net_area_m2 * layer.thickness_m

    def material_volumes_m3(self) -> dict[str, float]:
        """Об'єм кожного матеріалу шарів стіни, м³ (ключ — назва
        матеріалу з бази модуля 7)."""
        volumes: dict[str, float] = {}
        for layer in self.layers:
            volumes[layer.material.name] = volumes.get(layer.material.name, 0.0) + self.layer_volume_m3(layer)
        return volumes
