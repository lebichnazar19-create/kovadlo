"""
Балка й конструкція з балок (модуль 12): вага, кут нахилу, напруження
на згин, прогин, перевірка міцності з коефіцієнтом запасу.

`Beam` — та сама ідея, що й `Element` (модуль 1): дві точки + профіль +
матеріал + кут повороту профілю навколо осі. Тут точки тривимірні
(`Point3`, модуль 10, y — висота), бо кут нахилу елемента відносно
горизонталі й вертикалі не має сенсу для суто плоского плану модуля 1 —
`Beam` навмисно НЕ успадковує `Element`, а є окремим класом тієї самої
форми, щоб не змінювати ядро й не змішувати 2D-стіни з 3D-балками.

Формули згину й прогину — стандартні розрахункові схеми опору
матеріалів/будівельної механіки для двох типових способів обпирання
(шарнірно обпертa балка, консоль) і двох типів навантаження
(зосереджена сила посередині прольоту/на кінці консолі, рівномірно
розподілене навантаження). Для довільнішої розрахункової схеми
(нерівномірний розподіл, кілька сил, пружні опори) використовуйте
спеціалізоване ПЗ будівельної механіки — тут навмисно лише
найпоширеніші канонічні випадки.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum

from .geometry3d import Point3
from .materials import Material
from .mechanics_norms import (
    DEFAULT_SAFETY_FACTOR,
    GRAVITY_M_S2,
    MAX_DEFLECTION_RATIO,
    elastic_modulus_mpa_for,
)
from .steel_profiles import StructProfile


@dataclass(kw_only=True)
class Beam:
    """Балка: дві точки в просторі + профіль + матеріал + кут повороту
    профілю навколо осі балки, градуси."""

    start: Point3
    end: Point3
    profile: StructProfile
    material: Material
    angle: float = 0.0
    name: str = ""

    @property
    def length_mm(self) -> float:
        return self.start.distance_to(self.end)

    @property
    def volume_mm3(self) -> float:
        return self.profile.cross_section_area_mm2() * self.length_mm

    @property
    def weight_kg(self) -> float:
        """Маса балки, кг — потребує густини матеріалу
        (`Material.density_kg_m3`)."""
        if self.material.density_kg_m3 is None:
            raise ValueError(f"У матеріалу «{self.material.name}» не задана густина")
        return self.volume_mm3 * self.material.density_kg_m3 / 1_000_000_000.0  # мм³ -> м³

    @property
    def weight_n(self) -> float:
        """Вага балки (сила), Н = маса × g."""
        return self.weight_kg * GRAVITY_M_S2

    @property
    def angle_to_horizontal_deg(self) -> float:
        """Кут нахилу балки відносно горизонтальної площини (x, z), градуси
        [0, 90]. 0° — балка лежить горизонтально, 90° — вертикальна стійка."""
        length = self.length_mm
        if length == 0:
            return 0.0
        dy = abs(self.end.y - self.start.y)
        return math.degrees(math.asin(min(1.0, dy / length)))

    @property
    def angle_to_vertical_deg(self) -> float:
        """Кут нахилу балки відносно вертикальної осі, градуси [0, 90] —
        доповнює `angle_to_horizontal_deg` до 90°."""
        return 90.0 - self.angle_to_horizontal_deg


class LoadScheme(Enum):
    """Розрахункова схема навантаження балки."""

    SIMPLY_SUPPORTED_CENTER_POINT = "шарнірно обперта, зосереджена сила посередині"
    SIMPLY_SUPPORTED_UNIFORM = "шарнірно обперта, рівномірно розподілене навантаження"
    CANTILEVER_END_POINT = "консоль, зосереджена сила на кінці"
    CANTILEVER_UNIFORM = "консоль, рівномірно розподілене навантаження"


# Коефіцієнти класичних формул опору матеріалів для максимального згинального
# моменту (частка від P·L) і прогину (частка від P·L³/(EI)) для кожної схеми.
_MOMENT_COEFF: dict[LoadScheme, float] = {
    LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT: 1.0 / 4.0,
    LoadScheme.SIMPLY_SUPPORTED_UNIFORM: 1.0 / 8.0,
    LoadScheme.CANTILEVER_END_POINT: 1.0,
    LoadScheme.CANTILEVER_UNIFORM: 1.0 / 2.0,
}

_DEFLECTION_COEFF: dict[LoadScheme, float] = {
    LoadScheme.SIMPLY_SUPPORTED_CENTER_POINT: 1.0 / 48.0,
    LoadScheme.SIMPLY_SUPPORTED_UNIFORM: 5.0 / 384.0,
    LoadScheme.CANTILEVER_END_POINT: 1.0 / 3.0,
    LoadScheme.CANTILEVER_UNIFORM: 1.0 / 8.0,
}


def bending_moment_max_nmm(load_n: float, length_mm: float, scheme: LoadScheme) -> float:
    """Максимальний згинальний момент, Н·мм (`load_n` — сумарне
    навантаження: зосереджена сила або сума розподіленого навантаження
    по всій довжині)."""
    return _MOMENT_COEFF[scheme] * load_n * length_mm


def max_deflection_mm(
    load_n: float, length_mm: float, elastic_modulus_mpa: float, moment_of_inertia_mm4: float, scheme: LoadScheme
) -> float:
    """Максимальний прогин, мм."""
    if elastic_modulus_mpa <= 0 or moment_of_inertia_mm4 <= 0:
        raise ValueError("Модуль пружності й момент інерції мають бути додатними")
    coeff = _DEFLECTION_COEFF[scheme]
    return coeff * load_n * length_mm**3 / (elastic_modulus_mpa * moment_of_inertia_mm4)


def bending_stress_mpa(moment_max_nmm: float, section_modulus_mm3: float) -> float:
    """Напруження на згин, МПа = Н/мм²: σ = M / W."""
    if section_modulus_mm3 <= 0:
        raise ValueError("Момент опору перерізу має бути додатним")
    return moment_max_nmm / section_modulus_mm3


@dataclass
class BeamCheckResult:
    """Результат перевірки балки на міцність і прогин."""

    scheme: LoadScheme
    load_n: float
    moment_max_nmm: float
    stress_mpa: float
    allowable_stress_mpa: float
    deflection_mm: float
    deflection_limit_mm: float
    safety_margin: float  # фактичний коефіцієнт запасу = yield / stress

    @property
    def passes_strength(self) -> bool:
        return self.stress_mpa <= self.allowable_stress_mpa

    @property
    def passes_deflection(self) -> bool:
        return self.deflection_mm <= self.deflection_limit_mm

    @property
    def passes(self) -> bool:
        return self.passes_strength and self.passes_deflection


def evaluate_beam(
    beam: Beam,
    load_n: float,
    scheme: LoadScheme,
    yield_strength_mpa: float,
    *,
    elastic_modulus_mpa: float | None = None,
    safety_factor: float = DEFAULT_SAFETY_FACTOR,
    deflection_ratio: float = MAX_DEFLECTION_RATIO,
) -> BeamCheckResult:
    """Повна перевірка балки: момент, напруження, прогин, проходить/ні
    за міцністю (з коефіцієнтом запасу) і за прогином (L/деякий поділ).

    `elastic_modulus_mpa=None` означає пошук за назвою матеріалу балки
    в `mechanics_norms.ELASTIC_MODULUS_MPA` — якщо матеріалу там нема,
    треба передати значення явно.
    """
    if load_n < 0:
        raise ValueError("Навантаження не може бути від'ємним")
    if yield_strength_mpa <= 0:
        raise ValueError("Границя текучості має бути додатною")
    if safety_factor <= 0:
        raise ValueError("Коефіцієнт запасу має бути додатним")

    if elastic_modulus_mpa is None:
        elastic_modulus_mpa = elastic_modulus_mpa_for(beam.material.name)
        if elastic_modulus_mpa is None:
            raise ValueError(
                f"Немає модуля пружності для матеріалу «{beam.material.name}» — передайте elastic_modulus_mpa явно"
            )

    length_mm = beam.length_mm
    moment_max = bending_moment_max_nmm(load_n, length_mm, scheme)
    stress = bending_stress_mpa(moment_max, beam.profile.section_modulus_mm3())
    deflection = max_deflection_mm(
        load_n, length_mm, elastic_modulus_mpa, beam.profile.moment_of_inertia_mm4(), scheme
    )
    allowable_stress = yield_strength_mpa / safety_factor
    safety_margin = yield_strength_mpa / stress if stress > 0 else math.inf

    return BeamCheckResult(
        scheme=scheme,
        load_n=load_n,
        moment_max_nmm=moment_max,
        stress_mpa=stress,
        allowable_stress_mpa=allowable_stress,
        deflection_mm=deflection,
        deflection_limit_mm=deflection_ratio * length_mm,
        safety_margin=safety_margin,
    )


@dataclass
class Structure:
    """Конструкція з іменованих балок — вага цілого каркаса."""

    beams: dict[str, Beam] = field(default_factory=dict)

    def add(self, beam: Beam) -> None:
        name = beam.name or f"балка {len(self.beams) + 1}"
        if name in self.beams:
            raise ValueError(f"Балка з назвою «{name}» вже є в конструкції")
        self.beams[name] = beam

    @property
    def total_weight_kg(self) -> float:
        return sum(beam.weight_kg for beam in self.beams.values())

    @property
    def total_weight_n(self) -> float:
        return self.total_weight_kg * GRAVITY_M_S2
