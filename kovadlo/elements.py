"""
Element — базовий будівельний елемент.

Архітектура на майбутнє: будь-який лінійний будівельний елемент (стіна,
балка, металевий каркас тощо) описується однаково — дві точки + профіль
перерізу + матеріал + кут повороту профілю навколо осі елемента. Це
дозволяє додавати нові типи елементів і нові профілі (див. `profile.py`),
не переписуючи цей клас.
"""

from __future__ import annotations

from dataclasses import dataclass

from .geometry import Point
from .materials import Material
from .profile import Profile


@dataclass(kw_only=True)
class Element:
    """Базовий елемент: дві точки + профіль + матеріал + кут."""

    start: Point
    end: Point
    profile: Profile
    material: Material
    angle: float = 0.0  # кут повороту профілю навколо осі елемента, градуси

    @property
    def length_mm(self) -> float:
        """Довжина елемента (відстань між точками), мм."""
        return self.start.distance_to(self.end)

    @property
    def direction_deg(self) -> float:
        """Напрямок елемента від start до end, градуси [0, 360)."""
        return self.start.angle_to(self.end)
