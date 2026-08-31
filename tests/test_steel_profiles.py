"""Тести металопрофілів модуля 12 — площа, момент інерції, момент опору.

Кожне очікуване число тут перераховане вручну (в коментарі) окремо від
формули в коді — незалежна перевірка, а не дзеркало реалізації.
"""

import math

import pytest

from kovadlo.steel_profiles import (
    AngleProfile,
    ChannelProfile,
    FlatBarProfile,
    IBeamProfile,
    RectTubeProfile,
    RoundBarProfile,
    RoundTubeProfile,
    StructProfile,
)


def test_struct_profile_is_abstract():
    with pytest.raises(TypeError):
        StructProfile()  # type: ignore[abstract]


def test_round_bar_hand_verified():
    # d = 20 мм: A = π/4·20² = 314.159..., I = π/64·20⁴ = 7853.98...,
    # W = π/32·20³ = 785.40...
    p = RoundBarProfile(diameter=20)
    assert p.cross_section_area_mm2() == pytest.approx(math.pi / 4 * 400)
    assert p.moment_of_inertia_mm4() == pytest.approx(math.pi / 64 * 160_000)
    assert p.section_modulus_mm3() == pytest.approx(math.pi / 32 * 8_000)


def test_round_tube_hand_verified():
    # D=50, t=5 -> d_in=40. A = π/4·(2500-1600) = 706.86; I = π/64·(6 250 000
    # - 2 560 000) = 181 132.45; W = I / 25 = 7245.30
    p = RoundTubeProfile(outer_diameter=50, wall_thickness=5)
    assert p.cross_section_area_mm2() == pytest.approx(math.pi / 4 * 900)
    expected_i = math.pi / 64 * (50**4 - 40**4)
    assert p.moment_of_inertia_mm4() == pytest.approx(expected_i)
    assert p.section_modulus_mm3() == pytest.approx(expected_i / 25)


def test_flat_bar_hand_verified():
    # 40×5 мм: A = 200 мм²; I = 40·5³/12 = 416.667; W = 40·5²/6 = 166.667
    p = FlatBarProfile(width=40, thickness=5)
    assert p.cross_section_area_mm2() == pytest.approx(200)
    assert p.moment_of_inertia_mm4() == pytest.approx(40 * 125 / 12)
    assert p.section_modulus_mm3() == pytest.approx(40 * 25 / 6)


def test_channel_and_i_beam_hand_verified_and_equal_ix():
    # H=100, B=50, tw=5, tf=7 -> внутрішній виріз 45×86.
    # A = 50·100 - 45·86 = 5000 - 3870 = 1130
    # I = (50·100³ - 45·86³)/12 = (50 000 000 - 28 622 520)/12 = 1 781 456.67
    ch = ChannelProfile(height=100, flange_width=50, web_thickness=5, flange_thickness=7)
    ib = IBeamProfile(height=100, flange_width=50, web_thickness=5, flange_thickness=7)
    inner_w, inner_h = 45, 86
    expected_area = 50 * 100 - inner_w * inner_h
    expected_i = (50 * 100**3 - inner_w * inner_h**3) / 12
    assert ch.cross_section_area_mm2() == pytest.approx(expected_area)
    assert ch.moment_of_inertia_mm4() == pytest.approx(expected_i)
    assert ch.section_modulus_mm3() == pytest.approx(expected_i / 50)
    # Фізично Ix навколо горизонтальної осі однаковий для швелера й
    # двотавра з тими самими H/B/tw/tf (розподіл матеріалу по висоті
    # той самий) — саме це й перевіряємо як інваріант.
    assert ib.cross_section_area_mm2() == pytest.approx(ch.cross_section_area_mm2())
    assert ib.moment_of_inertia_mm4() == pytest.approx(ch.moment_of_inertia_mm4())
    assert ib.section_modulus_mm3() == pytest.approx(ch.section_modulus_mm3())


def test_rect_tube_hand_verified():
    # 60×40, t=3 -> внутрішні 54×34.
    # A = 60·40 - 54·34 = 2400 - 1836 = 564
    p = RectTubeProfile(width=60, height=40, wall_thickness=3)
    inner_w, inner_h = 54, 34
    expected_area = 60 * 40 - inner_w * inner_h
    expected_i = (60 * 40**3 - inner_w * inner_h**3) / 12
    assert p.cross_section_area_mm2() == pytest.approx(expected_area)
    assert p.moment_of_inertia_mm4() == pytest.approx(expected_i)
    assert p.section_modulus_mm3() == pytest.approx(expected_i / 20)


def test_angle_hand_verified():
    # leg_a=50 (вертикальна), leg_b=30 (горизонтальна), t=4.
    # A = 4·(50+30-4) = 4·76 = 304
    t, leg_a, leg_b = 4, 50, 30
    p = AngleProfile(leg_a=leg_a, leg_b=leg_b, thickness=t)
    assert p.cross_section_area_mm2() == pytest.approx(304)

    # Незалежний ручний перерахунок центроїда й моменту інерції —
    # той самий метод (Штейнер), але записаний окремо від коду профілю.
    a1, y1 = t * leg_a, leg_a / 2
    a2, y2 = leg_b * t, t / 2
    a_ov, y_ov = t * t, t / 2
    area = a1 + a2 - a_ov
    y_bar = (a1 * y1 + a2 * y2 - a_ov * y_ov) / area
    i1 = t * leg_a**3 / 12
    i2 = leg_b * t**3 / 12
    i_ov = t**4 / 12
    expected_i = (i1 + a1 * (y1 - y_bar) ** 2) + (i2 + a2 * (y2 - y_bar) ** 2) - (i_ov + a_ov * (y_ov - y_bar) ** 2)
    expected_w = expected_i / max(y_bar, leg_a - y_bar)

    assert p.moment_of_inertia_mm4() == pytest.approx(expected_i)
    assert p.section_modulus_mm3() == pytest.approx(expected_w)


def test_square_angle_centroid_hand_verified():
    # Рівнополичний кутник (L=40, t=5): формула центроїда згорнута
    # аналітично (a1=a2=tL, y1=L/2, y2=t/2, площа=t(2L-t)):
    #   y_bar = (L² + Lt - t²) / (2(2L - t))
    # НЕ дорівнює L/2 — центроїд L-подібного перерізу зміщений ближче
    # до кутка, бо там менше "розкиданого" матеріалу, ніж по всій
    # висоті полиці.
    L, t = 40, 5
    p = AngleProfile(leg_a=L, leg_b=L, thickness=t)
    expected_y_bar = (L**2 + L * t - t**2) / (2 * (2 * L - t))
    assert p._centroid_y_mm() == pytest.approx(expected_y_bar)
    assert expected_y_bar == pytest.approx(11.8333333, abs=1e-6)
