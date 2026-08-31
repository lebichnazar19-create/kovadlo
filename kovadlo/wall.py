"""Стіна — будівельний елемент з висотою."""

from __future__ import annotations

from dataclasses import dataclass

from .elements import Element
from .geometry import MM2_PER_M2, Point
from .materials import Material
from .profile import RectangularProfile


@dataclass(kw_only=True)
class Wall(Element):
    """Стіна: `Element` + висота.

    Товщина стіни зберігається в профілі (типово `RectangularProfile.thickness`).
    """

    height: float  # мм

    def __post_init__(self) -> None:
        if self.height <= 0:
            raise ValueError("Висота стіни має бути додатною")
        if self.length_mm <= 0:
            raise ValueError("Стіна не може мати нульову довжину (start == end)")

    @classmethod
    def create(
        cls,
        *,
        start: Point,
        end: Point,
        height: float,
        thickness: float,
        material: Material,
        angle: float = 0.0,
    ) -> "Wall":
        """Зручний конструктор: дві точки + висота + товщина + матеріал
        одразу створюють прямокутний профіль."""
        profile = RectangularProfile(thickness=thickness, height=height)
        return cls(
            start=start,
            end=end,
            profile=profile,
            material=material,
            angle=angle,
            height=height,
        )

    @property
    def thickness_mm(self) -> float:
        """Товщина стіни, мм (береться з профілю)."""
        thickness = getattr(self.profile, "thickness", None)
        if thickness is None:
            raise AttributeError("Профіль цієї стіни не має атрибута 'thickness'")
        return thickness

    @property
    def area_mm2(self) -> float:
        """Площа стіни (довжина × висота), мм²."""
        return self.length_mm * self.height

    @property
    def area_m2(self) -> float:
        """Площа стіни (довжина × висота), м²."""
        return self.area_mm2 / MM2_PER_M2
