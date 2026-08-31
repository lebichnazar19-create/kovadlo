"""Текстові звіти модуля 12 (механіка та фізика руху) — без графіки."""

from __future__ import annotations

from .beam import Beam, BeamCheckResult, Structure
from .motor import Motor, current_under_load_a, heat_dissipation_w, power_input_w
from .transmission import Transmission, power_w


def format_beam_report(beam: Beam, result: BeamCheckResult) -> str:
    """Звіт по одній балці: геометрія, навантаження, згин, прогин,
    перевірка міцності з коефіцієнтом запасу."""
    name = beam.name or "балка"
    lines = [
        f"Балка «{name}» — профіль {beam.profile.name}, матеріал {beam.material.name}",
        f"  Довжина:                  {beam.length_mm / 1000:.3f} м",
        f"  Кут до горизонталі:       {beam.angle_to_horizontal_deg:.1f}°",
        f"  Кут до вертикалі:         {beam.angle_to_vertical_deg:.1f}°",
    ]
    if beam.material.density_kg_m3 is not None:
        lines.append(f"  Вага:                     {beam.weight_kg:.2f} кг ({beam.weight_n:.1f} Н)")
    lines += [
        "",
        f"  Схема навантаження:       {result.scheme.value}",
        f"  Навантаження:             {result.load_n:.0f} Н",
        f"  Максимальний момент:      {result.moment_max_nmm / 1000:.2f} Н·м",
        f"  Напруження на згин:       {result.stress_mpa:.1f} МПа (допустимо ≤ {result.allowable_stress_mpa:.1f} МПа)",
        f"  Коефіцієнт запасу (факт): {result.safety_margin:.2f}",
        (
            f"  Прогин:                   {result.deflection_mm:.2f} мм "
            f"(допустимо ≤ {result.deflection_limit_mm:.2f} мм)"
        ),
        f"  Міцність:                 {'ПРОХОДИТЬ' if result.passes_strength else 'НЕ ПРОХОДИТЬ'}",
        f"  Прогин:                   {'ПРОХОДИТЬ' if result.passes_deflection else 'НЕ ПРОХОДИТЬ'}",
    ]
    return "\n".join(lines)


def format_structure_report(structure: Structure, results: dict[str, BeamCheckResult]) -> str:
    """Зведений звіт по всій конструкції: кожна балка + сумарна вага."""
    lines: list[str] = []
    for name, beam in structure.beams.items():
        result = results.get(name)
        if result is not None:
            lines.append(format_beam_report(beam, result))
        else:
            lines.append(f"Балка «{name}» — профіль {beam.profile.name}, матеріал {beam.material.name} (без перевірки навантаження)")
        lines.append("")

    lines.append(f"Разом балок:              {len(structure.beams)}")
    lines.append(f"Сумарна вага конструкції: {structure.total_weight_kg:.2f} кг ({structure.total_weight_n:.1f} Н)")
    failing = [name for name, result in results.items() if not result.passes]
    if failing:
        lines.append(f"Не проходять перевірку:   {', '.join(failing)}")
    else:
        lines.append("Усі перевірені балки проходять за міцністю й прогином.")
    return "\n".join(lines)


def format_drive_report(
    motor: Motor,
    transmission: Transmission,
    input_rpm: float,
    load_torque_output_nm: float,
) -> str:
    """Звіт приводу: двигун + передача, кінцеві оберти/момент на
    виході, споживаний струм і тепловиділення двигуна.

    `load_torque_output_nm` — момент опору на ВИХІДНОМУ валу передачі
    (те, що треба подолати робочому органу); вхідний момент двигуна
    відновлюється як зворотна задача через передатне число й ККД.
    """
    from .transmission import rpm_to_rad_s

    output_rpm = transmission.output_rpm(input_rpm)
    input_torque_nm = load_torque_output_nm / (transmission.ratio() * transmission.efficiency)
    current_a = current_under_load_a(motor, input_torque_nm)
    power_in = power_input_w(motor, current_a)
    input_omega = rpm_to_rad_s(input_rpm)
    output_omega = rpm_to_rad_s(output_rpm)
    power_out_shaft = power_w(load_torque_output_nm, output_omega)
    heat = heat_dissipation_w(motor, current_a, torque_nm=input_torque_nm, angular_velocity_rad_s=input_omega)

    lines = [
        f"Двигун «{motor.name}» ({motor.kind.value}), {motor.voltage_v:.0f} В",
        f"  Обороти на валу двигуна:     {input_rpm:.0f} об/хв",
        f"  Момент на валу двигуна:      {input_torque_nm:.3f} Н·м",
        f"  Споживаний струм:            {current_a:.2f} А",
        f"  Споживана потужність:        {power_in:.1f} Вт",
        f"  Тепловиділення:              {heat:.1f} Вт",
        "",
        f"Передача: {type(transmission).__name__}, i = {transmission.ratio():.3f}, ККД = {transmission.efficiency:.2f}",
        f"  Обороти на виході:           {output_rpm:.0f} об/хв",
        f"  Момент на виході:            {load_torque_output_nm:.3f} Н·м",
        f"  Механічна потужність виходу: {power_out_shaft:.1f} Вт",
    ]
    return "\n".join(lines)
