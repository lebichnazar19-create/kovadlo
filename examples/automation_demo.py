"""
Приклад: керування та логіка / автоматика (модуль 13) — автоматична
розсувна брама: два кінцевики, кнопка, фотобар'єр безпеки, двигун через
редуктор.

Показує:
  - зібраний приклад `build_gate_scenario` (sensors, actuators, controller,
    automation_logic — модуль 13) з розрахованим часом циклу (модуль 12);
  - перевірку контролера (піни/напруга/струм);
  - перевірку сценарію на глухі кути й заборонені переходи;
  - повний прогін циклу відкриття-закриття по кроках у часі;
  - безпечний реверс при перекритті фотобар'єру під час закривання;
  - аварійний таймаут, коли кінцевик не спрацював.

Лише розрахунок і текстовий вивід — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.automation_demo
"""

from __future__ import annotations

from kovadlo import (
    SimulationStep,
    build_gate_scenario,
    format_gate_system_report,
    format_simulation_report,
    run_scenario,
)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> None:
    system = build_gate_scenario(travel_distance_mm=3000.0, motor_rpm=3000.0, gear_ratio=30.0, drive_wheel_diameter_mm=60.0)

    section("Контролер і сценарій")
    print(format_gate_system_report(system))

    # --- Повний цикл: закрито -> відкрито -----------------------------------
    section("Симуляція: повне відкриття")
    open_steps = [
        SimulationStep(0.0, {
            "кнопка": False, "кінцевик_відкрито": False, "кінцевик_закрито": True,
            "фотобар'єр_перекрито": False, "скидання": False,
        }),
        SimulationStep(1.0, {"кнопка": True}),
        SimulationStep(1.5, {"кнопка": False, "кінцевик_закрито": False}),
        SimulationStep(1.5 + system.cycle_time_s, {"кінцевик_відкрито": True}),
    ]
    open_result = run_scenario(system.scenario, open_steps)
    print(format_simulation_report(open_result))

    # --- Закриття перерване фотобар'єром -------------------------------------
    # Спочатку повністю відкриваємо (фізично коректна послідовність — кожен
    # кінцевик очищається, щойно полотно залишає його позицію), і лише
    # потім починаємо закриття, яке перериває фотобар'єр.
    section("Симуляція: закриття перерване фотобар'єром (безпечний реверс)")
    t_open_done = 1.5 + system.cycle_time_s
    close_steps = [
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
    beam_result = run_scenario(system.scenario, close_steps)
    print(format_simulation_report(beam_result))

    # --- Аварійний таймаут (кінцевик не спрацював) ---------------------------
    section("Симуляція: аварійний таймаут")
    timeout_steps = [
        SimulationStep(0.0, {
            "кнопка": False, "кінцевик_відкрито": False, "кінцевик_закрито": True,
            "фотобар'єр_перекрито": False, "скидання": False,
        }),
        SimulationStep(1.0, {"кнопка": True}),
        SimulationStep(1.5, {"кнопка": False, "кінцевик_закрито": False}),
        SimulationStep(1.5 + system.timeout_s + 0.1, {}),  # кінцевик так і не спрацював
    ]
    timeout_result = run_scenario(system.scenario, timeout_steps)
    print(format_simulation_report(timeout_result))


if __name__ == "__main__":
    main()
