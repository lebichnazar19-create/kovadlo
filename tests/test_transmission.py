"""Тести передач модуля 12 — оберти/потужність і момент через редуктор.

Ключове число з завдання — "момент через редуктор" — перевірене вручну
в `test_gearbox_output_torque_hand_verified`.
"""

import math

import pytest

from kovadlo.transmission import (
    BeltTransmission,
    DirectTransmission,
    GearboxTransmission,
    Transmission,
    power_w,
    rad_s_to_rpm,
    rpm_to_rad_s,
    torque_nm,
)


def test_transmission_is_abstract():
    with pytest.raises(TypeError):
        Transmission()  # type: ignore[abstract]


def test_rpm_rad_s_roundtrip_hand_verified():
    # 1500 об/хв -> рад/с: 1500·2π/60 = 157.0796...
    assert rpm_to_rad_s(1500) == pytest.approx(1500 * 2 * math.pi / 60)
    assert rpm_to_rad_s(1500) == pytest.approx(157.0796326794897)
    assert rad_s_to_rpm(rpm_to_rad_s(1500)) == pytest.approx(1500)


def test_power_and_torque_hand_verified():
    # P = M·ω: 20 Н·м при 100 рад/с -> 2000 Вт
    assert power_w(20.0, 100.0) == pytest.approx(2000.0)
    assert torque_nm(2000.0, 100.0) == pytest.approx(20.0)


def test_torque_rejects_zero_angular_velocity():
    with pytest.raises(ValueError):
        torque_nm(1000.0, 0.0)


def test_direct_transmission_passes_through():
    d = DirectTransmission()
    assert d.ratio() == pytest.approx(1.0)
    assert d.output_torque_nm(15.0) == pytest.approx(15.0)
    assert d.output_angular_velocity_rad_s(50.0) == pytest.approx(50.0)


def test_gearbox_output_torque_hand_verified():
    # Редуктор i=5, ККД=0.9: вхід 1500 об/хв, момент 10 Н·м.
    # Вихідні оберти: 1500/5 = 300 об/хв.
    # Вихідний момент: 10·5·0.9 = 45 Н·м.
    gearbox = GearboxTransmission(gear_ratio=5, efficiency=0.9)
    assert gearbox.output_rpm(1500) == pytest.approx(300.0)
    assert gearbox.output_torque_nm(10.0) == pytest.approx(45.0)


def test_gearbox_power_ratio_equals_efficiency():
    # Потужність на виході = ККД × потужність на вході (втрати на тертя).
    gearbox = GearboxTransmission(gear_ratio=4, efficiency=0.85)
    in_omega = rpm_to_rad_s(1200)
    in_torque = 8.0
    out_omega = gearbox.output_angular_velocity_rad_s(in_omega)
    out_torque = gearbox.output_torque_nm(in_torque)

    p_in = power_w(in_torque, in_omega)
    p_out = power_w(out_torque, out_omega)
    assert p_out / p_in == pytest.approx(0.85)


def test_gearbox_rejects_bad_params():
    with pytest.raises(ValueError):
        GearboxTransmission(gear_ratio=0)
    with pytest.raises(ValueError):
        GearboxTransmission(gear_ratio=-3)
    with pytest.raises(ValueError):
        GearboxTransmission(gear_ratio=5, efficiency=0)
    with pytest.raises(ValueError):
        GearboxTransmission(gear_ratio=5, efficiency=1.1)


def test_belt_transmission_from_pulley_diameters_hand_verified():
    # Ведучий шків 50 мм, ведений 150 мм -> i = 150/50 = 3.
    # Оберти на виході втричі менші: 3000 -> 1000 об/хв.
    belt = BeltTransmission.from_pulley_diameters(driving_diameter_mm=50, driven_diameter_mm=150, efficiency=1.0)
    assert belt.ratio() == pytest.approx(3.0)
    assert belt.output_rpm(3000) == pytest.approx(1000.0)
    assert belt.output_torque_nm(10.0) == pytest.approx(30.0)


def test_belt_transmission_rejects_non_positive_diameters():
    with pytest.raises(ValueError):
        BeltTransmission.from_pulley_diameters(driving_diameter_mm=0, driven_diameter_mm=100)
    with pytest.raises(ValueError):
        BeltTransmission.from_pulley_diameters(driving_diameter_mm=50, driven_diameter_mm=-10)


def test_belt_transmission_speed_up_when_ratio_below_one():
    # Ведучий шків більший за ведений -> передача пришвидшує обертання.
    belt = BeltTransmission.from_pulley_diameters(driving_diameter_mm=150, driven_diameter_mm=50, efficiency=1.0)
    assert belt.ratio() == pytest.approx(1.0 / 3.0)
    assert belt.output_rpm(1000) == pytest.approx(3000.0)
