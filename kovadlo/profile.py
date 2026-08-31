"""
Профілі (перерізи) елементів.

Це ключова точка розширення архітектури: `Profile` — абстрактний базовий
клас, і будь-який `Element` (зокрема `Wall`) працює з ним лише через цей
інтерфейс. Сьогодні реально потрібен лише прямокутний переріз для стін,
але щоб довести, що архітектура витримає додавання металопрофілів без
переписування ядра, тут одразу є `SteelChannelProfile` (швелер),
`SteelAngleProfile` (кутник) і `SteelPipeProfile` (труба) — жоден з класів
Element/Wall/Room про них нічого не знає і знати не повинен.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass


class Profile(ABC):
    """Базовий клас перерізу елемента."""

    name: str = "profile"

    @abstractmethod
    def cross_section_area_mm2(self) -> float:
        """Площа поперечного перерізу профілю, мм²."""
        raise NotImplementedError


@dataclass
class RectangularProfile(Profile):
    """Прямокутний переріз — базовий профіль для стін.

    thickness — товщина стіни (по горизонталі), height — висота
    (по вертикалі). Обидва в міліметрах.
    """

    thickness: float
    height: float = 0.0
    name: str = "rectangular"

    def cross_section_area_mm2(self) -> float:
        return self.thickness * self.height


@dataclass
class SteelChannelProfile(Profile):
    """Металевий швелер (спрощена модель перерізу).

    height           — висота профілю, мм
    flange_width     — ширина полиці, мм
    web_thickness    — товщина стінки, мм
    flange_thickness — товщина полиці, мм
    """

    height: float
    flange_width: float
    web_thickness: float
    flange_thickness: float
    name: str = "steel_channel"

    def cross_section_area_mm2(self) -> float:
        web_area = self.height * self.web_thickness
        flanges_area = 2 * self.flange_width * self.flange_thickness
        return web_area + flanges_area


@dataclass
class SteelAngleProfile(Profile):
    """Металевий кутник (рівно- чи нерівнополичний).

    leg_a, leg_b — довжини полиць, мм; thickness — товщина, мм.
    """

    leg_a: float
    leg_b: float
    thickness: float
    name: str = "steel_angle"

    def cross_section_area_mm2(self) -> float:
        return self.thickness * (self.leg_a + self.leg_b - self.thickness)


@dataclass
class SteelPipeProfile(Profile):
    """Кругла металева труба.

    outer_diameter — зовнішній діаметр, мм; wall_thickness — товщина стінки, мм.
    """

    outer_diameter: float
    wall_thickness: float
    name: str = "steel_pipe"

    def cross_section_area_mm2(self) -> float:
        outer_r = self.outer_diameter / 2
        inner_r = outer_r - self.wall_thickness
        return math.pi * (outer_r**2 - inner_r**2)
