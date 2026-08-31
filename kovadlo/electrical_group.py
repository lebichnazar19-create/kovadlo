"""Група точок споживання і розрахунок кола (кабель, автомат, ПЗВ)."""

from __future__ import annotations

from dataclasses import dataclass, field

from .cable_route import CableRoute
from .electrical_norms import (
    MAX_VOLTAGE_DROP_PERCENT_DEFAULT,
    MIN_CROSS_SECTION_LIGHTING_MM2,
    VOLTAGE_V,
    PhaseType,
    calculate_current_a,
    rcd_required_for_kinds,
    select_breaker_rating_a,
    select_cross_section_mm2,
    voltage_drop_percent,
)
from .electrical_point import ConsumptionPoint


@dataclass
class Group:
    """Група точок споживання, що живиться від одного апарата захисту.

    `routes` — траса кожної точки від щитка (ключ — `ConsumptionPoint.name`).
    Кожна точка групи мусить мати свою трасу.
    """

    name: str
    phase: PhaseType
    points: list[ConsumptionPoint] = field(default_factory=list)
    routes: dict[str, CableRoute] = field(default_factory=dict)
    power_factor: float = 1.0
    connection_allowance_m: float = 0.5
    min_cross_section_mm2: float = MIN_CROSS_SECTION_LIGHTING_MM2
    max_voltage_drop_percent: float = MAX_VOLTAGE_DROP_PERCENT_DEFAULT

    def __post_init__(self) -> None:
        if not self.points:
            raise ValueError("Група має містити хоча б одну точку споживання")
        missing = [p.name for p in self.points if p.name not in self.routes]
        if missing:
            raise ValueError(f"Немає траси кабелю для точок: {', '.join(missing)}")

    @property
    def total_power_w(self) -> float:
        """Сумарна потужність групи, Вт."""
        return sum(p.power_w for p in self.points)

    @property
    def design_current_a(self) -> float:
        """Розрахунковий струм групи, А."""
        return calculate_current_a(self.total_power_w, self.phase, self.power_factor)

    @property
    def total_cable_length_m(self) -> float:
        """Сумарна довжина кабелю групи для закупівлі: довжина кожної
        траси плюс запас на підключення на кожну трасу окремо."""
        return sum(route.length_m + self.connection_allowance_m for route in self.routes.values())

    @property
    def critical_route_length_m(self) -> float:
        """Найдовша траса групи — визначальна для розрахунку перерізу за
        падінням напруги (найгірший випадок для спільного апарата захисту)."""
        return max(route.length_m for route in self.routes.values())


@dataclass
class GroupCalculation:
    """Результат розрахунку кола для групи."""

    group_name: str
    phase: PhaseType
    total_power_w: float
    design_current_a: float
    total_cable_length_m: float
    critical_route_length_m: float
    breaker_rating_a: float
    cross_section_mm2: float
    voltage_drop_percent: float
    rcd_required: bool
    rcd_note: str

    @property
    def voltage_v(self) -> float:
        return VOLTAGE_V[self.phase]


def calculate_group(group: Group) -> GroupCalculation:
    """Рахує коло для групи: номінал автомата, переріз жили за струмом і
    падінням напруги, потребу в ПЗВ/дифавтоматі."""
    design_current = group.design_current_a
    breaker_rating = select_breaker_rating_a(design_current)
    critical_length = group.critical_route_length_m
    cross_section = select_cross_section_mm2(
        design_current,
        breaker_rating,
        critical_length,
        group.phase,
        min_cross_section_mm2=group.min_cross_section_mm2,
        max_voltage_drop_percent=group.max_voltage_drop_percent,
    )
    drop = voltage_drop_percent(cross_section, design_current, critical_length, group.phase)
    needs_rcd, note = rcd_required_for_kinds({p.kind for p in group.points})

    return GroupCalculation(
        group_name=group.name,
        phase=group.phase,
        total_power_w=group.total_power_w,
        design_current_a=design_current,
        total_cable_length_m=group.total_cable_length_m,
        critical_route_length_m=critical_length,
        breaker_rating_a=breaker_rating,
        cross_section_mm2=cross_section,
        voltage_drop_percent=drop,
        rcd_required=needs_rcd,
        rcd_note=note,
    )
