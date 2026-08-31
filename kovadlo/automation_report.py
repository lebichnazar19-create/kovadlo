"""Текстові звіти модуля 13 (керування та логіка) — без графіки."""

from __future__ import annotations

from .automation_logic import Scenario, find_dead_end_states, find_forbidden_rule_violations
from .automation_sim import SimulationResult
from .controller import Controller, ControllerCheckResult
from .gate_automation import GateSystem


def format_controller_report(controller: Controller, result: ControllerCheckResult) -> str:
    """Звіт контролера: використання пінів, проблеми з напругою/струмом."""
    spec = controller.spec
    lines = [
        f"Контролер «{spec.name}»",
        f"  Цифрові входи:  {result.digital_inputs_used}/{result.digital_inputs_available}"
        f" {'OK' if result.enough_digital_inputs else 'НЕ ВИСТАЧАЄ'}",
        f"  Аналогові входи: {result.analog_inputs_used}/{result.analog_inputs_available}"
        f" {'OK' if result.enough_analog_inputs else 'НЕ ВИСТАЧАЄ'}",
        f"  Цифрові виходи: {result.digital_outputs_used}/{result.digital_outputs_available}"
        f" {'OK' if result.enough_digital_outputs else 'НЕ ВИСТАЧАЄ'}",
        f"  ШІМ-виходи:     {result.pwm_outputs_used}/{result.pwm_outputs_available}"
        f" {'OK' if result.enough_pwm_outputs else 'НЕ ВИСТАЧАЄ'}",
    ]
    if result.voltage_issues:
        lines.append("  Несумісні напруги:")
        lines += [f"    - {issue.message}" for issue in result.voltage_issues]
    if result.current_issues:
        lines.append("  Перевищення струму на виході:")
        lines += [f"    - {issue.message}" for issue in result.current_issues]
    lines.append(f"  Перевірка контролера: {'ПРОХОДИТЬ' if result.passes else 'НЕ ПРОХОДИТЬ'}")
    return "\n".join(lines)


def format_scenario_report(scenario: Scenario) -> str:
    """Звіт сценарію: стани, правила, таймери, глухі кути, заборонені переходи."""
    dead_ends = find_dead_end_states(scenario)
    violations = find_forbidden_rule_violations(scenario)
    lines = [
        f"Сценарій «{scenario.name}»",
        f"  Станів: {len(scenario.states)} ({', '.join(sorted(scenario.states))})",
        f"  Початковий стан: {scenario.initial_state}",
        f"  Правил: {len(scenario.rules)}",
        f"  Таймерів: {len(scenario.timers)}",
    ]
    for name, spec in scenario.timers.items():
        lines.append(f"    - {name}: {spec.duration_s:.1f} с")
    lines.append(f"  Глухі кути: {', '.join(sorted(dead_ends)) if dead_ends else 'немає'}")
    if violations:
        lines.append("  Заборонені переходи, яких дозволяють досягти правила:")
        lines += [f"    - {rule.name}" for rule in violations]
    else:
        lines.append("  Порушень заборонених переходів немає")
    return "\n".join(lines)


def format_simulation_report(result: SimulationResult) -> str:
    """Звіт прогону симуляції: журнал по кроках + кінцевий стан."""
    lines = [f"Симуляція сценарію «{result.scenario_name}»", ""]
    header = f"{'Час, с':>10}  {'Стан':<16} {'Спрацювали правила':<40} Виходи"
    lines.append(header)
    lines.append("-" * len(header))
    for entry in result.log:
        rules = ", ".join(entry.fired_rules) if entry.fired_rules else "-"
        outputs = ", ".join(f"{name}={value}" for name, value in sorted(entry.outputs.items())) or "-"
        lines.append(f"{entry.time_s:>10.2f}  {entry.state:<16} {rules:<40} {outputs}")
    lines.append("")
    lines.append(f"Кінцевий стан: {result.final_state}")
    return "\n".join(lines)


def format_gate_system_report(system: GateSystem) -> str:
    """Зведений звіт зібраного прикладу автоматичної брами: контролер +
    сценарій + розрахунок часу циклу."""
    controller_result = system.controller.check()
    lines = [
        format_controller_report(system.controller, controller_result),
        "",
        format_scenario_report(system.scenario),
        "",
        f"Двигун «{system.motor.name}» через редуктор i={system.transmission.gear_ratio:.1f}",
        f"  Час ходу (відкриття/закриття): {system.cycle_time_s:.2f} с",
        f"  Аварійний таймаут:              {system.timeout_s:.2f} с",
    ]
    return "\n".join(lines)
