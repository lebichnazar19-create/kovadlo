"""
Вал і обертові деталі (модуль 12): вісь обертання, маса, момент
інерції обертової маси диска/кільця/колеса.

**Важливе розрізнення термінів** (в українській/технічній літературі
обидва звуться "момент інерції", але це різні фізичні величини):

- момент інерції ПЕРЕРІЗУ (мм⁴, `StructProfile.moment_of_inertia_mm4`,
  `steel_profiles.py`) — характеристика форми перерізу, потрібна для
  розрахунку балки на згин (опір матеріалів);
- момент інерції ОБЕРТОВОЇ МАСИ (кг·м², цей файл) — характеристика
  розподілу маси відносно осі обертання, потрібна для динаміки
  обертання (M = I·ε, кінетична енергія обертання тощо; теорія машин
  і механізмів).

Формули дисків/кілець/коліс — стандартні (теорія машин і механізмів,
динаміка твердого тіла): суцільний диск I = ½mr², тонке кільце (обід)
I = mr², товстий диск/кільце (внутрішній і зовнішній радіус) —
узагальнена формула порожнистого циліндра I = ½m(r_out² + r_in²), яка
переходить у формулу суцільного диска при r_in = 0.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .geometry3d import Point3
from .materials import Material


def disk_moment_of_inertia_kg_m2(mass_kg: float, radius_m: float) -> float:
    """Суцільний диск відносно осі, перпендикулярної площині диска й
    що проходить через центр: I = ½·m·r²."""
    return 0.5 * mass_kg * radius_m**2


def ring_moment_of_inertia_kg_m2(mass_kg: float, radius_m: float) -> float:
    """Тонке кільце (обід, уся маса зосереджена на радіусі r): I = m·r²."""
    return mass_kg * radius_m**2


def wheel_moment_of_inertia_kg_m2(mass_kg: float, outer_radius_m: float, inner_radius_m: float = 0.0) -> float:
    """Колесо як порожнистий циліндр/товсте кільце (зовнішній і
    внутрішній радіус): I = ½·m·(r_out² + r_in²).

    При `inner_radius_m=0` це та сама формула суцільного диска —
    інваріант, перевірений тестом.
    """
    if inner_radius_m < 0 or inner_radius_m > outer_radius_m:
        raise ValueError("Внутрішній радіус має бути в межах [0, зовнішній радіус]")
    return 0.5 * mass_kg * (outer_radius_m**2 + inner_radius_m**2)


@dataclass(kw_only=True)
class Shaft:
    """Вал: вісь обертання (дві точки в просторі), діаметр, матеріал."""

    axis_start: Point3
    axis_end: Point3
    diameter_mm: float
    material: Material
    name: str = ""

    def __post_init__(self) -> None:
        if self.diameter_mm <= 0:
            raise ValueError("Діаметр вала має бути додатним")

    @property
    def length_mm(self) -> float:
        return self.axis_start.distance_to(self.axis_end)

    @property
    def radius_m(self) -> float:
        return self.diameter_mm / 2 / 1000.0

    @property
    def volume_mm3(self) -> float:
        return math.pi / 4 * self.diameter_mm**2 * self.length_mm

    @property
    def mass_kg(self) -> float:
        if self.material.density_kg_m3 is None:
            raise ValueError(f"У матеріалу «{self.material.name}» не задана густина")
        return self.volume_mm3 * self.material.density_kg_m3 / 1_000_000_000.0

    @property
    def mass_moment_of_inertia_kg_m2(self) -> float:
        """Вал як суцільний циліндр, що обертається навколо власної
        поздовжньої осі: I = ½·m·r²."""
        return disk_moment_of_inertia_kg_m2(self.mass_kg, self.radius_m)
