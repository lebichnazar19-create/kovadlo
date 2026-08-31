"""Тести симуляції сценарію в часі модуля 13."""

import pytest

from kovadlo.automation_logic import Action, Condition, Rule, Scenario, TimerSpec
from kovadlo.automation_sim import SimulationStep, run_scenario


def _gate_scenario() -> Scenario:
    states = {"ЗАКРИТО", "ВІДКРИВАЄТЬСЯ", "ВІДКРИТО", "АВАРІЯ"}
    rules = [
        Rule("Аварійний стоп", Condition(inputs={"аварія": True}), Action(new_state="АВАРІЯ")),
        Rule(
            "Старт відкриття",
            Condition(state_in="ЗАКРИТО", inputs={"кнопка": True}),
            Action(new_state="ВІДКРИВАЄТЬСЯ", outputs={"двигун_вперед": True}, start_timer="таймаут"),
        ),
        Rule(
            "Кінець відкриття",
            Condition(state_in="ВІДКРИВАЄТЬСЯ", inputs={"кінцевик_відкр": True}),
            Action(new_state="ВІДКРИТО", outputs={"двигун_вперед": False}, stop_timer="таймаут"),
        ),
    ]
    return Scenario(
        name="Брама", states=states, initial_state="ЗАКРИТО", rules=rules,
        timers={"таймаут": TimerSpec("таймаут", duration_s=10.0)},
    )


def test_run_scenario_hand_verified_log():
    scenario = _gate_scenario()
    steps = [
        SimulationStep(0.0, {"кнопка": False, "кінцевик_відкр": False, "аварія": False}),
        SimulationStep(1.0, {"кнопка": True}),
        SimulationStep(1.5, {"кнопка": False}),
        SimulationStep(6.0, {"кінцевик_відкр": True}),
    ]
    result = run_scenario(scenario, steps)

    assert [entry.state for entry in result.log] == ["ЗАКРИТО", "ВІДКРИВАЄТЬСЯ", "ВІДКРИВАЄТЬСЯ", "ВІДКРИТО"]
    assert result.log[1].fired_rules == ["Старт відкриття"]
    assert result.log[1].outputs["двигун_вперед"] is True
    assert result.log[2].fired_rules == []  # нічого не змінилось о 1.5с
    assert result.log[3].fired_rules == ["Кінець відкриття"]
    assert result.log[3].outputs["двигун_вперед"] is False
    assert result.final_state == "ВІДКРИТО"


def test_run_scenario_reached_state():
    scenario = _gate_scenario()
    steps = [
        SimulationStep(0.0, {"кнопка": True, "кінцевик_відкр": False, "аварія": False}),
        SimulationStep(5.0, {"кінцевик_відкр": True}),
    ]
    result = run_scenario(scenario, steps)
    assert result.reached_state("ВІДКРИВАЄТЬСЯ") is True
    assert result.reached_state("ВІДКРИТО") is True
    assert result.reached_state("АВАРІЯ") is False


def test_run_scenario_timeout_reaches_alarm():
    scenario = _gate_scenario()
    steps = [
        SimulationStep(0.0, {"кнопка": True, "кінцевик_відкр": False, "аварія": False}),
        SimulationStep(1.0, {"кнопка": False}),
        SimulationStep(15.0, {"аварія": True}),  # імітуємо зовнішній аварійний сигнал
    ]
    result = run_scenario(scenario, steps)
    assert result.final_state == "АВАРІЯ"
    assert result.reached_state("АВАРІЯ") is True


def test_run_scenario_rejects_unsorted_steps():
    scenario = _gate_scenario()
    with pytest.raises(ValueError):
        run_scenario(scenario, [SimulationStep(2.0, {}), SimulationStep(1.0, {})])


def test_run_scenario_allows_equal_timestamps():
    scenario = _gate_scenario()
    # Дві події в один момент часу — дозволено (напр. кілька сигналів
    # змінюються одночасно двома окремими записами).
    result = run_scenario(
        scenario,
        [
            SimulationStep(0.0, {"кнопка": False, "кінцевик_відкр": False, "аварія": False}),
            SimulationStep(0.0, {"кнопка": True}),
        ],
    )
    assert result.final_state == "ВІДКРИВАЄТЬСЯ"


def test_run_scenario_with_initial_inputs():
    scenario = _gate_scenario()
    result = run_scenario(
        scenario,
        [SimulationStep(1.0, {"кнопка": True})],
        initial_inputs={"кінцевик_відкр": False, "аварія": False},
    )
    assert result.final_state == "ВІДКРИВАЄТЬСЯ"
