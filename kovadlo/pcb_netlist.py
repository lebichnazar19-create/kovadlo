"""
Схема (логічний рівень): список компонентів + нетлист — з'єднання між
конкретними виводами, згруповані в ланцюги (net). Ланцюги живлення
(VCC, GND) виділені окремим типом для перевірки короткого замикання.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .pcb_component import Component


class NetKind(Enum):
    """Тип ланцюга схеми."""

    SIGNAL = "сигнал"
    POWER = "живлення"
    GROUND = "земля"


@dataclass(frozen=True)
class PinRef:
    """Посилання на конкретний вивід конкретного компонента (за позначенням)."""

    component: str  # Component.reference, напр. "R1"
    pin: int

    def __str__(self) -> str:
        return f"{self.component}.{self.pin}"


@dataclass
class Net:
    """Ланцюг схеми: назва, тип, список під'єднаних виводів.

    `voltage_v` — номінальна напруга ланцюга відносно землі (напр., VCC=5.0,
    GND=0.0); опціональна, потрібна лише для перевірки зазорів між
    доріжками різних ланцюгів на платі (див. `pcb_checks.py`)."""

    name: str
    kind: NetKind = NetKind.SIGNAL
    pins: list[PinRef] = field(default_factory=list)
    voltage_v: float | None = None

    def __post_init__(self) -> None:
        if len(self.pins) < 1:
            raise ValueError(f"Ланцюг «{self.name}» не має жодного під'єднаного виводу")


@dataclass
class ShortCircuit:
    """Знайдене коротке замикання: один вивід одночасно в кількох ланцюгах."""

    pin: PinRef
    nets: list[str]

    def __str__(self) -> str:
        return f"{self.pin}: одночасно в ланцюгах {', '.join(self.nets)}"


@dataclass
class Netlist:
    """Схема: компоненти (за позначенням) + список ланцюгів."""

    components: dict[str, Component]
    nets: list[Net] = field(default_factory=list)

    def __post_init__(self) -> None:
        known_refs = set(self.components)
        for net in self.nets:
            for pin_ref in net.pins:
                if pin_ref.component not in known_refs:
                    raise ValueError(
                        f"Ланцюг «{net.name}» посилається на невідомий компонент «{pin_ref.component}»"
                    )
                component = self.components[pin_ref.component]
                valid_numbers = {p.number for p in component.footprint.pins}
                if pin_ref.pin not in valid_numbers:
                    raise ValueError(
                        f"Ланцюг «{net.name}»: компонент «{pin_ref.component}» "
                        f"не має виводу №{pin_ref.pin}"
                    )

    def net_of(self, pin_ref: PinRef) -> list[Net]:
        """Усі ланцюги, до яких під'єднаний цей вивід (у справній схемі — щонайбільше один)."""
        return [net for net in self.nets if pin_ref in net.pins]

    def all_pin_refs(self) -> list[PinRef]:
        """Усі фізичні виводи всіх компонентів схеми."""
        return [
            PinRef(component=ref, pin=pin.number)
            for ref, component in self.components.items()
            for pin in component.footprint.pins
        ]

    def dangling_pins(self) -> list[PinRef]:
        """Виводи, які існують на компонентах, але не під'єднані до жодного ланцюга."""
        connected = {pin_ref for net in self.nets for pin_ref in net.pins}
        return [pin_ref for pin_ref in self.all_pin_refs() if pin_ref not in connected]

    def short_circuits(self) -> list[ShortCircuit]:
        """Виводи, під'єднані одночасно до кількох ланцюгів — це коротке
        замикання цих ланцюгів між собою (окремий фізичний вивід може
        належати лише одному електричному вузлу). Особливо небезпечний
        випадок — коли серед цих ланцюгів є і `POWER`, і `GROUND`."""
        by_pin: dict[PinRef, list[Net]] = {}
        for net in self.nets:
            for pin_ref in net.pins:
                by_pin.setdefault(pin_ref, []).append(net)
        return [
            ShortCircuit(pin=pin_ref, nets=[n.name for n in nets])
            for pin_ref, nets in by_pin.items()
            if len(nets) > 1
        ]

    def power_ground_shorts(self) -> list[ShortCircuit]:
        """Підмножина `short_circuits()`, де серед замкнених ланцюгів є і
        живлення, і земля — найкритичніша помилка схеми."""
        result = []
        for short in self.short_circuits():
            kinds = {net.kind for net in self.net_of(short.pin)}
            if NetKind.POWER in kinds and NetKind.GROUND in kinds:
                result.append(short)
        return result
