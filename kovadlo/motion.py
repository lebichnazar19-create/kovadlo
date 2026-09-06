"""
Рух деталей у часі: Transform (поворот + зсув) і рухи з методом at(t).

Ядро без графіки: рахує лише трансформації точок у часі, той самий
принцип, що й у решті проєкту — розкладка/розрахунок окремо від
рендеру (модулі 3/5/9/11 читають ці дані, самі їх не рахуючи).

Система координат узгоджена з модулем 10 (`geometry3d.py`) — Point3,
мм для зсувів. Кути на вході рухів — градуси (rpm для Rotation),
усередині рахунок веде в радіанах (перевикористовує `rpm_to_rad_s` з
модуля 12, `transmission.py`, той самий підхід, що й для оборотів
валу/колеса).

`Transform` — жорстке перетворення (rotation, translation), rotation —
матриця повороту 3x3 (рядки), translation — вектор зсуву:

    apply(point) = rotation @ point + translation

Композиція двох перетворень (`then`) — стандартна композиція SE(3):
якщо T = A.then(B), то T.apply(p) == B.apply(A.apply(p)) — спершу A,
потім B. Саме на цьому будується `Composite`: кілька рухів на одній
деталі застосовуються послідовно, і порядок у списку впливає на
результат (обертання й зсув не комутують).

`Rotation`/`Geared` — спільна база `RotationalMotion`: обидва виражені
кутом навколо однієї осі, тому `Geared` (кероване від іншого
обертального руху через передавальне число) успадковує вісь/точку
опори від `parent` і лише масштабує кут. `Geared.parent` навмисно
обмежений `RotationalMotion` (`Rotation` чи інший `Geared`) — "удвічі
більший кут" не має сенсу для лінійного чи складеного руху; інший тип
`parent` — `TypeError`.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Sequence

from .geometry3d import Point3
from .transmission import GearMesh, rpm_to_rad_s

Vector3 = tuple[float, float, float]
Matrix3 = tuple[Vector3, Vector3, Vector3]

_IDENTITY_MATRIX: Matrix3 = ((1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0))
_ZERO_VECTOR: Vector3 = (0.0, 0.0, 0.0)


def _normalize(v: Vector3) -> Vector3:
    """Одиничний вектор напрямку `v`; кидає ValueError для нульового вектора."""
    length = math.sqrt(v[0] ** 2 + v[1] ** 2 + v[2] ** 2)
    if length == 0:
        raise ValueError("Вісь/напрямок не може бути нульовим вектором")
    return (v[0] / length, v[1] / length, v[2] / length)


def _matvec(m: Matrix3, v: Vector3) -> Vector3:
    return tuple(sum(m[i][j] * v[j] for j in range(3)) for i in range(3))  # type: ignore[return-value]


def _matmul(a: Matrix3, b: Matrix3) -> Matrix3:
    return tuple(  # type: ignore[return-value]
        tuple(sum(a[i][k] * b[k][j] for k in range(3)) for j in range(3)) for i in range(3)
    )


def _rotation_matrix(axis: Vector3, angle_deg: float) -> Matrix3:
    """Матриця повороту на `angle_deg` навколо `axis` (формула Родріга).

    Вісь проходить через початок координат — зсув для повороту навколо
    довільної точки додає `Transform.rotation_about`.
    """
    kx, ky, kz = _normalize(axis)
    theta = math.radians(angle_deg)
    c = math.cos(theta)
    s = math.sin(theta)
    t = 1.0 - c
    return (
        (t * kx * kx + c, t * kx * ky - s * kz, t * kx * kz + s * ky),
        (t * kx * ky + s * kz, t * ky * ky + c, t * ky * kz - s * kx),
        (t * kx * kz - s * ky, t * ky * kz + s * kx, t * kz * kz + c),
    )


@dataclass(frozen=True)
class Transform:
    """Жорстке перетворення точки: поворот (3x3 матриця) + зсув (вектор, мм)."""

    rotation: Matrix3 = _IDENTITY_MATRIX
    translation: Vector3 = _ZERO_VECTOR

    @classmethod
    def identity(cls) -> "Transform":
        return cls()

    @classmethod
    def translation_by(cls, offset: Vector3) -> "Transform":
        return cls(rotation=_IDENTITY_MATRIX, translation=offset)

    @classmethod
    def rotation_about(cls, axis: Vector3, origin: Point3, angle_deg: float) -> "Transform":
        """Поворот на `angle_deg` навколо прямої, що проходить через `origin`
        з напрямком `axis`. `origin` лишається на місці (нерухома точка осі)."""
        r = _rotation_matrix(axis, angle_deg)
        o: Vector3 = (origin.x, origin.y, origin.z)
        r_o = _matvec(r, o)
        translation = (o[0] - r_o[0], o[1] - r_o[1], o[2] - r_o[2])
        return cls(rotation=r, translation=translation)

    def apply(self, point: Point3) -> Point3:
        """Застосовує перетворення до точки: rotation @ point + translation."""
        v: Vector3 = (point.x, point.y, point.z)
        rv = _matvec(self.rotation, v)
        return Point3(rv[0] + self.translation[0], rv[1] + self.translation[1], rv[2] + self.translation[2])

    def then(self, other: "Transform") -> "Transform":
        """Перетворення "спершу self, потім other": apply == other.apply(self.apply(p))."""
        rotation = _matmul(other.rotation, self.rotation)
        rotated_translation = _matvec(other.rotation, self.translation)
        translation = tuple(rotated_translation[i] + other.translation[i] for i in range(3))
        return Transform(rotation=rotation, translation=translation)  # type: ignore[arg-type]


class Motion(ABC):
    """Базовий рух деталі: трансформація як функція часу."""

    @abstractmethod
    def at(self, t: float) -> Transform:
        """Трансформація деталі в момент часу `t` (секунди від початку руху)."""
        raise NotImplementedError


@dataclass
class Linear(Motion):
    """Рівномірний зсув уздовж `axis` на `distance` (мм) за `duration` (с).

    Використовується і для розльоту деталей вибуховою схемою, і для
    ходу поршня. `t` клампується до [0, duration] — рух зупиняється й
    лишається в кінцевому положенні, а не проскакує його чи їде далі.
    Зворотний хід (поршень туди-сюди) — не цей клас, а комбінація
    рухів (`Composite`) чи окремий тип руху пізніше.
    """

    axis: Vector3
    distance: float
    duration: float

    def __post_init__(self) -> None:
        if self.duration <= 0:
            raise ValueError("duration має бути додатним")

    def at(self, t: float) -> Transform:
        t_clamped = min(max(t, 0.0), self.duration)
        ux, uy, uz = _normalize(self.axis)
        displacement = self.distance * t_clamped / self.duration
        return Transform.translation_by((ux * displacement, uy * displacement, uz * displacement))


class RotationalMotion(Motion):
    """Спільна база для рухів, виражених кутом навколо однієї осі.

    `Rotation` задає вісь/точку опори напряму; `Geared` бере їх від
    `parent` і лише масштабує кут передавальним числом.
    """

    axis: Vector3
    origin: Point3

    @abstractmethod
    def angle_deg(self, t: float) -> float:
        """Кут повороту навколо `axis`/`origin` у момент `t`, градуси."""
        raise NotImplementedError

    def at(self, t: float) -> Transform:
        return Transform.rotation_about(self.axis, self.origin, self.angle_deg(t))


@dataclass
class Rotation(RotationalMotion):
    """Рівномірне обертання навколо осі (`axis`, через `origin`) зі швидкістю `rpm`."""

    axis: Vector3
    origin: Point3
    rpm: float

    def angle_deg(self, t: float) -> float:
        return math.degrees(rpm_to_rad_s(self.rpm) * t)


@dataclass
class Geared(RotationalMotion):
    """Обертання, кероване від `parent` через передавальне число `ratio`.

    Вісь — та сама, що й у `parent` (паралельні вали зубчастої пари
    завжди паралельні одна одній). Точка опори — `parent.origin` за
    замовчуванням (найпростіший співвісний випадок, напр. складена
    шестерня на спільному валу), АБО власна `own_origin`, якщо задана —
    потрібна для реальної зубчастої пари, де осі коліс рознесені на
    міжосьову відстань (`GearMesh.center_distance_mm`), а не збігаються.
    Від'ємний `ratio` — зворотний напрям обертання відносно `parent`.
    """

    parent: RotationalMotion
    ratio: float
    own_origin: Point3 | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.parent, RotationalMotion):
            raise TypeError("Geared.parent має бути обертальним рухом (Rotation або Geared)")

    @property
    def axis(self) -> Vector3:
        return self.parent.axis

    @property
    def origin(self) -> Point3:
        return self.own_origin if self.own_origin is not None else self.parent.origin

    def angle_deg(self, t: float) -> float:
        return self.parent.angle_deg(t) * self.ratio

    @classmethod
    def from_mesh(cls, parent: RotationalMotion, mesh: GearMesh, *, origin: Point3 | None = None) -> "Geared":
        """Будує `Geared` із передавального числа зубчастого зачеплення
        `mesh` (`kovadlo.transmission.GearMesh`) — замість підбирати
        `ratio` вручну. `parent` рахується як ведуче колесо зачеплення
        (`mesh.gear_a`), результат — веде́не (`mesh.gear_b`).

        `GearMesh.ratio` = n_вх/n_вих = z_b/z_a (конвенція `Transmission`
        — у скільки разів передача сповільнює обертання), а `Geared.ratio`
        МНОЖИТЬ кут `parent`, тобто діє у зворотному напрямку — звідси
        `ratio = -1/mesh.ratio = -z_a/z_b`; мінус — те саме зовнішнє
        зачеплення реверсує напрям, що й `GearMesh.output_rpm`.

        `origin` — власний центр веденого колеса, якщо осі не збігаються
        з `parent` (звичайний випадок: рознесені на `center_distance_mm`,
        а не той самий вал); без нього — співвісно з `parent`, як і
        для звичайного `Geared(parent=..., ratio=...)`.
        """
        return cls(parent=parent, ratio=-1.0 / mesh.ratio, own_origin=origin)


@dataclass
class Composite(Motion):
    """Кілька рухів на одній деталі, застосовуються послідовно (за порядком у списку).

    `at(t)` рахує трансформацію кожного руху окремо в момент `t` і
    комбінує їх через `Transform.then()` — перший елемент списку
    застосовується першим. Порядок впливає на результат: обертання й
    зсув не комутують.
    """

    motions: Sequence[Motion]

    def at(self, t: float) -> Transform:
        result = Transform.identity()
        for motion in self.motions:
            result = result.then(motion.at(t))
        return result


@dataclass
class MotionPlan:
    """Зіставляє деталі (за іменем) з їхніми рухами."""

    motions: dict[str, Motion]

    def state_at(self, t: float) -> dict[str, Transform]:
        """Трансформації всіх деталей плану в момент часу `t`."""
        return {name: motion.at(t) for name, motion in self.motions.items()}


def exploded_view_motion_plan(
    layers: Sequence[tuple[str, float]],
    *,
    direction: Vector3,
    gap_mm: float,
    duration: float = 2.0,
) -> MotionPlan:
    """`MotionPlan` для "розібраного" (exploded view) багатошарового
    пакета — стіни чи будь-якої іншої шаруватої конструкції.

    `layers` — `(ім'я, товщина_мм)` у порядку від першого шару до
    останнього (для стіни — від внутрішньої поверхні до зовнішньої,
    той самий порядок, що документує
    `kovadlo.insulation.layer_interface_temperatures_c`, і та сама
    форма даних, що вже зберігає `HeatState.wall_layers` у веб-шарі,
    лише товщина тут у мм, не в м). Ключ у `MotionPlan.motions` —
    `f"{індекс}:{ім'я}"`, а не саме `ім'я`: той самий матеріал може
    повторюватися (симетрична стіна тиньк-цегла-утеплювач-цегла-тиньк),
    і чисте ім'я дало б колізію ключів.

    Розліт — НЕ симетричний від середини, а від першого шару назовні
    (так стіна реально монтується і так її читають на розрізі): шар
    `i=0` лишається нерухомим, кожен наступний зсувається вздовж
    `direction` (має вказувати від пакета назовні, у бік від
    останнього шару) на `i * gap_mm` — тобто між БУДЬ-ЯКИМИ сусідніми
    шарами в розібраному стані рівно `gap_mm` вільного простору,
    незалежно від їхньої товщини. Товщина шарів у самій формулі зсуву
    не бере участі (вона однакова для будь-якої товщини — лише індекс
    і gap): `Linear` рахує зсув ВІД уже коректно (впритул, без
    нахлистів) зібраної позиції кожного шару, а її з кумулятивних
    товщин будує сторона виклику (`web/motion_state.py` для стіни) —
    звідси й гарантія, що жоден шар не перетне сусіда, хоч би які
    різні в них товщини.
    """
    if not layers:
        raise ValueError("Список шарів не може бути порожнім")
    if gap_mm < 0:
        raise ValueError("Проміжок між шарами (gap_mm) не може бути від'ємним")

    motions: dict[str, Motion] = {}
    for i, (name, thickness_mm) in enumerate(layers):
        if thickness_mm <= 0:
            raise ValueError(f"Товщина шару «{name}» має бути додатною")
        motions[f"{i}:{name}"] = Linear(axis=direction, distance=i * gap_mm, duration=duration)
    return MotionPlan(motions=motions)
