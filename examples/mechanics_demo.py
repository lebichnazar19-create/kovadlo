"""
Приклад: механіка та фізика руху (модуль 12) — рама з металопрофілів і
привід невеликого моторизованого візка (двигун -> редуктор -> колесо).

Показує:
  - металопрофілі з моментом інерції й моментом опору (steel_profiles);
  - балку на згин: напруження, прогин, перевірка міцності з коефіцієнтом
    запасу, вагу конструкції (beam);
  - вал і колесо як обертові деталі (shaft);
  - редуктор: перерахунок моменту й обертів (transmission);
  - двигун BLDC: струм під навантаженням, потужність, тепловиділення,
    і зв'язок з модулем 4 (двигун як точка споживання) (motor);
  - кінематику: лінійна швидкість колеса, час розгону, чи вистачить
    моменту зрушити візок (kinematics).

Лише розрахунок і текстовий вивід — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.mechanics_demo
"""

from __future__ import annotations

from kovadlo import (
    Beam,
    GearboxTransmission,
    LoadScheme,
    Material,
    Motor,
    MotorKind,
    Point,
    Point3,
    IBeamProfile,
    Structure,
    can_move_mass,
    current_under_load_a,
    evaluate_beam,
    format_drive_report,
    format_structure_report,
    heat_dissipation_w,
    motor_pcb_track_width_mm,
    motor_to_consumption_point,
    power_input_w,
    required_force_to_move_n,
    time_to_speed_s,
    wheel_linear_speed_m_s,
)
from kovadlo.shaft import Shaft, wheel_moment_of_inertia_kg_m2
from kovadlo.transmission import rpm_to_rad_s

STEEL = Material(name="Сталь конструкційна S235JR", density_kg_m3=7850)


def section(title: str) -> None:
    print(f"\n=== {title} ===")


def main() -> None:
    # --- Рама з металопрофілів -------------------------------------------
    section("Рама: балки на згин")
    i_beam = IBeamProfile(height=100, flange_width=50, web_thickness=5, flange_thickness=7)
    frame = Structure()
    frame.add(
        Beam(start=Point3(0, 0, 0), end=Point3(1200, 0, 0), profile=i_beam, material=STEEL, name="Поперечина")
    )
    frame.add(
        Beam(start=Point3(0, 0, 0), end=Point3(0, 800, 0), profile=i_beam, material=STEEL, name="Стійка")
    )

    results = {
        "Поперечина": evaluate_beam(
            frame.beams["Поперечина"], load_n=3000.0, scheme=LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT,
            yield_strength_mpa=235.0,
        ),
        "Стійка": evaluate_beam(
            frame.beams["Стійка"], load_n=frame.total_weight_n, scheme=LoadScheme.CANTILEVER_END_POINT,
            yield_strength_mpa=235.0,
        ),
    }
    print(format_structure_report(frame, results))

    # --- Колесо як обертова деталь ----------------------------------------
    section("Колесо приводу")
    wheel_diameter_mm = 200.0
    wheel_mass_kg = 1.2
    wheel_inertia = wheel_moment_of_inertia_kg_m2(wheel_mass_kg, outer_radius_m=0.1, inner_radius_m=0.08)
    print(f"Момент інерції колеса (товсте кільце): {wheel_inertia:.4f} кг·м²")

    axle = Shaft(
        axis_start=Point3(0, 0, 0), axis_end=Point3(0, 0, 60), diameter_mm=12, material=STEEL, name="Вісь колеса"
    )
    print(f"Вісь колеса: маса {axle.mass_kg:.3f} кг, момент інерції {axle.mass_moment_of_inertia_kg_m2:.6f} кг·м²")

    # --- Привід: двигун -> редуктор -> колесо ------------------------------
    section("Привід")
    motor = Motor(
        name="Мотор-колесо", kind=MotorKind.BLDC, voltage_v=24.0, nominal_current_a=8.0, max_torque_nm=2.0,
        kv_rpm_per_v=150.0, efficiency=0.85,
    )
    gearbox = GearboxTransmission(gear_ratio=10, efficiency=0.9)
    input_rpm = 2000.0
    load_torque_output_nm = 1.5  # момент опору на валу колеса

    print(format_drive_report(motor, gearbox, input_rpm=input_rpm, load_torque_output_nm=load_torque_output_nm))

    input_torque_nm = load_torque_output_nm / (gearbox.ratio() * gearbox.efficiency)
    current_a = current_under_load_a(motor, input_torque_nm)
    heat_w = heat_dissipation_w(
        motor, current_a, torque_nm=input_torque_nm, angular_velocity_rad_s=rpm_to_rad_s(input_rpm)
    )
    print(f"Тепловиділення двигуна: {heat_w:.1f} Вт")

    consumer = motor_to_consumption_point(motor, Point(500, 500), current_a)
    print(f"Модуль 4: двигун як споживач «{consumer.name}» — {consumer.power_w:.1f} Вт ({current_a:.2f} А)")
    track_width = motor_pcb_track_width_mm(motor, input_torque_nm)
    print(f"Модуль 6: мінімальна ширина доріжки живлення на платі — {track_width:.2f} мм")

    # --- Кінематика візка ---------------------------------------------------
    section("Кінематика візка")
    output_rpm = gearbox.output_rpm(input_rpm)
    output_omega = rpm_to_rad_s(output_rpm)
    speed_m_s = wheel_linear_speed_m_s(wheel_diameter_mm, output_omega)
    print(f"Оберти колеса: {output_rpm:.0f} об/хв -> швидкість візка {speed_m_s:.2f} м/с")

    cart_mass_kg = 15.0
    accel_time_s = time_to_speed_s(
        target_speed_m_s=speed_m_s,
        wheel_diameter_mm=wheel_diameter_mm,
        mass_kg=cart_mass_kg,
        torque_nm=load_torque_output_nm,
        rotational_inertia_kg_m2=wheel_inertia,
    )
    print(f"Час розгону візка (маса {cart_mass_kg:.0f} кг) до {speed_m_s:.2f} м/с: {accel_time_s:.2f} с")

    friction = 0.05
    can_move = can_move_mass(load_torque_output_nm, wheel_diameter_mm, cart_mass_kg, friction_coefficient=friction)
    required_n = required_force_to_move_n(cart_mass_kg, friction_coefficient=friction)
    print(
        f"Чи вистачить моменту зрушити візок ({cart_mass_kg:.0f} кг, тертя {friction:.2f}): "
        f"{'ТАК' if can_move else 'НІ'} (потрібно {required_n:.1f} Н)"
    )


if __name__ == "__main__":
    main()
