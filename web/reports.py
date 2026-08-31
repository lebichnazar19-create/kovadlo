"""
Текстові звіти для вкладок модуля 9 (освітлення/вентиляція/тепло/пожежна
безпека).

У ядрі (модуль 8) немає готових `format_*_report` функцій, як у модулях
2 і 4 — лише розрахункові дата-класи. Ці звіти складено тут, у шарі
візуалізації (`web/`), з тих самих об'єктів ядра, без зміни модуля 8.
"""

from __future__ import annotations

import math

from kovadlo import (
    ClimateZone,
    DESIGN_OUTDOOR_TEMP_C,
    DetectorKind,
    Duct,
    FireDetector,
    LightFixture,
    Room,
    RoomPurpose,
    VentilatedRoomKind,
    WallLayer,
    condensation_risk_warnings,
    illuminance_lux,
    layer_interface_temperatures_c,
    required_luminous_flux_lm,
    wall_thermal_resistance_m2k_w,
    wall_u_value_w_m2k,
)
from kovadlo.fire_safety_norms import COVERAGE_AREA_M2
from kovadlo.insulation import WT2021_MAX_U_WALL_W_M2K
from kovadlo.lighting_norms import RECOMMENDED_LUX


def format_lighting_report(
    room: Room,
    purpose: RoomPurpose,
    fixtures: list[LightFixture],
    *,
    utilization_factor: float,
    maintenance_factor: float,
) -> str:
    target_lux = RECOMMENDED_LUX[purpose]
    total_flux = sum(f.luminous_flux_lm for f in fixtures)
    achieved = illuminance_lux(total_flux, room.floor_area_m2, utilization_factor=utilization_factor, maintenance_factor=maintenance_factor) if total_flux > 0 else 0.0
    meets = achieved >= target_lux

    lines = [
        f"Освітлення — {room.name or 'кімната'}",
        f"Призначення: {purpose.value}, норма {target_lux:.0f} лк",
        "",
        f"Світильники ({len(fixtures)}):",
    ]
    for fixture in fixtures:
        lines.append(f"  - {fixture.name} ({fixture.kind.value}): {fixture.luminous_flux_lm:.0f} лм, {fixture.power_w:.0f} Вт")

    lines += [
        "",
        f"Сумарний потік: {total_flux:.0f} лм",
        f"Розрахована освітленість: {achieved:.0f} лк",
        f"Норма виконана: {'так' if meets else 'ні'}",
    ]
    if not meets:
        deficit_flux = required_luminous_flux_lm(
            target_lux, room.floor_area_m2, utilization_factor=utilization_factor, maintenance_factor=maintenance_factor
        ) - total_flux
        note = f"Потрібно ще ≈{deficit_flux:.0f} лм світлового потоку"
        if fixtures:
            avg_flux = total_flux / len(fixtures)
            if avg_flux > 0:
                note += f" (~{math.ceil(deficit_flux / avg_flux)} світильників, як уже розміщені)"
        lines.append(note)
    lines.append(f"Сумарна потужність: {sum(f.power_w for f in fixtures):.0f} Вт")
    return "\n".join(lines)


def format_ventilation_report(
    room: Room,
    room_kind: VentilatedRoomKind,
    required_airflow_m3_h: float,
    ducts: list[tuple[str, Duct, float, float]],  # (name, duct, velocity_m_s, pressure_loss_pa)
    fan: tuple[str, float, float] | None,
) -> str:
    lines = [
        f"Вентиляція — {room.name or 'кімната'}",
        f"Призначення: {room_kind.value}",
        f"Потрібний повітрообмін: {required_airflow_m3_h:.0f} м³/год",
        "",
        f"Повітропроводи ({len(ducts)}):",
    ]
    total_dp = 0.0
    for name, duct, velocity, dp in ducts:
        size = f"⌀{duct.diameter_mm:.0f} мм" if duct.diameter_mm else f"{duct.width_mm:.0f}×{duct.height_mm:.0f} мм"
        lines.append(
            f"  - {name}: {duct.shape.value}, {size}, довжина {duct.length_m:.2f} м, "
            f"швидкість {velocity:.2f} м/с, втрати тиску {dp:.1f} Па"
        )
        total_dp += dp

    lines.append("")
    lines.append(f"Сумарні втрати тиску: {total_dp:.1f} Па")
    if fan:
        name, max_flow, max_pressure = fan
        lines.append(f"Підібраний вентилятор: {name} (до {max_flow:.0f} м³/год, до {max_pressure:.0f} Па)")
    else:
        lines.append("Вентилятор не підібрано (немає повітропроводів або немає відповідного в каталозі)")
    return "\n".join(lines)


def format_heat_report(
    room: Room,
    wall_data: list[tuple[int, list[WallLayer], float, float]],  # (wall_index, layers, indoor_temp_c, indoor_rh)
    climate_zone: ClimateZone,
) -> str:
    outdoor_temp = DESIGN_OUTDOOR_TEMP_C[climate_zone]
    lines = [f"Тепло — {room.name or 'кімната'}", f"Кліматична зона: {climate_zone.value} (розрахункова {outdoor_temp:.0f}°C)", ""]

    if not wall_data:
        lines.append("Жодна стіна ще не має заданої конструкції шарів.")
        return "\n".join(lines)

    for wall_index, layers, indoor_temp, indoor_rh in wall_data:
        wall = room.walls[wall_index]
        r_total = wall_thermal_resistance_m2k_w(layers)
        u_value = wall_u_value_w_m2k(layers)
        meets = u_value <= WT2021_MAX_U_WALL_W_M2K + 1e-9
        delta_t = indoor_temp - outdoor_temp
        heat_loss_w = wall.area_m2 * u_value * delta_t

        lines.append(f"Стіна {wall_index + 1} ({wall.length_mm:.0f}×{wall.height:.0f} мм, {wall.area_m2:.2f} м²):")
        lines.append("  Шари (від приміщення назовні):")
        for i, layer in enumerate(layers, start=1):
            lines.append(
                f"    {i}. {layer.material.name}, {layer.thickness_m * 1000:.0f} мм "
                f"(λ={layer.material.thermal_conductivity_w_mk:g} Вт/(м·К))"
            )
        lines.append(f"  Опір теплопередачі R: {r_total:.3f} м²·К/Вт")
        lines.append(f"  Коефіцієнт теплопередачі U: {u_value:.3f} Вт/(м²·К)")
        lines.append(
            f"  Норма WT2021: ≤{WT2021_MAX_U_WALL_W_M2K:.2f} Вт/(м²·К) — "
            f"{'відповідає' if meets else 'НЕ відповідає'}"
        )
        lines.append(f"  Тепловтрати через стіну: {heat_loss_w:.0f} Вт (ΔT={delta_t:.0f} К)")

        warnings = condensation_risk_warnings(layers, indoor_temp, indoor_rh, outdoor_temp)
        if warnings:
            lines.append("  Ризик конденсату:")
            for warning in warnings:
                lines.append(f"    - {warning}")
        else:
            lines.append("  Ризик конденсату: не виявлено")
        lines.append("")

    return "\n".join(lines).rstrip()


def format_fire_report(room: Room, detector_kind: DetectorKind, detectors: list[FireDetector], loop_length_m: float | None) -> str:
    radius_m = math.sqrt(COVERAGE_AREA_M2[detector_kind] / math.pi)
    lines = [
        f"Пожежна безпека — {room.name or 'кімната'}",
        f"Тип датчика: {detector_kind.value}",
        "",
        f"Датчики ({len(detectors)}), орієнтовний радіус покриття ~{radius_m:.1f} м:",
    ]
    for detector in detectors:
        lines.append(f"  - {detector.name}: ({detector.position.x:.0f}, {detector.position.z:.0f}) мм")

    lines.append("")
    if loop_length_m is not None:
        lines.append(f"Довжина шлейфу (щиток → датчики → щиток): {loop_length_m:.2f} м")
    else:
        lines.append("Довжина шлейфу: невідома (поставте щиток на вкладці «Електрика»)")
    return "\n".join(lines)
