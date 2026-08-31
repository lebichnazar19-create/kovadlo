"""
Металопрофілі з моментом інерції й моментом опору перерізу (модуль 12).

Розширює `Profile` (модуль 1, `profile.py`) — ядро не змінене, лише
додано новий абстрактний нащадок `StructProfile` із двома новими
методами, потрібними для розрахунку балки на згин: `moment_of_inertia_mm4`
(момент інерції перерізу відносно центральної горизонтальної осі) і
`section_modulus_mm3` (момент опору = I / c, де c — відстань від
центроїда до найдальшого волокна перерізу).

Усі формули — стандартний курс опору матеріалів (площа й момент
інерції простих і складених перерізів через теорему Штейнера
(паралельних осей) або метод "суцільний мінус вирізаний прямокутник").
Профілі кутника й швелера — спрощені моделі (тонкостінне наближення,
без округлень на згинах, без добутку інерції для несиметричних
перерізів) — для точного розрахунку відповідального вузла звіряйте з
сортаментом (EN 10056 кутники, EN 10279 швелери, EN 10365 двотаври).
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass

from .profile import Profile


class StructProfile(Profile, ABC):
    """Профіль з даними, потрібними для розрахунку балки на згин."""

    @abstractmethod
    def moment_of_inertia_mm4(self) -> float:
        """Момент інерції перерізу відносно центральної горизонтальної
        осі (та, навколо якої балка згинається під вертикальним
        навантаженням), мм⁴."""
        raise NotImplementedError

    @abstractmethod
    def section_modulus_mm3(self) -> float:
        """Момент опору перерізу W = I / c, мм³ (c — відстань від
        центроїда до найдальшого волокна; саме на це волокно припадає
        максимальне напруження згину)."""
        raise NotImplementedError


@dataclass
class AngleProfile(StructProfile):
    """Кутник (рівно- чи нерівнополичний), тонкостінне наближення.

    leg_a — довжина вертикальної полиці, leg_b — горизонтальної,
    thickness — товщина обох полиць, усе в мм. Переріз моделюється як
    дві прямокутні смуги (вертикальна leg_a×thickness, горизонтальна
    leg_b×thickness), що перекриваються в кутовому квадраті
    thickness×thickness — площа й момент інерції рахуються з
    відніманням цього перекриття (теорема Штейнера відносно спільного
    центроїда).
    """

    leg_a: float
    leg_b: float
    thickness: float
    name: str = "angle"

    def cross_section_area_mm2(self) -> float:
        return self.thickness * (self.leg_a + self.leg_b - self.thickness)

    def _centroid_y_mm(self) -> float:
        t = self.thickness
        a1, y1 = t * self.leg_a, self.leg_a / 2  # вертикальна смуга
        a2, y2 = self.leg_b * t, t / 2  # горизонтальна смуга
        a_ov, y_ov = t * t, t / 2  # перекриття в кутку
        area = a1 + a2 - a_ov
        return (a1 * y1 + a2 * y2 - a_ov * y_ov) / area

    def moment_of_inertia_mm4(self) -> float:
        t = self.thickness
        y_bar = self._centroid_y_mm()

        a1, y1, i1 = t * self.leg_a, self.leg_a / 2, t * self.leg_a**3 / 12
        a2, y2, i2 = self.leg_b * t, t / 2, self.leg_b * t**3 / 12
        a_ov, y_ov, i_ov = t * t, t / 2, t**4 / 12

        return (
            (i1 + a1 * (y1 - y_bar) ** 2)
            + (i2 + a2 * (y2 - y_bar) ** 2)
            - (i_ov + a_ov * (y_ov - y_bar) ** 2)
        )

    def section_modulus_mm3(self) -> float:
        y_bar = self._centroid_y_mm()
        c_max = max(y_bar, self.leg_a - y_bar)
        return self.moment_of_inertia_mm4() / c_max


def _box_minus_box_area_mm2(width: float, height: float, inner_width: float, inner_height: float) -> float:
    return width * height - inner_width * inner_height


def _box_minus_box_inertia_mm4(width: float, height: float, inner_width: float, inner_height: float) -> float:
    """I суцільного прямокутника мінус I вирізаного (обидва центровані
    на тій самій горизонтальній осі — коректно для швелера й двотавра,
    де верхня й нижня полиці симетричні відносно середини висоти)."""
    return (width * height**3 - inner_width * inner_height**3) / 12


@dataclass
class ChannelProfile(StructProfile):
    """Швелер (U-подібний переріз).

    height — зовнішня висота, flange_width — ширина полиці,
    web_thickness — товщина стінки, flange_thickness — товщина полиці,
    усе в мм. Модель: суцільний прямокутник height×flange_width мінус
    вирізаний прямокутник (height - 2·flange_thickness) × (flange_width
    - web_thickness) з відкритого боку.
    """

    height: float
    flange_width: float
    web_thickness: float
    flange_thickness: float
    name: str = "channel"

    def _inner_dims_mm(self) -> tuple[float, float]:
        return self.flange_width - self.web_thickness, self.height - 2 * self.flange_thickness

    def cross_section_area_mm2(self) -> float:
        inner_w, inner_h = self._inner_dims_mm()
        return _box_minus_box_area_mm2(self.flange_width, self.height, inner_w, inner_h)

    def moment_of_inertia_mm4(self) -> float:
        inner_w, inner_h = self._inner_dims_mm()
        return _box_minus_box_inertia_mm4(self.flange_width, self.height, inner_w, inner_h)

    def section_modulus_mm3(self) -> float:
        return self.moment_of_inertia_mm4() / (self.height / 2)


@dataclass
class IBeamProfile(StructProfile):
    """Двотавр (I-подібний переріз).

    Ті самі параметри й та сама модель "суцільний мінус вирізаний
    прямокутник", що й швелер: відносно горизонтальної осі згину площа
    вирізаного матеріалу однакова незалежно від того, вирізана вона з
    одного боку (швелер) чи розділена на два симетричних вирізи
    (двотавр) — тому формула I й W тут та сама, що й у `ChannelProfile`
    з однаковими height/flange_width/web_thickness/flange_thickness
    (фізично коректно: I_x залежить лише від розподілу матеріалу по
    висоті, а не по ширині).
    """

    height: float
    flange_width: float
    web_thickness: float
    flange_thickness: float
    name: str = "i_beam"

    def _inner_dims_mm(self) -> tuple[float, float]:
        return self.flange_width - self.web_thickness, self.height - 2 * self.flange_thickness

    def cross_section_area_mm2(self) -> float:
        inner_w, inner_h = self._inner_dims_mm()
        return _box_minus_box_area_mm2(self.flange_width, self.height, inner_w, inner_h)

    def moment_of_inertia_mm4(self) -> float:
        inner_w, inner_h = self._inner_dims_mm()
        return _box_minus_box_inertia_mm4(self.flange_width, self.height, inner_w, inner_h)

    def section_modulus_mm3(self) -> float:
        return self.moment_of_inertia_mm4() / (self.height / 2)


@dataclass
class RoundTubeProfile(StructProfile):
    """Кругла труба: outer_diameter, wall_thickness, мм."""

    outer_diameter: float
    wall_thickness: float
    name: str = "round_tube"

    def _inner_diameter_mm(self) -> float:
        return self.outer_diameter - 2 * self.wall_thickness

    def cross_section_area_mm2(self) -> float:
        d_out, d_in = self.outer_diameter, self._inner_diameter_mm()
        return math.pi / 4 * (d_out**2 - d_in**2)

    def moment_of_inertia_mm4(self) -> float:
        d_out, d_in = self.outer_diameter, self._inner_diameter_mm()
        return math.pi / 64 * (d_out**4 - d_in**4)

    def section_modulus_mm3(self) -> float:
        return self.moment_of_inertia_mm4() / (self.outer_diameter / 2)


@dataclass
class RectTubeProfile(StructProfile):
    """Прямокутна труба: width, height (зовнішні), wall_thickness, мм."""

    width: float
    height: float
    wall_thickness: float
    name: str = "rect_tube"

    def _inner_dims_mm(self) -> tuple[float, float]:
        t = self.wall_thickness
        return self.width - 2 * t, self.height - 2 * t

    def cross_section_area_mm2(self) -> float:
        inner_w, inner_h = self._inner_dims_mm()
        return _box_minus_box_area_mm2(self.width, self.height, inner_w, inner_h)

    def moment_of_inertia_mm4(self) -> float:
        inner_w, inner_h = self._inner_dims_mm()
        return _box_minus_box_inertia_mm4(self.width, self.height, inner_w, inner_h)

    def section_modulus_mm3(self) -> float:
        return self.moment_of_inertia_mm4() / (self.height / 2)


@dataclass
class FlatBarProfile(StructProfile):
    """Смуга: прямокутний суцільний переріз width×thickness, мм.

    Згин розглядається навколо осі, паралельної широкій грані (смуга
    "лежить плиском") — найпоширеніший випадок використання смуги як
    балки.
    """

    width: float
    thickness: float
    name: str = "flat_bar"

    def cross_section_area_mm2(self) -> float:
        return self.width * self.thickness

    def moment_of_inertia_mm4(self) -> float:
        return self.width * self.thickness**3 / 12

    def section_modulus_mm3(self) -> float:
        return self.width * self.thickness**2 / 6


@dataclass
class RoundBarProfile(StructProfile):
    """Пруток: суцільний круглий переріз, diameter, мм."""

    diameter: float
    name: str = "round_bar"

    def cross_section_area_mm2(self) -> float:
        return math.pi / 4 * self.diameter**2

    def moment_of_inertia_mm4(self) -> float:
        return math.pi / 64 * self.diameter**4

    def section_modulus_mm3(self) -> float:
        return math.pi / 32 * self.diameter**3
