"""
Приклад: інженерні системи будівлі (модуль 8) для однієї кімнати —
кухня 4×3 м, висота 2.7 м.

Показує всі п'ять підсистем і їхні зв'язки з ядром (модулі 1, 4, 7):
  8.1 освітлення — підбір світильників + групу в проводці модуля 4;
  8.2 вентиляція — повітрообмін, діаметр каналу, вентилятор;
  8.3 кліматизація — тепловий баланс (з урахуванням вентиляції 8.2) і
      підбір радіатора/кондиціонера;
  8.4 утеплення — товщина утеплювача до норми WT2021, ціна з модуля 7,
      перевірка точки роси (той самий шар стіни, що й у 8.3);
  8.5 пожежна безпека — автоматична розстановка датчиків по контуру
      кімнати (модуль 1) і довжина шлейфу.

Лише розрахунок і текстовий вивід — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.building_systems_demo
"""

from __future__ import annotations

import math

from kovadlo import (
    BuildingElement,
    ClimateZone,
    DESIGN_OUTDOOR_TEMP_C,
    DEFAULT_INDOOR_TEMP_C,
    DetectorKind,
    FixtureKind,
    HeatBalance,
    LightFixture,
    Material,
    Point,
    Room,
    WallLayer,
    auto_place_detectors,
    build_default_database,
    build_route,
    check_against_wt2021,
    condensation_risk_warnings,
    insulation_cost_per_m2,
    lighting_group,
    loop_length_m,
    plan_lighting,
    required_airflow_m3_h,
    required_insulation_thickness_m,
    select_ac_power_kw,
    select_fan,
    select_radiator_power_w,
    select_round_duct_diameter_mm,
    air_velocity_m_s,
    pressure_loss_pa,
    RoomPurpose,
    VentilatedRoomKind,
)
from kovadlo.ventilation import Duct, DuctShape

ROOM_HEIGHT_M = 2.7


def build_room() -> Room:
    return Room.from_contour(
        [Point(0, 0), Point(4000, 0), Point(4000, 3000), Point(0, 3000)],
        height=ROOM_HEIGHT_M * 1000,
        thickness=200,
        material=Material(name="цегла", density_kg_m3=1800),
        name="Кухня",
    )


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> None:
    room = build_room()
    area_m2 = room.floor_area_m2
    volume_m3 = area_m2 * ROOM_HEIGHT_M
    print(f"Кімната «{room.name}»: {area_m2:.1f} м², об'єм {volume_m3:.1f} м³")

    # --- 8.1 Освітлення ------------------------------------------------
    section("8.1 Освітлення")
    plan = plan_lighting(area_m2, RoomPurpose.KITCHEN, fixture_flux_lm=1500, fixture_power_w=15)
    print(f"Норма: {plan.target_lux:.0f} лк. Потрібно світильників: {plan.fixtures_count}")
    print(f"Досягнута освітленість: {plan.achieved_lux:.0f} лк (норма виконана: {plan.meets_target})")
    print(f"Сумарна потужність освітлення: {plan.total_power_w:.0f} Вт")

    fixtures = [
        LightFixture(f"Св{i + 1}", FixtureKind.CEILING, Point(500 + i * 1000, 1500), luminous_flux_lm=1500, power_w=15)
        for i in range(plan.fixtures_count)
    ]
    panel = Point(0, 0)
    routes = {f.name: build_route(panel, [f.position], snap=False) for f in fixtures}
    group = lighting_group(fixtures, routes)
    print(f"Група проводки «{group.name}» (модуль 4): {group.total_power_w:.0f} Вт, {group.design_current_a:.2f} А")

    # --- 8.2 Вентиляція --------------------------------------------------
    section("8.2 Вентиляція")
    airflow = required_airflow_m3_h(VentilatedRoomKind.KITCHEN, volume_m3)
    diameter_mm = select_round_duct_diameter_mm(airflow)
    duct = Duct(points=[Point(0, 0), Point(0, 5000), Point(5000, 5000)], shape=DuctShape.ROUND, diameter_mm=diameter_mm)
    velocity = air_velocity_m_s(airflow, duct.cross_section_area_m2())
    dp = pressure_loss_pa(duct, airflow)
    fan_name, fan_flow, fan_pressure = select_fan(airflow, dp)
    print(f"Потрібний повітрообмін: {airflow:.0f} м³/год")
    print(f"Діаметр каналу: {diameter_mm:.0f} мм, швидкість {velocity:.2f} м/с, втрати тиску {dp:.1f} Па")
    print(f"Вентилятор: {fan_name} (до {fan_flow:.0f} м³/год, до {fan_pressure:.0f} Па)")

    # --- 8.4 Утеплення (рахуємо перед 8.3, бо кліматизація його використовує) ---
    section("8.4 Утеплення")
    db = build_default_database()
    concrete = db.find_by_name("Бетон C25/30")
    wool = db.find_by_name("Мінеральна вата (кам'яна)")

    base_layers = [WallLayer(concrete, thickness_m=0.20)]
    needed_thickness_m = required_insulation_thickness_m(base_layers, wool)
    # округлюємо до практичного кроку 10 мм, з запасом
    wool_thickness_m = math.ceil(needed_thickness_m * 100) / 100
    wall_layers = base_layers + [WallLayer(wool, thickness_m=wool_thickness_m)]

    check = check_against_wt2021(wall_layers)
    cost = insulation_cost_per_m2(wool, wool_thickness_m)
    print(f"Потрібна товщина утеплювача: {needed_thickness_m * 1000:.0f} мм (беремо {wool_thickness_m * 1000:.0f} мм)")
    print(f"U стіни: {check.u_value_w_m2k:.3f} Вт/(м²·К), норма WT2021 ≤ {check.max_u_value_w_m2k:.2f} — відповідає: {check.meets_norm}")
    print(f"Орієнтовна ціна утеплювача: {cost:.2f} зл/м²")

    warnings = condensation_risk_warnings(
        wall_layers, indoor_temp_c=DEFAULT_INDOOR_TEMP_C, indoor_relative_humidity_percent=50.0, outdoor_temp_c=-20.0
    )
    print(f"Ризик конденсату: {'ЄСТЬ — ' + '; '.join(warnings) if warnings else 'не виявлено'}")

    # --- 8.3 Кліматизація --------------------------------------------------
    section("8.3 Кліматизація")
    exterior_wall = room.walls[0]  # умовно: лише перша стіна кімнати виходить на вулицю
    window_area_m2 = 1.5
    wall_area_m2 = exterior_wall.area_m2 - window_area_m2

    wall_element = BuildingElement("Зовнішня стіна", area_m2=wall_area_m2, u_value_w_m2k=check.u_value_w_m2k)
    window_element = BuildingElement("Вікно", area_m2=window_area_m2, u_value_w_m2k=1.1)

    delta_t = DEFAULT_INDOOR_TEMP_C - DESIGN_OUTDOOR_TEMP_C[ClimateZone.ZONE_III]
    balance = HeatBalance(elements=[wall_element, window_element], delta_t_k=delta_t, airflow_m3_h=airflow)

    print(f"Розрахункова різниця температур: {delta_t:.0f} К (зона {ClimateZone.ZONE_III.value})")
    print(f"Тепловтрати трансмісією: {balance.transmission_loss_w:.0f} Вт")
    print(f"Тепловтрати на вентиляцію: {balance.ventilation_loss_w:.0f} Вт")
    print(f"Разом потрібна потужність: {balance.total_loss_w:.0f} Вт")
    print(f"Підібраний радіатор: {select_radiator_power_w(balance.total_loss_w):.0f} Вт")
    print(f"Або кондиціонер: {select_ac_power_kw(balance.total_loss_w):.1f} кВт")

    # --- 8.5 Пожежна безпека --------------------------------------------------
    section("8.5 Пожежна безпека")
    detectors = auto_place_detectors(room, DetectorKind.SMOKE)
    print(f"Автоматично розставлено димових датчиків: {len(detectors)}")
    for detector in detectors:
        print(f"  - {detector.name}: ({detector.position.x:.0f}, {detector.position.z:.0f}) мм")
    loop = loop_length_m(panel, [d.position for d in detectors])
    print(f"Довжина шлейфу від щитка: {loop:.2f} м")


if __name__ == "__main__":
    main()
