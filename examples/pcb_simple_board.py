"""
Приклад: проста друкована плата (модуль 6).

Мікросхема (DIP-8) + два резистори + світлодіод + роз'єм живлення:
роз'єм живить мікросхему, вихід мікросхеми через резистор запалює
світлодіод, на вхід мікросхеми підтягнутий резистор до VCC.

Ролі виводів мікросхеми (VCC/GND/OUT/IN) тут — умовна ілюстративна
розкладка для прикладу, а НЕ розпіновка якоїсь конкретної реальної
мікросхеми за даташитом.

Лише розрахунок і текстовий вивід — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.pcb_simple_board
"""

from __future__ import annotations

from kovadlo import (
    Board,
    Component,
    ComponentKind,
    ComponentUnit,
    Layer,
    Net,
    NetKind,
    Netlist,
    PinRef,
    Placement,
    Point,
    Track,
    Via,
    build_track,
    connector_footprint,
    dip_footprint,
    format_board_report,
    two_pin_footprint,
)


def demo_snap() -> None:
    """Демонстрація прив'язки кута доріжки до кроку 45°."""
    start = Point(0, 0)
    rough_target = Point(9.6, 10.3)  # неточно наведений курсор, майже 45°
    track = build_track(start, [rough_target], width_mm=0.3, layer=Layer.TOP, net="DEMO", snap_step=45.0)
    end = track.points[-1]
    print("Прив'язка кута доріжки (snap):")
    print(f"  ціль без прив'язки:  ({rough_target.x:.2f}, {rough_target.z:.2f})")
    print(f"  точка після прив'язки: ({end.x:.2f}, {end.z:.2f}) — кут точно 45°")
    print()


def _manhattan_track(a: Point, b: Point, width_mm: float, layer: Layer, net: str) -> Track:
    """Г-подібна доріжка (горизонталь + вертикаль) від `a` до `b`.

    Обидва сегменти — точно 0°/90°, тобто кратні 45°, і при цьому доріжка
    гарантовано влучає точно в другий вивід (на відміну від `build_track`
    зі сніпом, який зберігає відстань, а не кінцеву точку)."""
    bend = Point(b.x, a.z)
    points = [a, bend, b] if bend != a and bend != b else [a, b]
    return Track(points=points, width_mm=width_mm, layer=layer, net=net)


def build_board_and_netlist() -> tuple[Board, Netlist]:
    # --- компоненти ---------------------------------------------------
    j1 = Component("J1", "Роз'єм живлення", ComponentKind.CONNECTOR, connector_footprint(2, pitch=2.54))
    u1 = Component("U1", "Логічна мікросхема", ComponentKind.IC, dip_footprint(8))
    r1 = Component("R1", "Резистор (обмежувальний)", ComponentKind.RESISTOR, two_pin_footprint("THT-2", spacing=10.0), 330, ComponentUnit.OHM)
    r2 = Component("R2", "Резистор (підтяжка)", ComponentKind.RESISTOR, two_pin_footprint("THT-2", spacing=8.0), 10_000, ComponentUnit.OHM)
    d1 = Component("D1", "Світлодіод", ComponentKind.LED, two_pin_footprint("LED-T1", spacing=2.5))

    components = {"J1": j1, "U1": u1, "R1": r1, "R2": r2, "D1": d1}

    # --- плата й розміщення --------------------------------------------
    board = Board(name="Проста плата з ІМС", contour=[Point(0, 0), Point(50, 0), Point(50, 35), Point(0, 35)])
    board.placements["J1"] = Placement(component=j1, position=Point(2, 15))
    board.placements["U1"] = Placement(component=u1, position=Point(15, 10))
    board.placements["R1"] = Placement(component=r1, position=Point(30, 20))
    board.placements["R2"] = Placement(component=r2, position=Point(5, 28))
    board.placements["D1"] = Placement(component=d1, position=Point(44, 10))

    # умовні ролі виводів U1 (DIP-8): 8=VCC, 4=GND, 3=OUT, 2=IN
    j1_pos, u1_pos = board.placements["J1"], board.placements["U1"]
    r1_pos, r2_pos, d1_pos = board.placements["R1"], board.placements["R2"], board.placements["D1"]

    # --- нетлист (схема) -------------------------------------------------
    netlist = Netlist(
        components=components,
        nets=[
            Net(
                "VCC",
                NetKind.POWER,
                [PinRef("J1", 1), PinRef("U1", 8), PinRef("R2", 1)],
                voltage_v=5.0,
            ),
            Net(
                "GND",
                NetKind.GROUND,
                [PinRef("J1", 2), PinRef("U1", 4), PinRef("D1", 2)],
                voltage_v=0.0,
            ),
            Net("OUT", NetKind.SIGNAL, [PinRef("U1", 3), PinRef("R1", 1)]),
            Net("LED_A", NetKind.SIGNAL, [PinRef("R1", 2), PinRef("D1", 1)]),
            Net("IN", NetKind.SIGNAL, [PinRef("U1", 2), PinRef("R2", 2)]),
        ],
    )

    # --- доріжки (Г-подібні, кожен сегмент кратний 45°) -------------------
    # GND і IN навмисно на нижньому шарі, а не на верхньому разом з рештою —
    # інакше вони перетиналися б із VCC/OUT на тому самому шарі без зазору.
    def pin(ref: str, number: int) -> Point:
        return board.pin_position(ref, number)

    board.tracks.append(_manhattan_track(pin("J1", 1), pin("U1", 8), 0.5, Layer.TOP, "VCC"))
    board.tracks.append(_manhattan_track(pin("U1", 8), pin("R2", 1), 0.5, Layer.TOP, "VCC"))
    board.tracks.append(_manhattan_track(pin("J1", 2), pin("U1", 4), 0.5, Layer.BOTTOM, "GND"))
    board.tracks.append(_manhattan_track(pin("U1", 4), pin("D1", 2), 0.5, Layer.BOTTOM, "GND"))
    board.tracks.append(_manhattan_track(pin("R1", 2), pin("D1", 1), 0.4, Layer.TOP, "LED_A"))
    board.tracks.append(_manhattan_track(pin("U1", 2), pin("R2", 2), 0.3, Layer.BOTTOM, "IN"))

    # ланцюг OUT — демонстрація перехідного отвору: перший відрізок на
    # верхньому шарі, перехід на нижній через via, другий відрізок на
    # нижньому шарі (справжня зміна шару посеред траси, а не на виводі).
    out_start, out_end = pin("U1", 3), pin("R1", 1)
    out_bend = Point(out_end.x, out_start.z)
    board.tracks.append(Track(points=[out_start, out_bend], width_mm=0.4, layer=Layer.TOP, net="OUT"))
    board.tracks.append(Track(points=[out_bend, out_end], width_mm=0.4, layer=Layer.BOTTOM, net="OUT"))
    board.vias.append(Via(position=out_bend, net="OUT", drill_diameter_mm=0.3, pad_diameter_mm=0.6))

    return board, netlist


def main() -> None:
    demo_snap()

    board, netlist = build_board_and_netlist()

    # орієнтовні очікувані струми ланцюгів для перевірки ширини за IPC-2221
    net_currents_a = {"VCC": 0.015, "GND": 0.015, "OUT": 0.010, "LED_A": 0.010, "IN": 0.0001}

    print(format_board_report(board, netlist, net_currents_a=net_currents_a))
    print()
    print(
        "Примітка: цю плату розведено вручну, без автотрасувальника, і "
        "перевірка зазорів вище свідомо лишена як є — вона показує "
        "справжній конфлікт (GND зустрічається з IN/OUT у тісному місці "
        "біля роз'єму) саме такий, який DRC-перевірка й повинна ловити "
        "до виготовлення плати. Реальний наступний крок — перетрасувати "
        "ці ділянки чи додати ще один via, а не ігнорувати попередження."
    )


if __name__ == "__main__":
    main()
