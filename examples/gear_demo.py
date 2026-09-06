"""
Приклад: зубчасте зачеплення (модуль 12, `kovadlo/transmission.py`) —
двоступеневий редуктор з двох пар циліндричних коліс зовнішнього
зачеплення.

  - ступінь 1: z=20 -> z=60, модуль 2 мм
  - ступінь 2: z=20 -> z=40, модуль 3 мм

Вхід — 1500 об/хв на веденче колесо першої ступені. Кожне зовнішнє
зачеплення реверсує напрям обертання (`GearMesh.output_rpm` — зі
знаком), тому після ДВОХ ступенів напрям на виході знову збігається зі
вхідним — саме так рахує `GearTrain`, послідовно застосовуючи кожен
реверс, а не діленням на сумарне передатне число напряму.

Лише розрахунок і текстовий вивід — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.gear_demo
"""

from __future__ import annotations

from kovadlo import Gear, GearMesh, GearTrain

INPUT_RPM = 1500.0


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def print_stage(title: str, mesh: GearMesh, input_rpm: float) -> float:
    section(title)
    print(
        f"Колесо A: z={mesh.gear_a.teeth}, модуль={mesh.gear_a.module_mm:.0f} мм — "
        f"ділильний ⌀{mesh.gear_a.pitch_diameter_mm:.1f} мм, зовнішній ⌀{mesh.gear_a.outer_diameter_mm:.1f} мм"
    )
    print(
        f"Колесо B: z={mesh.gear_b.teeth}, модуль={mesh.gear_b.module_mm:.0f} мм — "
        f"ділильний ⌀{mesh.gear_b.pitch_diameter_mm:.1f} мм, зовнішній ⌀{mesh.gear_b.outer_diameter_mm:.1f} мм"
    )
    print(f"Міжосьова відстань: {mesh.center_distance_mm:.1f} мм")
    print(f"Передатне число: {mesh.ratio:.2f}")

    output_rpm = mesh.output_rpm(input_rpm)
    direction = "той самий напрям" if output_rpm * input_rpm > 0 else "напрям реверсовано"
    print(f"Вхід: {input_rpm:.1f} об/хв -> вихід: {output_rpm:.1f} об/хв ({direction})")
    return output_rpm


def main() -> None:
    stage1 = GearMesh(Gear(module_mm=2, teeth=20, width_mm=15), Gear(module_mm=2, teeth=60, width_mm=15))
    stage2 = GearMesh(Gear(module_mm=3, teeth=20, width_mm=20), Gear(module_mm=3, teeth=40, width_mm=20))
    train = GearTrain([stage1, stage2])

    rpm_after_stage1 = print_stage("Ступінь 1 (z=20 -> z=60, m=2)", stage1, INPUT_RPM)
    rpm_after_stage2 = print_stage("Ступінь 2 (z=20 -> z=40, m=3)", stage2, rpm_after_stage1)

    section("Разом")
    print(f"Сумарне передатне число: {train.total_ratio:.2f}")
    output_rpm = train.output_rpm(INPUT_RPM)
    direction = "той самий напрям, що й вхід" if output_rpm * INPUT_RPM > 0 else "напрям реверсовано відносно входу"
    print(f"Вхід: {INPUT_RPM:.1f} об/хв -> вихід усього ланцюга: {output_rpm:.1f} об/хв ({direction})")


if __name__ == "__main__":
    main()
