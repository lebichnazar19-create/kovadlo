"""Кімната: полігональний контур + стіни."""

from __future__ import annotations

from dataclasses import dataclass, field

from .geometry import MM2_PER_M2, Point, polygon_area, polygon_perimeter, snap_point
from .materials import Material
from .wall import Wall


@dataclass
class Room:
    """Кімната: замкнений полігональний контур довільної форми + список стін.

    Контур замикається автоматично — останню точку з'єднано з першою.
    `walls` не обов'язково відповідають один в один ребрам контуру: їх
    можна будувати вручну (наприклад, з різною товщиною/матеріалом на
    різних ділянках), або згенерувати автоматично через `from_contour`.
    """

    contour: list[Point]
    walls: list[Wall] = field(default_factory=list)
    name: str = ""

    def __post_init__(self) -> None:
        if len(self.contour) < 3:
            raise ValueError("Контур кімнати має містити щонайменше 3 точки")

    @classmethod
    def from_contour(
        cls,
        contour: list[Point],
        *,
        height: float,
        thickness: float,
        material: Material,
        name: str = "",
        snap: bool = True,
        snap_step: float = 15.0,
    ) -> "Room":
        """Будує кімнату з контуру, створюючи по стіні на кожному ребрі.

        Якщо `snap=True`, кожна наступна точка контуру (крім першої)
        прив'язується до напрямку, кратного `snap_step` градусів відносно
        попередньої вже прив'язаної точки — так само, як прилипає кут під
        час малювання стіни в CAD-редакторі. Зверніть увагу: прив'язується
        послідовність намальованих ребер, а не замикаюче ребро "останній
        пункт → перший" — воно яке вийде, таке й буде, щоб контур
        гарантовано замкнувся саме в стартовій точці.
        """
        points = list(contour)
        if snap and len(points) > 1:
            snapped = [points[0]]
            for point in points[1:]:
                snapped.append(snap_point(snapped[-1], point, snap_step))
            points = snapped

        n = len(points)
        walls = [
            Wall.create(
                start=points[i],
                end=points[(i + 1) % n],
                height=height,
                thickness=thickness,
                material=material,
            )
            for i in range(n)
        ]
        return cls(contour=points, walls=walls, name=name)

    @property
    def floor_area_mm2(self) -> float:
        """Площа підлоги, мм²."""
        return polygon_area(self.contour)

    @property
    def floor_area_m2(self) -> float:
        """Площа підлоги, м²."""
        return self.floor_area_mm2 / MM2_PER_M2

    @property
    def perimeter_mm(self) -> float:
        """Периметр контуру кімнати, мм."""
        return polygon_perimeter(self.contour)

    def wall_areas_m2(self) -> list[float]:
        """Площа кожної стіни окремо, м²."""
        return [wall.area_m2 for wall in self.walls]

    @property
    def total_wall_area_m2(self) -> float:
        """Сумарна площа всіх стін кімнати, м²."""
        return sum(self.wall_areas_m2())
