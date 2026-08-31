"""
Розрахунки на основі 3D-геометрії (модуль 10): об'єм приміщення, площа
зовнішніх огороджень з вікнами, об'єм і орієнтовна вартість матеріалів.
"""

from __future__ import annotations

from .insulation import insulation_cost_per_m2
from .room import Room
from .wall3d import Wall3D


def room_volume_m3(room: Room) -> float:
    """Об'єм приміщення (для розрахунку повітрообміну, модуль 8.2):
    площа підлоги × висота стін. Висота береться з першої стіни —
    `Room.from_contour` будує всі стіни кімнати з однаковою висотою."""
    if not room.walls:
        raise ValueError("Кімната без стін — немає висоти для розрахунку об'єму")
    height_m = room.walls[0].height / 1000.0
    return room.floor_area_m2 * height_m


def exterior_envelope_area_m2(walls3d: list[Wall3D]) -> float:
    """Сумарна площа зовнішніх огороджень за вирахуванням вікон/дверей
    (для тепловтрат, модуль 8.3) — сума `net_area_m2` переданих стін."""
    return sum(wall3d.net_area_m2 for wall3d in walls3d)


def wall_material_volumes_m3(walls3d: list[Wall3D]) -> dict[str, float]:
    """Сумарний об'єм кожного матеріалу по всіх переданих стінах, м³
    (напр., скільки бетону чи утеплювача на всі стіни разом), за
    вирахуванням отворів (наскрізних через усі шари)."""
    totals: dict[str, float] = {}
    for wall3d in walls3d:
        for material_name, volume in wall3d.material_volumes_m3().items():
            totals[material_name] = totals.get(material_name, 0.0) + volume
    return totals


def wall_material_costs_pln(walls3d: list[Wall3D]) -> dict[str, float]:
    """Орієнтовна вартість кожного матеріалу по всіх переданих стінах,
    злотих — з цін бази модуля 7 (`insulation_cost_per_m2`, яка сама
    бере ціну за м³/кг/м² з `MaterialSpec.prices`).

    Рахується як (ціна за м² шару цієї товщини) × (чиста площа стіни) —
    товщина в усіх стінах для одного матеріалу може відрізнятися, тому
    підсумовуємо по кожному шару окремо, а не за середньою товщиною.
    """
    totals: dict[str, float] = {}
    for wall3d in walls3d:
        for layer in wall3d.layers:
            cost_per_m2 = insulation_cost_per_m2(layer.material, layer.thickness_m)
            if cost_per_m2 is None:
                continue
            cost = cost_per_m2 * wall3d.net_area_m2
            totals[layer.material.name] = totals.get(layer.material.name, 0.0) + cost
    return totals
