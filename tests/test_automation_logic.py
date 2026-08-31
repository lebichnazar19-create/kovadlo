"""Тести рушія логіки керування модуля 13 — правила, стани, таймери,
блокування, глухі кути.

Ключове число з завдання — "перехід станів" — перевірене вручну в
`test_apply_step_state_transition_hand_verified`.
"""

import pytest

from kovadlo.automation_logic import (
    Action,
    Condition,
    MachineState,
    Rule,
    Scenario,
    TimerSpec,
    apply_step,
    expired_timers,
    find_dead_end_states,
    find_forbidden_rule_violations,
)


def _gate_scenario(**overrides) -> Scenario:
    states = {"ЗАКРИТО", "ВІДКРИВАЄТЬСЯ", "ВІДКРИТО", "ЗАКРИВАЄТЬСЯ", "АВАРІЯ"}
    rules = [
        Rule(
            "Аварійний стоп",
            Condition(inputs={"аварія": True}),
            Action(new_state="АВАРІЯ", outputs={"двигун_вперед": False, "двигун_назад": False}),
        ),
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
        Rule(
            "Таймаут відкриття",
            Condition(state_in="ВІДКРИВАЄТЬСЯ", timer_expired="таймаут"),
            Action(new_state="АВАРІЯ", outputs={"двигун_вперед": False}),
        ),
    ]
    params = dict(
        name="Брама",
        states=states,
        initial_state="ЗАКРИТО",
        rules=rules,
        timers={"таймаут": TimerSpec("таймаут", duration_s=10.0)},
        forbidden_transitions={("АВАРІЯ", "ВІДКРИВАЄТЬСЯ")},
    )
    params.update(overrides)
    return Scenario(**params)


def test_condition_matches_state_and_inputs():
    cond = Condition(state_in="ЗАКРИТО", inputs={"кнопка": True})
    assert cond.matches("ЗАКРИТО", {"кнопка": True}, set()) is True
    assert cond.matches("ВІДКРИТО", {"кнопка": True}, set()) is False
    assert cond.matches("ЗАКРИТО", {"кнопка": False}, set()) is False


def test_condition_wildcard_state_matches_any():
    cond = Condition(inputs={"аварія": True})
    assert cond.matches("ЗАКРИТО", {"аварія": True}, set()) is True
    assert cond.matches("ВІДКРИТО", {"аварія": True}, set()) is True


def test_condition_timer_expired():
    cond = Condition(state_in="ВІДКРИВАЄТЬСЯ", timer_expired="таймаут")
    assert cond.matches("ВІДКРИВАЄТЬСЯ", {}, {"таймаут"}) is True
    assert cond.matches("ВІДКРИВАЄТЬСЯ", {}, set()) is False


def test_timer_spec_rejects_non_positive_duration():
    with pytest.raises(ValueError):
        TimerSpec("x", duration_s=0.0)


def test_scenario_rejects_unknown_initial_state():
    with pytest.raises(ValueError):
        Scenario(name="x", states={"A", "B"}, initial_state="C")


def test_scenario_rejects_rule_referencing_unknown_state():
    with pytest.raises(ValueError):
        Scenario(
            name="x", states={"A", "B"}, initial_state="A",
            rules=[Rule("r", Condition(state_in="C"), Action())],
        )


def test_scenario_rejects_rule_referencing_unknown_timer():
    with pytest.raises(ValueError):
        Scenario(
            name="x", states={"A", "B"}, initial_state="A",
            rules=[Rule("r", Condition(state_in="A", timer_expired="немає"), Action())],
        )


def test_scenario_rejects_forbidden_transition_with_unknown_state():
    with pytest.raises(ValueError):
        Scenario(name="x", states={"A", "B"}, initial_state="A", forbidden_transitions={("A", "C")})


def test_apply_step_no_match_returns_empty_and_keeps_state():
    scenario = _gate_scenario()
    ms = MachineState(state="ЗАКРИТО", input_values={"кнопка": False, "кінцевик_відкр": False, "аварія": False})
    fired = apply_step(scenario, ms, 0.0)
    assert fired == []
    assert ms.state == "ЗАКРИТО"


def test_apply_step_state_transition_hand_verified():
    # У стані ЗАКРИТО, кнопка натиснута -> спрацьовує "Старт відкриття":
    # новий стан ВІДКРИВАЄТЬСЯ, вихід двигун_вперед=True, таймер стартує.
    scenario = _gate_scenario()
    ms = MachineState(state="ЗАКРИТО", input_values={"кнопка": True, "кінцевик_відкр": False, "аварія": False})
    fired = apply_step(scenario, ms, 1.0)

    assert [r.name for r in fired] == ["Старт відкриття"]
    assert ms.state == "ВІДКРИВАЄТЬСЯ"
    assert ms.output_values["двигун_вперед"] is True
    assert ms.timer_started_at["таймаут"] == pytest.approx(1.0)


def test_apply_step_chains_multiple_rules_same_timestamp():
    # Аварія одразу перекриває "Старт відкриття", навіть якщо обидві
    # умови виконуються одночасно (аварійне правило — перше в списку).
    scenario = _gate_scenario()
    ms = MachineState(state="ЗАКРИТО", input_values={"кнопка": True, "кінцевик_відкр": False, "аварія": True})
    fired = apply_step(scenario, ms, 0.0)
    assert [r.name for r in fired] == ["Аварійний стоп"]
    assert ms.state == "АВАРІЯ"


def test_apply_step_stops_timer_on_completion():
    scenario = _gate_scenario()
    ms = MachineState(state="ЗАКРИТО", input_values={"кнопка": True, "кінцевик_відкр": False, "аварія": False})
    apply_step(scenario, ms, 0.0)
    assert "таймаут" in ms.timer_started_at

    ms.input_values["кнопка"] = False
    ms.input_values["кінцевик_відкр"] = True
    apply_step(scenario, ms, 3.0)
    assert ms.state == "ВІДКРИТО"
    assert "таймаут" not in ms.timer_started_at


def test_apply_step_timeout_triggers_alarm_hand_verified():
    # Таймер стартує о t=0 (тривалість 10с) -> сплив, коли t-started>=10.
    scenario = _gate_scenario()
    ms = MachineState(state="ЗАКРИТО", input_values={"кнопка": True, "кінцевик_відкр": False, "аварія": False})
    apply_step(scenario, ms, 0.0)
    ms.input_values["кнопка"] = False

    assert expired_timers(scenario, ms, 9.9) == set()
    assert expired_timers(scenario, ms, 10.0) == {"таймаут"}

    fired = apply_step(scenario, ms, 10.0)
    assert [r.name for r in fired] == ["Таймаут відкриття"]
    assert ms.state == "АВАРІЯ"


def test_apply_step_raises_on_forbidden_transition():
    scenario = Scenario(
        name="x", states={"АВАРІЯ", "ВІДКРИВАЄТЬСЯ"}, initial_state="АВАРІЯ",
        rules=[Rule("bad", Condition(state_in="АВАРІЯ"), Action(new_state="ВІДКРИВАЄТЬСЯ"))],
        forbidden_transitions={("АВАРІЯ", "ВІДКРИВАЄТЬСЯ")},
    )
    ms = MachineState(state="АВАРІЯ", input_values={})
    with pytest.raises(RuntimeError):
        apply_step(scenario, ms, 0.0)


def test_apply_step_terminates_with_oscillating_rules_without_error():
    # Кожне правило спрацьовує щонайбільше раз за виклик apply_step —
    # тож навіть таке "пінг-понг" визначення станів не зациклюється
    # нескінченно: a_to_b спрацьовує (A->B), потім b_to_a (B->A), потім
    # a_to_b вже використане цього кроку -> крок завершується.
    scenario = Scenario(
        name="x", states={"A", "B"}, initial_state="A",
        rules=[
            Rule("a_to_b", Condition(state_in="A"), Action(new_state="B")),
            Rule("b_to_a", Condition(state_in="B"), Action(new_state="A")),
        ],
    )
    ms = MachineState(state="A", input_values={})
    fired = apply_step(scenario, ms, 0.0)
    assert [r.name for r in fired] == ["a_to_b", "b_to_a"]
    assert ms.state == "A"


def test_find_dead_end_states_hand_verified():
    # У цьому (навмисно неповному) сценарії немає правила, що виводить
    # з АВАРІЇ — єдиний "вихід" з будь-якого стану (аварійне правило)
    # веде САМЕ в АВАРІЮ, тож для неї самої це не вихід.
    scenario = _gate_scenario()
    assert find_dead_end_states(scenario) == {"АВАРІЯ"}


def test_find_dead_end_states_respects_terminal_states():
    scenario = _gate_scenario(terminal_states={"АВАРІЯ"})
    assert find_dead_end_states(scenario) == set()


def test_find_dead_end_states_empty_when_reset_rule_exists():
    scenario = _gate_scenario(
        rules=_gate_scenario().rules
        + [Rule("Скидання", Condition(state_in="АВАРІЯ", inputs={"скидання": True}), Action(new_state="ЗАКРИТО"))],
        timers={"таймаут": TimerSpec("таймаут", duration_s=10.0)},
    )
    assert find_dead_end_states(scenario) == set()


def test_find_forbidden_rule_violations_detects_bad_rule():
    scenario = Scenario(
        name="x", states={"АВАРІЯ", "ВІДКРИВАЄТЬСЯ"}, initial_state="АВАРІЯ",
        rules=[Rule("bad", Condition(state_in="АВАРІЯ"), Action(new_state="ВІДКРИВАЄТЬСЯ"))],
        forbidden_transitions={("АВАРІЯ", "ВІДКРИВАЄТЬСЯ")},
    )
    violations = find_forbidden_rule_violations(scenario)
    assert [r.name for r in violations] == ["bad"]


def test_find_forbidden_rule_violations_empty_for_gate_scenario():
    # У штатному сценарії брами жодне правило не намагається одразу
    # з АВАРІЇ перейти у ВІДКРИВАЄТЬСЯ.
    scenario = _gate_scenario()
    assert find_forbidden_rule_violations(scenario) == []
