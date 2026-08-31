"""
Освітлення (8.1): світильник як точка на плані, розрахунок освітленості
приміщення (лк), підбір кількості світильників, зв'язок з модулем 4.

Розрахунок — спрощений "метод коефіцієнта використання" (lumen method):

    E = (Φ_загальний · UF · MF) / S

де UF — коефіцієнт використання світлового потоку (частка потоку, що
реально доходить до робочої площини — залежить від індексу приміщення
й коефіцієнтів відбиття поверхонь), MF — коефіцієнт запасу (старіння
ламп, забруднення). Тут UF/MF — явні параметри з орієнтовними
значеннями за замовчуванням (`lighting_norms.py`), а не таблична
функція індексу приміщення — для точного проєктування використовуйте
фотометричні дані конкретного світильника й таблиці коефіцієнта
використання виробника.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from .cable_route import CableRoute
from .electrical_group import Group
from .electrical_norms import PhaseType
from .electrical_point import ConsumptionPoint, PointKind
from .geometry import Point
from .lighting_norms import (
    DEFAULT_MAINTENANCE_FACTOR,
    DEFAULT_UTILIZATION_FACTOR,
    RECOMMENDED_LUX,
    RoomPurpose,
)


class FixtureKind(Enum):
    """Тип світильника."""

    CEILING = "стельовий"
    WALL = "настінний"
    SPOT = "точковий"
    PENDANT = "підвісний"
    LED_STRIP = "led-стрічка"


@dataclass
class LightFixture:
    """Світильник як точка на плані."""

    name: str
    kind: FixtureKind
    position: Point
    luminous_flux_lm: float
    power_w: float
    beam_angle_deg: float = 120.0
    color_temp_k: float = 4000.0

    def __post_init__(self) -> None:
        if self.luminous_flux_lm <= 0:
            raise ValueError("Світловий потік має бути додатним")
        if self.power_w <= 0:
            raise ValueError("Потужність світильника має бути додатною")

    @property
    def luminous_efficacy_lm_per_w(self) -> float:
        """Світлова віддача, лм/Вт."""
        return self.luminous_flux_lm / self.power_w

    def to_consumption_point(self) -> ConsumptionPoint:
        """Місток до модуля 4: світильник як точка споживання типу LIGHT."""
        return ConsumptionPoint(name=self.name, kind=PointKind.LIGHT, position=self.position, power_w=self.power_w)


def illuminance_lux(
    total_luminous_flux_lm: float,
    area_m2: float,
    *,
    utilization_factor: float = DEFAULT_UTILIZATION_FACTOR,
    maintenance_factor: float = DEFAULT_MAINTENANCE_FACTOR,
) -> float:
    """Освітленість робочої площини, лк: E = Φ·UF·MF / S."""
    if area_m2 <= 0:
        raise ValueError("Площа приміщення має бути додатною")
    if not (0 < utilization_factor <= 1) or not (0 < maintenance_factor <= 1):
        raise ValueError("UF і MF мають бути в діапазоні (0, 1]")
    return total_luminous_flux_lm * utilization_factor * maintenance_factor / area_m2


def required_luminous_flux_lm(
    target_lux: float,
    area_m2: float,
    *,
    utilization_factor: float = DEFAULT_UTILIZATION_FACTOR,
    maintenance_factor: float = DEFAULT_MAINTENANCE_FACTOR,
) -> float:
    """Обернена формула: сумарний світловий потік, потрібний для
    досягнення `target_lux` на площі `area_m2`."""
    if target_lux <= 0:
        raise ValueError("Цільова освітленість має бути додатною")
    if not (0 < utilization_factor <= 1) or not (0 < maintenance_factor <= 1):
        raise ValueError("UF і MF мають бути в діапазоні (0, 1]")
    return target_lux * area_m2 / (utilization_factor * maintenance_factor)


def fixtures_needed(required_flux_lm: float, fixture_flux_lm: float) -> int:
    """Кількість однакових світильників, щоб покрити потрібний сумарний потік."""
    if fixture_flux_lm <= 0:
        raise ValueError("Світловий потік одного світильника має бути додатним")
    return math.ceil(required_flux_lm / fixture_flux_lm)


@dataclass
class LightingPlan:
    """Результат підбору освітлення кімнати."""

    room_purpose: RoomPurpose
    area_m2: float
    target_lux: float
    fixture_flux_lm: float
    fixture_power_w: float
    fixtures_count: int
    achieved_lux: float

    @property
    def total_power_w(self) -> float:
        return self.fixtures_count * self.fixture_power_w

    @property
    def meets_target(self) -> bool:
        return self.achieved_lux >= self.target_lux


def plan_lighting(
    area_m2: float,
    purpose: RoomPurpose,
    fixture_flux_lm: float,
    fixture_power_w: float,
    *,
    utilization_factor: float = DEFAULT_UTILIZATION_FACTOR,
    maintenance_factor: float = DEFAULT_MAINTENANCE_FACTOR,
) -> LightingPlan:
    """Підбирає кількість однакових світильників для приміщення заданого
    призначення (`RoomPurpose`) і площі."""
    target_lux = RECOMMENDED_LUX[purpose]
    required_flux = required_luminous_flux_lm(
        target_lux, area_m2, utilization_factor=utilization_factor, maintenance_factor=maintenance_factor
    )
    count = fixtures_needed(required_flux, fixture_flux_lm)
    achieved = illuminance_lux(
        count * fixture_flux_lm, area_m2, utilization_factor=utilization_factor, maintenance_factor=maintenance_factor
    )
    return LightingPlan(
        room_purpose=purpose,
        area_m2=area_m2,
        target_lux=target_lux,
        fixture_flux_lm=fixture_flux_lm,
        fixture_power_w=fixture_power_w,
        fixtures_count=count,
        achieved_lux=achieved,
    )


def lighting_group(fixtures: list[LightFixture], routes: dict[str, CableRoute], name: str = "Освітлення") -> Group:
    """Будує групу модуля 4 зі світильників — саме так освітлення
    "стає групою в проводці" без зміни ядра модуля 4: `LightFixture`
    перетворюється на `ConsumptionPoint` (`to_consumption_point`), а
    `Group` — це вже наявна сутність модуля 4."""
    points = [fixture.to_consumption_point() for fixture in fixtures]
    return Group(name=name, phase=PhaseType.SINGLE, points=points, routes=routes)
