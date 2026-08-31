"""Матеріал елемента."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Material:
    """Матеріал будівельного елемента.

    density_kg_m3 — опційна густина (кг/м³), знадобиться пізніше для
    розрахунку ваги/навантаження; для площ вона не потрібна.
    """

    name: str
    density_kg_m3: float | None = None
