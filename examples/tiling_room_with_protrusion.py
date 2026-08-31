"""
Приклад: покриття плиткою підлоги кімнати з виступом (модуль 2).

Бере кімнату з `examples/room_with_protrusion.py` (модуль 1) і рахує
покриття підлоги плиткою 600x600 мм із фугою 2 мм. Лише розрахунок і
текстовий вивід — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.tiling_room_with_protrusion
"""

from __future__ import annotations

from examples.room_with_protrusion import build_room_with_protrusion
from kovadlo import Grout, Point, RowOffset, Surface, Tile, TileLayout, calculate_tiling, format_report

TILE = Tile(width=600, height=600, name="Керамограніт «Граніт сірий»", color="сірий")
GROUT = Grout(width_mm=2.0, color="сірий")


def main() -> None:
    room = build_room_with_protrusion()
    surface = Surface.from_room_floor(room)
    layout = TileLayout(start=Point(0, 0), row_offset=RowOffset.NONE, angle=0)

    result = calculate_tiling(surface, TILE, GROUT, layout, tiles_per_package=4)

    print(format_report(surface, TILE, GROUT, layout, result))


if __name__ == "__main__":
    main()
