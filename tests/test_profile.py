import math

import pytest

from kovadlo.elements import Element
from kovadlo.geometry import Point
from kovadlo.materials import Material
from kovadlo.profile import (
    RectangularProfile,
    SteelAngleProfile,
    SteelChannelProfile,
    SteelPipeProfile,
)


def test_rectangular_profile_area():
    profile = RectangularProfile(thickness=200, height=2700)
    assert profile.cross_section_area_mm2() == pytest.approx(200 * 2700)


def test_steel_channel_profile_area():
    profile = SteelChannelProfile(height=200, flange_width=76, web_thickness=5.2, flange_thickness=8.7)
    expected = 200 * 5.2 + 2 * 76 * 8.7
    assert profile.cross_section_area_mm2() == pytest.approx(expected)


def test_steel_angle_profile_area():
    profile = SteelAngleProfile(leg_a=50, leg_b=50, thickness=5)
    expected = 5 * (50 + 50 - 5)
    assert profile.cross_section_area_mm2() == pytest.approx(expected)


def test_steel_pipe_profile_area():
    profile = SteelPipeProfile(outer_diameter=60, wall_thickness=4)
    outer_r, inner_r = 30, 26
    expected = math.pi * (outer_r**2 - inner_r**2)
    assert profile.cross_section_area_mm2() == pytest.approx(expected)


@pytest.mark.parametrize(
    "profile",
    [
        RectangularProfile(thickness=100, height=2500),
        SteelChannelProfile(height=200, flange_width=76, web_thickness=5.2, flange_thickness=8.7),
        SteelAngleProfile(leg_a=63, leg_b=40, thickness=5),
        SteelPipeProfile(outer_diameter=48, wall_thickness=3),
    ],
)
def test_element_accepts_any_profile_without_core_changes(profile):
    """Ключова перевірка архітектури: Element працює з будь-яким Profile,
    включно з майбутніми металопрофілями, без жодних змін у своєму коді."""
    element = Element(
        start=Point(0, 0),
        end=Point(1000, 0),
        profile=profile,
        material=Material(name="сталь"),
    )
    assert element.length_mm == pytest.approx(1000.0)
    assert element.profile.cross_section_area_mm2() > 0
