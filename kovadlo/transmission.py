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

`Gear`/`GearMesh`/`GearTrain` — зубчасте зачеплення окремо від
`Transmission` вище: там ratio — довільне число з паспорта, тут воно
виведене з чисел зубів (n_вх·z_вх = n_вих·z_вих — однакова колова
швидкість на ділильному колі), і зовнішнє зачеплення реверсує напрям
обертання, чого базовий `Transmission.output_rpm` не враховує (там
немає поняття знаку/напряму), тому ці класи — окремі, без спадкування.
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


_MIN_TEETH = 8  # менше — підрізання ніжки зуба при стандартному нарізанні (орієнтовна практична межа)


@dataclass(frozen=True)
class Gear:
    """Циліндричне зубчасте колесо: модуль, число зубів, ширина вінця, мм.

    `module_mm` — модуль зачеплення (крок/π), мм; два колеса можуть
    зачепитись, лише якщо в них однаковий модуль (`GearMesh`).
    """

    module_mm: float
    teeth: int
    width_mm: float

    def __post_init__(self) -> None:
        if self.module_mm <= 0:
            raise ValueError("Модуль зубчастого колеса має бути додатним")
        if self.teeth < _MIN_TEETH:
            raise ValueError(f"Число зубів має бути не менше {_MIN_TEETH}")
        if self.width_mm <= 0:
            raise ValueError("Ширина вінця має бути додатною")

    @property
    def pitch_diameter_mm(self) -> float:
        """Ділильний діаметр, мм: d = m·z."""
        return self.module_mm * self.teeth

    @property
    def outer_diameter_mm(self) -> float:
        """Зовнішній діаметр, мм: da = d + 2·m (висота голівки зуба = m)."""
        return self.pitch_diameter_mm + 2 * self.module_mm


@dataclass(frozen=True)
class GearMesh:
    """Пара коліс у зовнішньому зачепленні (`gear_a` веде, `gear_b` веде́ний).

    Зачеплення можливе лише для однакового модуля обох коліс — інакше
    крок зубів не збігається і колеса фізично не зчепляться.
    """

    gear_a: Gear
    gear_b: Gear

    def __post_init__(self) -> None:
        if self.gear_a.module_mm != self.gear_b.module_mm:
            raise ValueError(
                f"Колеса з різним модулем не зчепити: {self.gear_a.module_mm} і {self.gear_b.module_mm}"
            )

    @property
    def center_distance_mm(self) -> float:
        """Міжосьова відстань, мм: (d_a + d_b) / 2."""
        return (self.gear_a.pitch_diameter_mm + self.gear_b.pitch_diameter_mm) / 2.0

    @property
    def ratio(self) -> float:
        """Передатне число i = n_вх/n_вих = z_b / z_a (однакова колова
        швидкість на ділильних колах: n_a·z_a = n_b·z_b)."""
        return self.gear_b.teeth / self.gear_a.teeth

    def output_rpm(self, input_rpm: float) -> float:
        """Оберти веденого колеса (`gear_b`) при вхідних обертах `gear_a`
        на `input_rpm`. Зовнішнє зачеплення реверсує напрям обертання —
        результат зі знаком, протилежним до `input_rpm`."""
        return -input_rpm / self.ratio


@dataclass(frozen=True)
class GearTrain:
    """Ланцюг зачеплень одне за одним: вихід `meshes[i]` — вхід `meshes[i+1]`."""

    meshes: list[GearMesh]

    def __post_init__(self) -> None:
        if not self.meshes:
            raise ValueError("Ланцюг зачеплень не може бути порожнім")

    @property
    def total_ratio(self) -> float:
        """Сумарне передавальне число — добуток передатних чисел усіх зачеплень."""
        total = 1.0
        for mesh in self.meshes:
            total *= mesh.ratio
        return total

    def output_rpm(self, input_rpm: float) -> float:
        """Оберти на виході останнього зачеплення ланцюга; напрям (знак)
        враховує реверс кожного окремого зовнішнього зачеплення по черзі
        — послідовне застосування `GearMesh.output_rpm`, а не ділення
        на `total_ratio` напряму, щоб знак не загубився."""
        rpm = input_rpm
        for mesh in self.meshes:
            rpm = mesh.output_rpm(rpm)
        return rpm
