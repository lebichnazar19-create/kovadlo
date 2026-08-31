"""
Обертання й передачі (модуль 12): переведення обертів у кутову
швидкість, потужність через крутний момент (P = M·ω), і три типи
механічних передач — теорія машин і механізмів.

Передача — незалежно від типу (пряма, редуктор, ремінна) — описується
одним і тим самим фізичним співвідношенням: передатне число `ratio` =
n_вх / n_вих (у скільки разів передача сповільнює обертання), при
цьому крутний момент на виході зростає в те саме число разів (з
поправкою на ККД, бо частина потужності йде на тертя):

    n_вих = n_вх / ratio
    M_вих = M_вх · ratio · η

Для редуктора `ratio` — це його передатне число (з паспорта/шильдика).
Для ремінної передачі `ratio` = D_веденого шківа / D_ведучого шківа
(без урахування прослизання ременя — ідеальний випадок).
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass


def rpm_to_rad_s(rpm: float) -> float:
    """Оберти на хвилину -> кутова швидкість, рад/с: ω = n·2π/60."""
    return rpm * 2 * math.pi / 60.0


def rad_s_to_rpm(angular_velocity_rad_s: float) -> float:
    """Кутова швидкість, рад/с -> оберти на хвилину."""
    return angular_velocity_rad_s * 60.0 / (2 * math.pi)


def power_w(torque_nm: float, angular_velocity_rad_s: float) -> float:
    """Потужність, Вт: P = M·ω."""
    return torque_nm * angular_velocity_rad_s


def torque_nm(power_w_: float, angular_velocity_rad_s: float) -> float:
    """Крутний момент, Н·м: M = P/ω."""
    if angular_velocity_rad_s == 0:
        raise ValueError("Кутова швидкість не може бути нульовою (момент при ω=0 не визначений)")
    return power_w_ / angular_velocity_rad_s


class Transmission(ABC):
    """Механічна передача: перераховує момент і оберти з входу на вихід."""

    efficiency: float = 1.0

    @abstractmethod
    def ratio(self) -> float:
        """Передатне число i = n_вх / n_вих."""
        raise NotImplementedError

    def output_angular_velocity_rad_s(self, input_angular_velocity_rad_s: float) -> float:
        return input_angular_velocity_rad_s / self.ratio()

    def output_rpm(self, input_rpm: float) -> float:
        return input_rpm / self.ratio()

    def output_torque_nm(self, input_torque_nm: float) -> float:
        return input_torque_nm * self.ratio() * self.efficiency


@dataclass
class DirectTransmission(Transmission):
    """Пряма передача (муфта, безпосереднє з'єднання) — ratio = 1."""

    efficiency: float = 1.0

    def ratio(self) -> float:
        return 1.0


@dataclass
class GearboxTransmission(Transmission):
    """Редуктор із передатним числом `gear_ratio` (з паспорта/шильдика)."""

    gear_ratio: float
    efficiency: float = 0.95

    def __post_init__(self) -> None:
        if self.gear_ratio <= 0:
            raise ValueError("Передатне число редуктора має бути додатним")
        if not (0 < self.efficiency <= 1):
            raise ValueError("ККД має бути в діапазоні (0, 1]")

    def ratio(self) -> float:
        return self.gear_ratio


@dataclass
class BeltTransmission(Transmission):
    """Ремінна передача: `pulley_ratio` = D_веденого шківа / D_ведучого
    шківа (ідеальний випадок, без прослизання ременя)."""

    pulley_ratio: float
    efficiency: float = 0.95

    def __post_init__(self) -> None:
        if self.pulley_ratio <= 0:
            raise ValueError("Відношення діаметрів шківів має бути додатним")
        if not (0 < self.efficiency <= 1):
            raise ValueError("ККД має бути в діапазоні (0, 1]")

    def ratio(self) -> float:
        return self.pulley_ratio

    @classmethod
    def from_pulley_diameters(cls, driving_diameter_mm: float, driven_diameter_mm: float, efficiency: float = 0.95) -> "BeltTransmission":
        """Зручний конструктор напряму з діаметрів шківів, мм."""
        if driving_diameter_mm <= 0 or driven_diameter_mm <= 0:
            raise ValueError("Діаметри шківів мають бути додатними")
        return cls(pulley_ratio=driven_diameter_mm / driving_diameter_mm, efficiency=efficiency)
