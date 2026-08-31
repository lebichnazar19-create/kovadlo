"""
Приклад: електропроводка кімнати з виступом (модуль 4).

Використовує ту саму кімнату, що й `examples/room_with_protrusion.py`
(модуль 1), розміщує точки споживання, групує їх у кола, будує траси
кабелю від щитка (з прив'язкою кутів до 90°) і друкує звіт із
розрахунком кожного кола та специфікацією кабелю на закупівлю.

Лише розрахунок і текстовий вивід — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.wiring_apartment
"""

from __future__ import annotations

from kovadlo import (
    ConsumptionPoint,
    Group,
    Point,
    PointKind,
    PhaseType,
    WiringPlan,
    build_route,
    format_wiring_report,
)

# Щиток — біля входу, на стіні (0,0)-(0,3000) з прикладу модуля 1.
PANEL_POSITION = Point(100, 2900)


def build_plan() -> WiringPlan:
    panel = ConsumptionPoint(name="Щиток", kind=PointKind.PANEL, position=PANEL_POSITION)

    # --- Освітлення -------------------------------------------------------
    light_main = ConsumptionPoint(name="Св. основна кімната", kind=PointKind.LIGHT, position=Point(2000, 1500))
    light_protrusion = ConsumptionPoint(name="Св. виступ", kind=PointKind.LIGHT, position=Point(4750, 2500))
    switch_main = ConsumptionPoint(name="Вимикач при вході", kind=PointKind.SWITCH, position=Point(2000, 3000))

    lighting_group = Group(
        name="Освітлення",
        phase=PhaseType.SINGLE,
        points=[light_main, light_protrusion, switch_main],
        routes={
            # траса по стіні вниз, потім по стелі до центру кімнати
            light_main.name: build_route(PANEL_POSITION, [Point(100, 1500), Point(2000, 1500)]),
            light_protrusion.name: build_route(PANEL_POSITION, [Point(100, 2500), Point(4750, 2500)]),
            switch_main.name: build_route(PANEL_POSITION, [Point(100, 3000), Point(2000, 3000)]),
        },
    )

    # --- Розетки ------------------------------------------------------------
    socket_1 = ConsumptionPoint(name="Розетка 1", kind=PointKind.SOCKET, position=Point(3800, 100))
    socket_2 = ConsumptionPoint(name="Розетка 2", kind=PointKind.SOCKET, position=Point(100, 1500))
    socket_3 = ConsumptionPoint(name="Розетка 3 (виступ)", kind=PointKind.SOCKET, position=Point(5300, 2200))

    sockets_group = Group(
        name="Розетки",
        phase=PhaseType.SINGLE,
        points=[socket_1, socket_2, socket_3],
        routes={
            socket_1.name: build_route(PANEL_POSITION, [Point(100, 100), Point(3800, 100)]),
            socket_2.name: build_route(PANEL_POSITION, [Point(100, 1500)]),
            socket_3.name: build_route(PANEL_POSITION, [Point(100, 2200), Point(5300, 2200)]),
        },
        min_cross_section_mm2=2.5,  # силове коло з розетками — поширена практика
    )

    # --- Плита (трифазна) ----------------------------------------------------
    stove = ConsumptionPoint(name="Плита", kind=PointKind.STOVE, position=Point(3900, 3000))
    stove_group = Group(
        name="Плита",
        phase=PhaseType.THREE,
        points=[stove],
        routes={stove.name: build_route(PANEL_POSITION, [Point(100, 3000), Point(3900, 3000)])},
        min_cross_section_mm2=6.0,  # практика для стаціонарної потужної плити
    )

    # --- Бойлер ------------------------------------------------------------
    boiler = ConsumptionPoint(name="Бойлер", kind=PointKind.BOILER, position=Point(5300, 2900))
    boiler_group = Group(
        name="Бойлер",
        phase=PhaseType.SINGLE,
        points=[boiler],
        routes={boiler.name: build_route(PANEL_POSITION, [Point(5300, 2900)])},
        min_cross_section_mm2=2.5,
    )

    return WiringPlan(panel=panel, groups=[lighting_group, sockets_group, stove_group, boiler_group])


def main() -> None:
    plan = build_plan()
    print(format_wiring_report(plan))


if __name__ == "__main__":
    main()
