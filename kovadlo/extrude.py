"""Витягування (extrude) контуру кімнати у вертикальні тривимірні грані."""

from __future__ import annotations

from .geometry import Point
from .geometry3d import Face, Point3


def extrude_contour_walls(contour: list[Point], height: float, base_height: float = 0.0) -> list[Face]:
    """Витягує контур кімнати (модуль 1) вертикально на `height`
    (від `base_height`), повертає по одній вертикальній грані на кожне
    ребро контуру — проста "коробка" стін без товщини (для товщини
    див. `wall3d.py`)."""
    if len(contour) < 3:
        raise ValueError("Контур має містити щонайменше 3 точки")
    if height <= 0:
        raise ValueError("Висота витягування має бути додатною")

    n = len(contour)
    faces = []
    for i in range(n):
        a, b = contour[i], contour[(i + 1) % n]
        faces.append(
            Face(
                points=[
                    Point3.from_plan(a, base_height),
                    Point3.from_plan(b, base_height),
                    Point3.from_plan(b, base_height + height),
                    Point3.from_plan(a, base_height + height),
                ]
            )
        )
    return faces


def extrude_flat_faces(contour: list[Point], height: float) -> tuple[Face, Face]:
    """Верхня й нижня горизонтальні грані того самого контуру, на
    висотах 0 і `height` — "дно" і "стеля" витягнутого об'єму."""
    bottom = Face(points=[Point3.from_plan(p, 0) for p in contour])
    top = Face(points=[Point3.from_plan(p, height) for p in contour])
    return bottom, top
