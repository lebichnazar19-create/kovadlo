"""Тести прикладу «Автоматична брама» (модуль 13) — повний цикл.

Ключове число з завдання — "час циклу" (скільки секунд відкривається
брама) — перевірене вручну в `test_gate_cycle_time_hand_verified`.
"""

import math

import pytest

from kovadlo.automation_logic import find_dead_end_states, find_forbidden_rule_violations
from kovadlo.automation_sim import SimulationStep, run_scenario
from kovadlo.gate_automation import build_gate_scenario, gate_cycle_time_s, recommended_timeout_s
from kovadlo.transmission import GearboxTransmission, rpm_to_rad_s
from kovadlo.kinematics import wheel_linear_speed_m_s


def test_gate_cycle_time_hand_verified():
    # Редуктор i=30, вхід 3000 об/хв -> вихід 100 об/хв.
    # ω = 100·2π/60 = 10.4720 рад/с; колесо d=60мм (r=0.03м):
    # v = ω·r = 0.31416 м/с; час ходу 3000мм = 3.0/0.31416 = 9.5493 с
    gearbox = GearboxTransmission(gear_ratio=30, efficiency=0.9)
    output_rpm = gearbox.output_rpm(3000.0)
    omega = rpm_to_rad_s(output_rpm)
    speed = wheel_linear_speed_m_s(60.0, omega)
    expected = 3000.0 / 1000.0 / speed

    actual = gate_cycle_time_s(3000.0, 3000.0, gearbox, 60.0)
    assert actual == pytest.approx(expected)
    assert actual == pytest.approx(9.549296585513721, rel=1e-9)


def test_gate_cycle_time_rejects_bad_inputs():
    gearbox = GearboxTransmission(gear_ratio=30, efficiency=0.9)
    with pytest.raises(ValueError):
        gate_cycle_time_s(0.0, 3000.0, gearbox, 60.0)
    with pytest.raises(ValueError):
        gate_cycle_time_s(3000.0, 0.0, gearbox, 60.0)


def test_recommended_timeout_hand_verified():
    assert recommended_timeout_s(9.5493, margin_s=5.0) == pytest.approx(14.5493)


def test_recommended_timeout_rejects_bad_inputs():
    with pytest.raises(ValueError):
        recommended_timeout_s(0.0)
    with pytest.raises(ValueError):
        recommended_timeout_s(10.0, margin_s=-1.0)


def test_build_gate_scenario_controller_passes_check():
    # Двигун під'єднаний через контактори (малий струм котушки), а не
    # напряму — контролер має проходити перевірку струму й напруги.
    system = build_gate_scenario()
    result = system.controller.check()
    assert result.passes is True


def test_build_gate_scenario_has_no_dead_ends():
    system = build_gate_scenario()
    assert find_dead_end_states(system.scenario) == set()


def test_build_gate_scenario_has_no_forbidden_violations():
    system = build_gate_scenario()
    assert find_forbidden_rule_violations(system.scenario) == []


def test_gate_full_cycle_open_hand_verified():
    system = build_gate_scenario()
    steps = [
        SimulationStep(0.0, {
            "кнопка": False, "кінцевик_відкрито": False, "кінцевик_закрито": True,
            "фотобар'єр_перекрито": False, "скидання": False,
        }),
        SimulationStep(1.0, {"кнопка": True}),
        SimulationStep(1.5, {"кнопка": False, "кінцевик_закрито": False}),
        SimulationStep(1.5 + system.cycle_time_s, {"кінцевик_відкрито": True}),
    ]
    result = run_scenario(system.scenario, steps)

    assert [entry.state for entry in result.log] == ["ЗАКРИТО", "ВІДКРИВАЄТЬСЯ", "ВІДКРИВАЄТЬСЯ", "ВІДКРИТО"]
    assert result.log[1].outputs["двигун_вперед"] is True
    assert result.log[-1].outputs["двигун_вперед"] is False
    assert result.final_state == "ВІДКРИТО"


def test_gate_full_cycle_open_then_close_hand_verified():
    system = build_gate_scenario()
    t_open_done = 1.5 + system.cycle_time_s
    steps = [
        SimulationStep(0.0, {
            "кнопка": False, "кінцевик_відкрито": False, "кінцевик_закрито": True,
            "фотобар'єр_перекрито": False, "скидання": False,
        }),
        SimulationStep(1.0, {"кнопка": True}),
        SimulationStep(1.5, {"кнопка": False, "кінцевик_закрито": False}),
        SimulationStep(t_open_done, {"кінцевик_відкрито": True}),
        SimulationStep(t_open_done + 2.0, {"кнопка": True}),
        SimulationStep(t_open_done + 2.5, {"кнопка": False, "кінцевик_відкрито": False}),
        SimulationStep(t_open_done + 2.5 + system.cycle_time_s, {"кінцевик_закрито": True}),
    ]
    result = run_scenario(system.scenario, steps)
    assert result.final_state == "ЗАКРИТО"
    assert result.reached_state("ВІДКРИТО") is True
    assert result.reached_state("ЗАКРИВАЄТЬСЯ") is True


def test_gate_photobeam_reverses_while_closing():
    # Фотобар'єр перекритий під час закривання -> безпечний реверс
    # (назад у ВІДКРИВАЄТЬСЯ), а не аварія й не продовження закриття.
    # Спочатку повністю відкриваємо (фізично коректна послідовність:
    # кожен кінцевик очищається, щойно полотно залишає його позицію),
    # і лише потім починаємо закриття, яке перериває фотобар'єр.
    system = build_gate_scenario()
    t_open_done = 1.5 + system.cycle_time_s
    steps = [
        SimulationStep(0.0, {
            "кнопка": False, "кінцевик_відкрито": False, "кінцевик_закрито": True,
            "фотобар'єр_перекрито": False, "скидання": False,
        }),
        SimulationStep(1.0, {"кнопка": True}),
        SimulationStep(1.5, {"кнопка": False, "кінцевик_закрито": False}),
        SimulationStep(t_open_done, {"кінцевик_відкрито": True}),
        SimulationStep(t_open_done + 1.0, {"кнопка": True}),
        SimulationStep(t_open_done + 1.5, {"кнопка": False, "кінцевик_відкрито": False}),
        SimulationStep(t_open_done + 2.0, {"фотобар'єр_перекрито": True}),
    ]
    result = run_scenario(system.scenario, steps)
    assert result.log[-2].state == "ЗАКРИВАЄТЬСЯ"  # дійсно почало закриватися перед перериванням
    assert result.log[-1].state == "ВІДКРИВАЄТЬСЯ"
    assert result.log[-1].outputs["двигун_назад"] is False
    assert result.log[-1].outputs["двигун_вперед"] is True
    assert result.reached_state("АВАРІЯ") is False


def test_gate_timeout_triggers_alarm():
    system = build_gate_scenario()
    steps = [
        SimulationStep(0.0, {
            "кнопка": False, "кінцевик_відкрито": False, "кінцевик_закрито": True,
            "фотобар'єр_перекрито": False, "скидання": False,
        }),
        SimulationStep(1.0, {"кнопка": True}),
        SimulationStep(1.5, {"кнопка": False, "кінцевик_закрито": False}),
        # кінцевик відкриття НІКОЛИ не спрацьовує (заклинило) -> таймаут
        SimulationStep(1.5 + system.timeout_s + 0.1, {}),
    ]
    result = run_scenario(system.scenario, steps)
    assert result.final_state == "АВАРІЯ"
    assert result.log[-1].outputs["двигун_вперед"] is False


def test_gate_reset_after_alarm_returns_to_closed():
    system = build_gate_scenario()
    steps = [
        SimulationStep(0.0, {
            "кнопка": False, "кінцевик_відкрито": False, "кінцевик_закрито": True,
            "фотобар'єр_перекрито": False, "скидання": False,
        }),
        SimulationStep(1.0, {"кнопка": True}),
        SimulationStep(1.5, {"кнопка": False, "кінцевик_закрито": False}),
        SimulationStep(1.5 + system.timeout_s + 0.1, {}),
        SimulationStep(1.5 + system.timeout_s + 1.0, {"скидання": True}),
    ]
    result = run_scenario(system.scenario, steps)
    assert result.log[-2].state == "АВАРІЯ"
    assert result.final_state == "ЗАКРИТО"


def test_gate_forbidden_transition_blocks_direct_alarm_to_moving():
    system = build_gate_scenario()
    assert ("АВАРІЯ", "ВІДКРИВАЄТЬСЯ") in system.scenario.forbidden_transitions
    assert ("АВАРІЯ", "ЗАКРИВАЄТЬСЯ") in system.scenario.forbidden_transitions
