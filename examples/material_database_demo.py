"""
Приклад: база матеріалів (модуль 7) — наскрізне використання іншими модулями.

Показує:
  - пошук/фільтр за властивостями;
  - підбір під задачу з обґрунтуванням (клей для балкона);
  - порівняння двох матеріалів за ціною для однакової теплотехнічної задачі;
  - прив'язку до стіни (модуль 1) через `to_core_material()` і пошук
    повного запису назад за іменем — саме так реалізовано "посилання на
    базу" без зміни ядра;
  - опір мідної доріжки (для модуля 6) через дані бази, а не хардкод.

Лише розрахунок і текстовий вивід — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.material_database_demo
"""

from __future__ import annotations

from kovadlo import (
    Point,
    Room,
    build_default_database,
    compare_for_thermal_resistance,
    conductor_resistance_ohm,
    select_tile_adhesive_for_balcony,
)
from kovadlo.pcb_norms import track_resistance_ohm


def main() -> None:
    db = build_default_database()
    print(f"У базі {len(db.materials)} матеріалів у {len({m.category for m in db.materials})} категоріях.\n")

    # --- пошук і фільтр ----------------------------------------------------
    print("Утеплювачі з теплопровідністю < 0.03 Вт/(м·К):")
    for m in db.where_thermal_conductivity_below(0.03):
        print(f"  - {m.summary_line()}: λ={m.thermal_conductivity_w_mk:g} Вт/(м·К)")
    print()

    print("Морозостійкі матеріали:")
    for m in db.where_frost_resistant():
        print(f"  - {m.name}")
    print()

    # --- підбір під задачу: клей для балкона --------------------------------
    print("Підбір клею для плитки на балконі (вулиця, морозостійкий, водостійкий):")
    for result in select_tile_adhesive_for_balcony(db):
        print(f"  - {result}")
    print()

    # --- порівняння: утеплення стіни, R = 2.5 м²·К/Вт -----------------------
    wool = db.find_by_name("Мінеральна вата (кам'яна)")
    xps = db.find_by_name("XPS (екструдований пінополістирол)")
    comparison = compare_for_thermal_resistance(wool, xps, required_resistance_m2k_w=2.5)
    print("Порівняння утеплювачів для стіни (R = 2.5 м²·К/Вт):")
    print(comparison)
    print()

    # --- прив'язка до стіни (модуль 1) -------------------------------------
    concrete = db.find_by_name("Бетон C25/30")
    wall_material = concrete.to_core_material()  # саме це передається у Wall/Room
    room = Room.from_contour(
        [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)],
        height=2700,
        thickness=200,
        material=wall_material,
    )
    print(f"Стіна побудована з матеріалу «{room.walls[0].material.name}» (з модуля 1).")
    looked_up = db.find_by_name(room.walls[0].material.name)
    print(
        f"Повний запис бази знайдено назад за іменем: "
        f"міцність на стиск {looked_up.compressive_strength_mpa:g} МПа, "
        f"джерело: {looked_up.source_note}"
    )
    print()

    # --- опір мідної доріжки для модуля 6 -----------------------------------
    copper = db.find_by_name("Мідь (провідникова, відпалена)")
    r_from_db = conductor_resistance_ohm(copper, length_m=0.1, cross_section_mm2=0.5 * 0.035)
    r_from_pcb_module = track_resistance_ohm(length_mm=100, width_mm=0.5)
    print("Опір мідної доріжки 100×0.5×0.035 мм:")
    print(f"  за питомим опором з бази матеріалів: {r_from_db * 1000:.1f} мОм")
    print(f"  за внутрішньою константою модуля 6 (із запасом на нагрів): {r_from_pcb_module * 1000:.1f} мОм")


if __name__ == "__main__":
    main()
