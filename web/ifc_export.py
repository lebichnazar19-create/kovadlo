"""Експорт кімнати(-т) у IFC4 через IfcOpenShell.

IfcOpenShell — LGPL-бібліотека; підключена лише тут, звичайним `import`
(`pip install ifcopenshell`, окремий venv/extra — НЕ в `kovadlo/`, щоб
ядро лишалось stdlib-only, див. головне правило в CLAUDE.md). Жодного її
коду сюди не скопійовано й не залінковано статично — LGPL це дозволяє
без зміни ліцензії самого Ковадла.

Одиниці: kovadlo — мм, IFC — м; конвертація ×0.001 (MM_TO_M) в одному
місці, як і для three.js (web/static/index.html).

Осі: kovadlo/three.js — X/Z горизонтальна площина, Y — висота (вгору).
IFC — X/Y горизонтальна площина, Z — висота (вгору). Тому geometry
"перекладає" координати (x, y_висота, z) -> IFC (x, z, y_висота) —
свідомий переклад конвенції, а не помилка дзеркалення (див. CLAUDE.md,
пастка №1 — там про ІНШУ річ, плутати не варто).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

import ifcopenshell
import ifcopenshell.api.aggregate
import ifcopenshell.api.context
import ifcopenshell.api.feature
import ifcopenshell.api.geometry
import ifcopenshell.api.material
import ifcopenshell.api.root
import ifcopenshell.api.spatial
import ifcopenshell.api.unit

from kovadlo.geometry3d import Face
from kovadlo.opening import Opening
from kovadlo.room import Room

MM_TO_M = 0.001

# Проріз/wall-representation дублює тонкий "нахлест" — щоб булева
# операція IfcOpeningElement↔IfcWallStandardCase не спотикалась на
# точній дотичності граней (той самий прийом, що в офіційному прикладі
# ifcopenshell.api.feature.add_feature).
_OPENING_MARGIN_M = 0.02

# Назва матеріалу кімнати (kovadlo Material.name, довільний текст
# українською) -> назва IfcMaterial. Матеріалів поза мапою експортуємо
# з тією самою назвою, що є, — мапа лише для типових/очікуваних термінів.
MATERIAL_NAME_MAP: dict[str, str] = {
    "цегла": "Brick",
    "бетон": "Concrete",
    "залізобетон": "Reinforced Concrete",
    "дерево": "Wood",
    "газобетон": "Aerated Concrete",
    "гіпсокартон": "Gypsum Board",
}


@dataclass
class RoomExport:
    """Одна кімната для експорту — той самий `Room` (контур + стіни з
    товщиною/висотою/матеріалом), яким уже користується геометрія
    (web/scene3d.py), плюс те, що в kovadlo зберігається ОКРЕМО від
    `Room` (прив'язка отворів до стіни — за індексом, як і в AppState;
    дах — опційно, з kovadlo/roof3d.py)."""

    room: Room
    floor_thickness_mm: float
    openings_by_wall: dict[int, list[Opening]] = field(default_factory=dict)
    roof_faces: list[Face] | None = None
    name: str = ""


def _xz_to_ifc_xy(x_mm: float, z_mm: float) -> tuple[float, float]:
    return (x_mm * MM_TO_M, z_mm * MM_TO_M)


def _place_along(
    file: ifcopenshell.file,
    element: ifcopenshell.entity_instance,
    p1: tuple[float, float],
    p2: tuple[float, float],
    elevation: float,
) -> None:
    """Позиціонує елемент так, щоб його локальна вісь X дивилась від p1
    до p2 (площина IFC XY, метри), а локальний Z-початок був на
    `elevation`. Той самий розрахунок матриці, що
    `ifcopenshell.api.geometry.create_2pt_wall` робить всередині себе —
    тут явно, бо потрібен і для стіни (create_2pt_wall), і для отвору
    в ній (де такого готового хелпера немає)."""
    p1_ = np.array(p1, dtype=float)
    p2_ = np.array(p2, dtype=float)
    v = p2_ - p1_
    v /= np.linalg.norm(v)
    matrix = np.array(
        [
            [v[0], -v[1], 0.0, p1_[0]],
            [v[1], v[0], 0.0, p1_[1]],
            [0.0, 0.0, 1.0, elevation],
            [0.0, 0.0, 0.0, 1.0],
        ]
    )
    ifcopenshell.api.geometry.edit_object_placement(file, product=element, matrix=matrix)


def _faceted_roof_representation(
    file: ifcopenshell.file, context: ifcopenshell.entity_instance, faces: list[Face]
) -> ifcopenshell.entity_instance:
    """`IfcShellBasedSurfaceModel` з відкритою оболонкою (`IfcOpenShell`,
    сутність IFC-схеми — не плутати з бібліотекою) — дах не замкнений
    об'єм (немає низу/боків), тому НЕ `IfcFacetedBrep`/`IfcClosedShell`,
    які вимагають цілісного тіла."""
    ifc_faces = []
    for face in faces:
        points = [
            file.createIfcCartesianPoint((p.x * MM_TO_M, p.z * MM_TO_M, p.y * MM_TO_M)) for p in face.points
        ]
        loop = file.createIfcPolyLoop(points)
        bound = file.createIfcFaceOuterBound(loop, True)
        ifc_faces.append(file.createIfcFace([bound]))
    shell = file.createIfcOpenShell(ifc_faces)
    surface_model = file.createIfcShellBasedSurfaceModel([shell])
    return file.createIfcShapeRepresentation(context, context.ContextIdentifier, "SurfaceModel", [surface_model])


def export_project(rooms: list[RoomExport], out_path: str, project_name: str) -> None:
    """Експортує кімнати в один .ifc-файл (IFC4):
    IfcProject → IfcSite → IfcBuilding → IfcBuildingStorey, і в поверх —
    стіни (IfcWallStandardCase + IfcMaterial), підлоги (IfcSlab,
    PredefinedType=FLOOR), прорізи (IfcOpeningElement + IfcRelVoidsElement
    на відповідній стіні) і дах (IfcRoof), якщо переданий.
    """
    file = ifcopenshell.file(schema="IFC4")

    project = ifcopenshell.api.root.create_entity(file, ifc_class="IfcProject", name=project_name)
    ifcopenshell.api.unit.assign_unit(file)  # за замовчуванням — SI (метри, кв. метри, м³)

    model_context = ifcopenshell.api.context.add_context(file, context_type="Model")
    body_context = ifcopenshell.api.context.add_context(
        file, context_type="Model", context_identifier="Body", target_view="MODEL_VIEW", parent=model_context
    )

    site = ifcopenshell.api.root.create_entity(file, ifc_class="IfcSite", name="Ділянка")
    building = ifcopenshell.api.root.create_entity(file, ifc_class="IfcBuilding", name="Будівля")
    storey = ifcopenshell.api.root.create_entity(file, ifc_class="IfcBuildingStorey", name="Поверх 1")
    ifcopenshell.api.aggregate.assign_object(file, products=[site], relating_object=project)
    ifcopenshell.api.aggregate.assign_object(file, products=[building], relating_object=site)
    ifcopenshell.api.aggregate.assign_object(file, products=[storey], relating_object=building)

    materials: dict[str, ifcopenshell.entity_instance] = {}

    def material_entity(name: str) -> ifcopenshell.entity_instance:
        ifc_name = MATERIAL_NAME_MAP.get(name, name or "Матеріал не вказано")
        if ifc_name not in materials:
            materials[ifc_name] = ifcopenshell.api.material.add_material(file, name=ifc_name)
        return materials[ifc_name]

    elements_for_storey: list[ifcopenshell.entity_instance] = []

    for room_export in rooms:
        room = room_export.room

        # --- підлога ---
        slab = ifcopenshell.api.root.create_entity(
            file, ifc_class="IfcSlab", predefined_type="FLOOR", name=room_export.name or "Підлога"
        )
        polyline = [_xz_to_ifc_xy(p.x, p.z) for p in room.contour]
        slab_representation = ifcopenshell.api.geometry.add_slab_representation(
            file,
            context=body_context,
            depth=room_export.floor_thickness_mm * MM_TO_M,
            direction_sense="NEGATIVE",  # вниз від Z=0, як і "верх плити на y=0" у room.js::extrudeFloor
            polyline=polyline,
        )
        ifcopenshell.api.geometry.assign_representation(file, product=slab, representation=slab_representation)
        ifcopenshell.api.geometry.edit_object_placement(file, product=slab)
        elements_for_storey.append(slab)

        # --- стіни (+ матеріал, + прорізи) ---
        for wall_index, wall in enumerate(room.walls):
            wall_entity = ifcopenshell.api.root.create_entity(
                file, ifc_class="IfcWallStandardCase", name=f"Стіна {wall_index + 1}"
            )
            p1 = _xz_to_ifc_xy(wall.start.x, wall.start.z)
            p2 = _xz_to_ifc_xy(wall.end.x, wall.end.z)
            thickness_m = wall.thickness_mm * MM_TO_M
            wall_representation = ifcopenshell.api.geometry.add_wall_representation(
                file,
                context=body_context,
                length=wall.length_mm * MM_TO_M,
                height=wall.height * MM_TO_M,
                thickness=thickness_m,
                # Центровано на осьовій лінії start->end (±thickness/2) —
                # та сама умовність, що й kovadlo/wall3d.py й
                # web/static/js/geometry/room.js::extrudeWall; без offset
                # add_wall_representation кладе всю товщину В ОДИН БІК.
                offset=-thickness_m / 2,
            )
            ifcopenshell.api.geometry.assign_representation(file, product=wall_entity, representation=wall_representation)
            _place_along(file, wall_entity, p1, p2, elevation=0.0)
            ifcopenshell.api.material.assign_material(file, products=[wall_entity], material=material_entity(wall.material.name))
            elements_for_storey.append(wall_entity)

            direction = (np.array(p2) - np.array(p1))
            direction = direction / np.linalg.norm(direction)

            for opening in room_export.openings_by_wall.get(wall_index, []):
                opening_entity = ifcopenshell.api.root.create_entity(
                    file, ifc_class="IfcOpeningElement", name=opening.label()
                )
                opening_thickness_m = thickness_m + _OPENING_MARGIN_M
                opening_representation = ifcopenshell.api.geometry.add_wall_representation(
                    file,
                    context=body_context,
                    length=opening.width_mm * MM_TO_M,
                    height=opening.height_mm * MM_TO_M,
                    thickness=opening_thickness_m,
                    offset=-opening_thickness_m / 2,
                )
                ifcopenshell.api.geometry.assign_representation(
                    file, product=opening_entity, representation=opening_representation
                )
                origin = np.array(p1) + direction * (opening.offset_mm * MM_TO_M)
                _place_along(
                    file,
                    opening_entity,
                    tuple(origin),
                    tuple(origin + direction),
                    elevation=opening.sill_height_mm * MM_TO_M,
                )
                ifcopenshell.api.feature.add_feature(file, feature=opening_entity, element=wall_entity)

        # --- дах (опційно) ---
        if room_export.roof_faces:
            roof_entity = ifcopenshell.api.root.create_entity(file, ifc_class="IfcRoof", name="Дах")
            roof_representation = _faceted_roof_representation(file, body_context, room_export.roof_faces)
            ifcopenshell.api.geometry.assign_representation(file, product=roof_entity, representation=roof_representation)
            ifcopenshell.api.geometry.edit_object_placement(file, product=roof_entity)
            elements_for_storey.append(roof_entity)

    ifcopenshell.api.spatial.assign_container(file, products=elements_for_storey, relating_structure=storey)

    file.write(out_path)
