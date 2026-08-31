"""
Кінематика руху (модуль 12): лінійна швидкість колеса, час розгону з
урахуванням маси й моменту інерції, перевірка "чи вистачить моменту
зрушити задану масу" — теорія машин і механізмів, динаміка твердого тіла.

Ідея переведення маси, що рухається лінійно, в еквівалентний момент
інерції на валу колеса (через квадрат радіуса) — стандартний прийом
розрахунку приводів коліс/транспортерів: колесо радіуса r, що котиться
без прослизання зі швидкістю v, обертається з кутовою швидкістю
ω = v/r, а маса m, яку воно везе, "виглядає" з боку вала як додатковий
момент інерції I = m·r² (та сама енергія руху ½mv² = ½(m·r²)·ω²).
"""

from __future__ import annotations

import math

from .mechanics_norms import GRAVITY_M_S2


def _radius_m(wheel_diameter_mm: float) -> float:
    if wheel_diameter_mm <= 0:
        raise ValueError("Діаметр колеса має бути додатним")
    return wheel_diameter_mm / 2 / 1000.0


def wheel_linear_speed_m_s(wheel_diameter_mm: float, angular_velocity_rad_s: float) -> float:
    """Лінійна швидкість колеса, м/с: v = ω·r (кочення без прослизання)."""
    return angular_velocity_rad_s * _radius_m(wheel_diameter_mm)


def wheel_angular_velocity_rad_s(wheel_diameter_mm: float, linear_speed_m_s: float) -> float:
    """Обернена задача: кутова швидкість за лінійною швидкістю, рад/с."""
    return linear_speed_m_s / _radius_m(wheel_diameter_mm)


def time_to_speed_s(
    target_speed_m_s: float,
    wheel_diameter_mm: float,
    mass_kg: float,
    torque_nm: float,
    rotational_inertia_kg_m2: float = 0.0,
) -> float:
    """Час розгону до `target_speed_m_s` при сталому крутному моменті
    `torque_nm` на валу колеса, з урахуванням маси, що рухається
    (`mass_kg`, приведена до валу як m·r²), і власного моменту інерції
    обертових частин (`rotational_inertia_kg_m2` — колеса, ротора тощо).

    З рівняння обертання M = I·dω/dt при сталому M: t = I·Δω / M.
    """
    if target_speed_m_s < 0:
        raise ValueError("Цільова швидкість не може бути від'ємною")
    if mass_kg < 0:
        raise ValueError("Маса не може бути від'ємною")
    if torque_nm <= 0:
        raise ValueError("Крутний момент для розгону має бути додатним")
    if rotational_inertia_kg_m2 < 0:
        raise ValueError("Момент інерції обертових частин не може бути від'ємним")

    radius_m = _radius_m(wheel_diameter_mm)
    target_omega = target_speed_m_s / radius_m
    effective_inertia = rotational_inertia_kg_m2 + mass_kg * radius_m**2
    return effective_inertia * target_omega / torque_nm


def required_force_to_move_n(mass_kg: float, friction_coefficient: float = 0.0, incline_deg: float = 0.0) -> float:
    """Сила, потрібна, щоб зрушити масу з місця: подолати тертя спокою
    й (на схилі) складову ваги вздовж схилу.

    F = m·g·(sin(схил) + μ·cos(схил))
    """
    if mass_kg < 0:
        raise ValueError("Маса не може бути від'ємною")
    if friction_coefficient < 0:
        raise ValueError("Коефіцієнт тертя не може бути від'ємним")
    incline_rad = math.radians(incline_deg)
    return mass_kg * GRAVITY_M_S2 * (math.sin(incline_rad) + friction_coefficient * math.cos(incline_rad))


def available_force_n(torque_nm: float, wheel_diameter_mm: float) -> float:
    """Тягове зусилля колеса при заданому крутному моменті: F = M / r."""
    return torque_nm / _radius_m(wheel_diameter_mm)


def can_move_mass(
    torque_nm: float,
    wheel_diameter_mm: float,
    mass_kg: float,
    friction_coefficient: float = 0.0,
    incline_deg: float = 0.0,
) -> bool:
    """Проста перевірка: чи вистачить моменту зрушити задану масу
    (тягове зусилля колеса ≥ сила опору рушанню)."""
    return available_force_n(torque_nm, wheel_diameter_mm) >= required_force_to_move_n(
        mass_kg, friction_coefficient, incline_deg
    )
