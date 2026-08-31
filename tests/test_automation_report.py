"""Тести текстових звітів модуля 13 — лише перевірка вмісту (без графіки)."""

from kovadlo.automation_logic import Action, Condition, Rule, Scenario
from kovadlo.automation_report import (
    format_controller_report,
    format_gate_system_report,
    format_scenario_report,
    format_simulation_report,
)
from kovadlo.automation_sim import SimulationStep, run_scenario
from kovadlo.controller import Controller, ControllerSpec
from kovadlo.gate_automation import build_gate_scenario
from kovadlo.sensors import OutputType, Sensor, SensorKind


def test_format_controller_report_ok():
    ctrl = Controller(spec=ControllerSpec(name="Тест", digital_inputs=2, analog_inputs=1, digital_outputs=1, pwm_outputs=0))
    ctrl.bind_input("D0", Sensor(name="Кнопка", kind=SensorKind.BUTTON, output_type=OutputType.DIGITAL, voltage_v=5.0, current_a=0.001))
    result = ctrl.check()
    report = format_controller_report(ctrl, result)
    assert "Тест" in report
    assert "1/2" in report
    assert "ПРОХОДИТЬ" in report
    assert "Несумісні напруги" not in report


def test_format_controller_report_lists_issues():
    ctrl = Controller(spec=ControllerSpec(name="Тест", digital_inputs=1, analog_inputs=0, digital_outputs=0, pwm_outputs=0, max_current_per_output_a=0.1))
    ctrl.bind_input("D0", Sensor(name="Датчик 24В", kind=SensorKind.MOTION, output_type=OutputType.DIGITAL, voltage_v=24.0, current_a=0.02))
    result = ctrl.check()
    report = format_controller_report(ctrl, result)
    assert "Несумісні напруги" in report
    assert "НЕ ПРОХОДИТЬ" in report


def test_format_scenario_report_no_dead_ends():
    scenario = Scenario(
        name="Проста", states={"A", "B"}, initial_state="A",
        rules=[Rule("a_to_b", Condition(state_in="A"), Action(new_state="B")), Rule("b_to_a", Condition(state_in="B"), Action(new_state="A"))],
    )
    report = format_scenario_report(scenario)
    assert "Проста" in report
    assert "Глухі кути: немає" in report
    assert "Порушень заборонених переходів немає" in report


def test_format_scenario_report_lists_dead_ends():
    scenario = Scenario(name="Пастка", states={"A", "B"}, initial_state="A", rules=[Rule("a_to_b", Condition(state_in="A"), Action(new_state="B"))])
    report = format_scenario_report(scenario)
    assert "Глухі кути: B" in report


def test_format_simulation_report_contains_steps_and_final_state():
    system = build_gate_scenario()
    steps = [
        SimulationStep(0.0, {
            "кнопка": False, "кінцевик_відкрито": False, "кінцевик_закрито": True,
            "фотобар'єр_перекрито": False, "скидання": False,
        }),
        SimulationStep(1.0, {"кнопка": True}),
    ]
    result = run_scenario(system.scenario, steps)
    report = format_simulation_report(result)
    assert "Автоматична брама" in report
    assert "ВІДКРИВАЄТЬСЯ" in report
    assert "Кнопка із закрито" in report
    assert f"Кінцевий стан: {result.final_state}" in report


def test_format_gate_system_report_combines_everything():
    system = build_gate_scenario()
    report = format_gate_system_report(system)
    assert "Контролер брами" in report
    assert "Автоматична брама" in report
    assert f"{system.cycle_time_s:.2f}" in report
    assert f"{system.timeout_s:.2f}" in report
    assert "ПРОХОДИТЬ" in report
