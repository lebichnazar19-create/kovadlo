"""
Виконавчі механізми (модуль 13): реле, контактор, електромагнітний
замок, соленоїд, клапан — плюс адаптерні функції, що дозволяють
трактувати нарівні з ними й `Motor` (модуль 12) як виконавчий механізм
контролера, не змінюючи `motor.py` (ядро) і не змушуючи його
успадковувати щось нове.

Один клас `Actuator` + перелік `ActuatorKind` — той самий підхід, що й
`ConsumptionPoint`+`PointKind` (модуль 4) чи `LightFixture`+`FixtureKind`
(модуль 8): різні типи механізмів відрізняються лише семантикою
(`kind`), а не набором полів (напруга, струм, час спрацювання).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Union

from .motor import Motor


class ActuatorKind(Enum):
    """Тип виконавчого механізму (крім двигуна — той описаний повністю
    в модулі 12, `motor.Motor`)."""

    RELAY = "реле"
    CONTACTOR = "контактор"
    LOCK = "електромагнітний замок"
    SOLENOID = "соленоїд"
    VALVE = "клапан"


@dataclass(kw_only=True)
class Actuator:
    """Простий виконавчий механізм: напруга, струм, час спрацювання."""

    name: str
    kind: ActuatorKind
    voltage_v: float
    current_a: float
    actuation_time_s: float

    def __post_init__(self) -> None:
        if self.voltage_v <= 0:
            raise ValueError("Напруга живлення механізму має бути додатною")
        if self.current_a < 0:
            raise ValueError("Струм не може бути від'ємним")
        if self.actuation_time_s < 0:
            raise ValueError("Час спрацювання не може бути від'ємним")

    @property
    def power_w(self) -> float:
        return self.voltage_v * self.current_a


# Виконавчий механізм на виході контролера — або повний `Motor` (модуль
# 12), або один із простих механізмів цього файлу.
ActuatorLike = Union[Motor, Actuator]


def actuator_voltage_v(actuator: ActuatorLike) -> float:
    """Напруга живлення механізму — уніфіковано для `Motor` і `Actuator`
    (в обох поле зветься однаково, `voltage_v`, тож насправді просто
    повертає його; функція існує, щоб виклик коду не залежав від
    конкретного типу)."""
    return actuator.voltage_v


def actuator_current_a(actuator: ActuatorLike) -> float:
    """Номінальний струм механізму — `Motor.nominal_current_a` чи
    `Actuator.current_a` залежно від типу."""
    if isinstance(actuator, Motor):
        return actuator.nominal_current_a
    return actuator.current_a


def actuator_kind_label(actuator: ActuatorLike) -> str:
    """Людський опис типу механізму — `MotorKind`/`ActuatorKind`, залежно від типу."""
    return actuator.kind.value
