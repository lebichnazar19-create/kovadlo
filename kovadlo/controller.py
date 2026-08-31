"""
Контролер (модуль 13): опис входів/виходів, прив'язка датчиків і
механізмів, перевірка пінів/напруг/струму.

Три перевірки, явно потрібні за завданням:
1. чи вистачає пінів (окремо цифрові/аналогові входи, цифрові/ШІМ виходи);
2. чи сумісні напруги (типові рівні 3.3/5/12 В — керуючий контролер і
   польові пристрої часто живляться від різних рейок, тому перевіряємо
   збіг з точністю до допуску, а не з логічною напругою самого контролера);
3. чи не перевищено допустимий струм на вихід (типове обмеження GPIO —
   якщо навантаження споживає більше, потрібне проміжне реле/драйвер,
   а не пряме підключення до піна).
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .actuators import ActuatorLike, actuator_current_a, actuator_voltage_v
from .sensors import OutputType, Sensor


@dataclass(kw_only=True)
class ControllerSpec:
    """Паспортні дані контролера: кількість входів/виходів кожного типу."""

    name: str
    digital_inputs: int
    analog_inputs: int
    digital_outputs: int
    pwm_outputs: int
    max_current_per_output_a: float = 0.5

    def __post_init__(self) -> None:
        for field_name in ("digital_inputs", "analog_inputs", "digital_outputs", "pwm_outputs"):
            if getattr(self, field_name) < 0:
                raise ValueError(f"{field_name} не може бути від'ємним")
        if self.max_current_per_output_a <= 0:
            raise ValueError("max_current_per_output_a має бути додатним")


@dataclass(frozen=True)
class PinIssue:
    """Одна знайдена проблема прив'язки: пін + людське пояснення."""

    pin_id: str
    message: str


@dataclass
class ControllerCheckResult:
    """Результат перевірки контролера: використання пінів + список проблем."""

    digital_inputs_used: int
    digital_inputs_available: int
    analog_inputs_used: int
    analog_inputs_available: int
    digital_outputs_used: int
    digital_outputs_available: int
    pwm_outputs_used: int
    pwm_outputs_available: int
    voltage_issues: list[PinIssue] = field(default_factory=list)
    current_issues: list[PinIssue] = field(default_factory=list)

    @property
    def enough_digital_inputs(self) -> bool:
        return self.digital_inputs_used <= self.digital_inputs_available

    @property
    def enough_analog_inputs(self) -> bool:
        return self.analog_inputs_used <= self.analog_inputs_available

    @property
    def enough_digital_outputs(self) -> bool:
        return self.digital_outputs_used <= self.digital_outputs_available

    @property
    def enough_pwm_outputs(self) -> bool:
        return self.pwm_outputs_used <= self.pwm_outputs_available

    @property
    def enough_pins(self) -> bool:
        return (
            self.enough_digital_inputs
            and self.enough_analog_inputs
            and self.enough_digital_outputs
            and self.enough_pwm_outputs
        )

    @property
    def passes(self) -> bool:
        return self.enough_pins and not self.voltage_issues and not self.current_issues


def _voltage_compatible(voltage_v: float, available_voltages_v: tuple[float, ...], tolerance_v: float) -> bool:
    return any(abs(voltage_v - available) <= tolerance_v for available in available_voltages_v)


@dataclass(kw_only=True)
class Controller:
    """Контролер із прив'язаними входами (датчики) й виходами
    (двигуни/механізми)."""

    spec: ControllerSpec
    input_bindings: dict[str, Sensor] = field(default_factory=dict)
    output_bindings: dict[str, tuple[ActuatorLike, bool]] = field(default_factory=dict)

    def bind_input(self, pin_id: str, sensor: Sensor) -> None:
        if pin_id in self.input_bindings:
            raise ValueError(f"Вхід «{pin_id}» уже зайнятий")
        self.input_bindings[pin_id] = sensor

    def bind_output(self, pin_id: str, actuator: ActuatorLike, *, uses_pwm: bool = False) -> None:
        if pin_id in self.output_bindings:
            raise ValueError(f"Вихід «{pin_id}» уже зайнятий")
        self.output_bindings[pin_id] = (actuator, uses_pwm)

    def check(
        self,
        *,
        available_voltages_v: tuple[float, ...] = (3.3, 5.0, 12.0),
        voltage_tolerance_v: float = 0.3,
    ) -> ControllerCheckResult:
        """Повна перевірка: піни, напруги, струм на виходах."""
        digital_inputs_used = sum(1 for s in self.input_bindings.values() if s.output_type is OutputType.DIGITAL)
        analog_inputs_used = sum(1 for s in self.input_bindings.values() if s.output_type is OutputType.ANALOG)
        digital_outputs_used = sum(1 for _, uses_pwm in self.output_bindings.values() if not uses_pwm)
        pwm_outputs_used = sum(1 for _, uses_pwm in self.output_bindings.values() if uses_pwm)

        voltage_issues: list[PinIssue] = []
        for pin_id, sensor in self.input_bindings.items():
            if not _voltage_compatible(sensor.voltage_v, available_voltages_v, voltage_tolerance_v):
                voltage_issues.append(
                    PinIssue(
                        pin_id,
                        f"Вхід «{pin_id}» ({sensor.name}): напруга датчика {sensor.voltage_v:.1f} В "
                        f"не відповідає жодній доступній рейці {available_voltages_v}",
                    )
                )
        for pin_id, (actuator, _) in self.output_bindings.items():
            voltage_v = actuator_voltage_v(actuator)
            if not _voltage_compatible(voltage_v, available_voltages_v, voltage_tolerance_v):
                voltage_issues.append(
                    PinIssue(
                        pin_id,
                        f"Вихід «{pin_id}» ({actuator.name}): напруга механізму {voltage_v:.1f} В "
                        f"не відповідає жодній доступній рейці {available_voltages_v}",
                    )
                )

        current_issues: list[PinIssue] = []
        for pin_id, (actuator, _) in self.output_bindings.items():
            current_a = actuator_current_a(actuator)
            if current_a > self.spec.max_current_per_output_a:
                current_issues.append(
                    PinIssue(
                        pin_id,
                        f"Вихід «{pin_id}» ({actuator.name}): струм {current_a:.3f} А перевищує допустимий "
                        f"{self.spec.max_current_per_output_a:.3f} А на вихід — потрібне проміжне реле/драйвер",
                    )
                )

        return ControllerCheckResult(
            digital_inputs_used=digital_inputs_used,
            digital_inputs_available=self.spec.digital_inputs,
            analog_inputs_used=analog_inputs_used,
            analog_inputs_available=self.spec.analog_inputs,
            digital_outputs_used=digital_outputs_used,
            digital_outputs_available=self.spec.digital_outputs,
            pwm_outputs_used=pwm_outputs_used,
            pwm_outputs_available=self.spec.pwm_outputs,
            voltage_issues=voltage_issues,
            current_issues=current_issues,
        )
