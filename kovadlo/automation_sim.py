"""
Симуляція сценарію в часі (модуль 13): подаєш послідовність подій
(зміни вхідних сигналів у певні моменти часу), система рахує зміну
станів і виходів по кроках — детермінований прогін того самого
`apply_step` (`automation_logic.py`) по черзі для кожної події.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .automation_logic import MachineState, Scenario, apply_step


@dataclass(frozen=True)
class SimulationStep:
    """Одна подія симуляції: момент часу + зміни вхідних сигналів
    (лише перелічені входи змінюються, решта зберігає попереднє
    значення — як реальні контакти, що тримають стан, поки їх не
    перемкнули)."""

    time_s: float
    inputs: dict[str, bool] = field(default_factory=dict)


@dataclass(frozen=True)
class SimulationLogEntry:
    """Стан системи одразу після обробки однієї події симуляції."""

    time_s: float
    state: str
    outputs: dict[str, bool]
    fired_rules: list[str]


@dataclass
class SimulationResult:
    """Повний журнал прогону сценарію."""

    scenario_name: str
    log: list[SimulationLogEntry]
    final_state: str

    def reached_state(self, state: str) -> bool:
        """Чи побувала система у стані `state` хоч раз за час симуляції."""
        return any(entry.state == state for entry in self.log)


def run_scenario(
    scenario: Scenario, steps: list[SimulationStep], *, initial_inputs: dict[str, bool] | None = None
) -> SimulationResult:
    """Прогін сценарію по послідовності подій `steps` (мають бути
    відсортовані за часом, що не спадає — таймери рахуються від
    модельного часу)."""
    machine_state = MachineState(state=scenario.initial_state, input_values=dict(initial_inputs or {}))

    log: list[SimulationLogEntry] = []
    last_time_s = float("-inf")
    for step in steps:
        if step.time_s < last_time_s:
            raise ValueError(f"Кроки симуляції мають бути відсортовані за часом (t={step.time_s} після t={last_time_s})")
        last_time_s = step.time_s

        machine_state.input_values.update(step.inputs)
        fired = apply_step(scenario, machine_state, step.time_s)
        log.append(
            SimulationLogEntry(
                time_s=step.time_s,
                state=machine_state.state,
                outputs=dict(machine_state.output_values),
                fired_rules=[rule.name for rule in fired],
            )
        )

    return SimulationResult(scenario_name=scenario.name, log=log, final_state=machine_state.state)
