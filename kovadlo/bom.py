"""
Специфікація деталей (BOM) для конструкції з балок (модуль 12): бере
набір `Beam` і повертає перелік УНІКАЛЬНИХ деталей із кількістю.

Дві деталі — одна позиція специфікації, якщо в них однаковий профіль
(тип і всі розміри перерізу), матеріал і довжина (з допуском на
округлення — реальний вимір/розкрій ніколи не дає ідеальний збіг до
мікрона). `Beam.angle` (поворот профілю навколо власної осі) у
групуванні НЕ бере участі: та сама труба чи кутник, повернуті на
довільний кут, ріжуться однаково й лежать на складі в одній купі — це
не окрема деталь.

Справжня дзеркальність (ліва/права деталь з отворами по різних боках)
— це властивість САМОЇ деталі (наприклад, окремого поля в `Beam` чи
профілі), а не її орієнтації в збірці. У ядрі зараз такої ознаки нема
— цей модуль її не вигадує й не намагається вивести з `angle`.
"""

from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Any, Iterable

from .beam import Beam
from .profile import Profile

# Людські назви профілів модуля 12 (steel_profiles.py) за іменем класу.
# Профіль невідомого (майбутнього) типу не ламає групування — просто
# дістає менш гарну назву (з `profile.name`), а не падає з помилкою.
_PROFILE_LABELS: dict[str, str] = {
    "AngleProfile": "Кутник",
    "ChannelProfile": "Швелер",
    "IBeamProfile": "Двотавр",
    "RoundTubeProfile": "Труба кругла",
    "RectTubeProfile": "Труба прямокутна",
    "FlatBarProfile": "Смуга",
    "RoundBarProfile": "Пруток",
}


@dataclass(frozen=True)
class BomLine:
    """Одна позиція специфікації: номер, назва (тип профілю), розмір,
    матеріал окремим полем, кількість однакових деталей."""

    position: int
    name: str
    size: str
    material_name: str
    count: int


def _profile_label(profile: Profile) -> str:
    """Людська назва типу профілю — за іменем класу, з fallback на `profile.name`."""
    return _PROFILE_LABELS.get(type(profile).__name__, profile.name.replace("_", " ").capitalize())


def _profile_dimensions_str(profile: Profile) -> str:
    """Розміри перерізу через "×" — усі числові поля профілю, крім `name`.

    Через `dataclasses.fields`, а не хардкод-список типів: новий тип
    перерізу підхоплюється автоматично, без правок цього модуля (той
    самий принцип розширюваності, що й у решті ядра).
    """
    dims = [
        getattr(profile, f.name)
        for f in dataclasses.fields(profile)
        if f.name != "name" and isinstance(getattr(profile, f.name), (int, float))
    ]
    return "×".join(f"{v:.0f}" for v in dims)


def _group_key(beam: Beam, length_tolerance_mm: float) -> tuple[Any, ...]:
    """Ключ групування: тип+розміри профілю, матеріал, довжина з допуском."""
    return (
        type(beam.profile).__name__,
        dataclasses.astuple(beam.profile),
        beam.material,
        round(beam.length_mm / length_tolerance_mm),
    )


def build_bill_of_materials(elements: Iterable[Beam], *, length_tolerance_mm: float = 1.0) -> list[BomLine]:
    """Специфікація унікальних деталей конструкції з кількістю (BOM).

    Позиції нумеруються в порядку ПЕРШОЇ появи унікальної групи у
    вхідній послідовності — стабільно: той самий список `elements` (у
    тому самому порядку) завжди дає той самий перелік і ту саму
    нумерацію, бо накопичення йде через звичайний `dict` (зберігає
    порядок вставки), без множин чи хешованого перебору.
    """
    if length_tolerance_mm <= 0:
        raise ValueError("length_tolerance_mm має бути додатним")

    groups: dict[tuple[Any, ...], list[Beam]] = {}
    for beam in elements:
        key = _group_key(beam, length_tolerance_mm)
        groups.setdefault(key, []).append(beam)

    lines: list[BomLine] = []
    for position, (_, members) in enumerate(groups.items(), start=1):
        sample = members[0]
        name = _profile_label(sample.profile)
        size = f"{_profile_dimensions_str(sample.profile)} мм, L={sample.length_mm:.0f} мм"
        lines.append(
            BomLine(position=position, name=name, size=size, material_name=sample.material.name, count=len(members))
        )
    return lines
