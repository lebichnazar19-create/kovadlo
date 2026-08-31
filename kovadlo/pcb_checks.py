"""
Перевірки плати:

- ratsnest — чи кожне з'єднання нетлиста (модуль схеми) фізично
  реалізоване доріжками/перехідними отворами на платі;
- мінімальні зазори між доріжками різних ланцюгів (IPC-2221, див.
  `pcb_norms.py`).

Тут-таки — невеликі геометричні хелпери (відстань точка-відрізок,
перетин відрізків, відстань відрізок-відрізок), яких немає в ядрі
(модуль 1 має лише точку, полігони й відсікання опуклих полігонів, а
не відстань між відрізками) — вони специфічні для перевірки плати, тож
живуть тут, а не в `geometry.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations

from .geometry import Point
from .pcb_board import Board, Track
from .pcb_netlist import Netlist, PinRef
from .pcb_norms import Layer, min_clearance_mm

_POSITION_TOLERANCE_MM = 1e-3  # точки, що відрізняються менш ніж на це, вважаються тим самим вузлом


class _UnionFind:
    """Система неперетинних множин — для перевірки зв'язності графа."""

    def __init__(self) -> None:
        self._parent: dict[object, object] = {}

    def find(self, x: object) -> object:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: object, b: object) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb

    def connected(self, a: object, b: object) -> bool:
        return self.find(a) == self.find(b)


def _node(point: Point, layer: Layer) -> tuple[float, float, Layer]:
    """Ключ вузла графа зв'язності: округлення до мкм прибирає похибки
    округлення з плаваючою комою, лишаючи справжні (більші) розриви."""
    return (round(point.x, 3), round(point.z, 3), layer)


@dataclass
class RatsnestGap:
    """Незʼєднана пара виводів одного ланцюга схеми — доріжки/перехідні
    отвори не реалізують це з'єднання нетлиста."""

    net: str
    pin_a: PinRef
    pin_b: PinRef

    def __str__(self) -> str:
        return f"{self.net}: {self.pin_a} не з'єднано з {self.pin_b}"


def unrouted_connections(netlist: Netlist, board: Board) -> list[RatsnestGap]:
    """Перевіряє, чи кожен ланцюг нетлиста фізично реалізований на платі
    (ratsnest). Для компонентів, ще не розміщених на платі, перевірку
    пропущено (немає фізичних координат для їхніх виводів).

    Спрощення: вивід компонента вважається доступним з обох шарів плати
    (поводиться як неявний перехідний отвір у своїй точці) — окремого
    моделювання "з якого боку впаяний вивід" тут немає.

    Прогалини повертаються відносно ПЕРШОГО розміщеного виводу кожного
    ланцюга (діагностичний список, а не мінімальний набір відсутніх
    з'єднань) — цього достатньо, щоб побачити, які виводи лишились
    не приєднаними.
    """
    gaps: list[RatsnestGap] = []
    for net in netlist.nets:
        placed_pins = [p for p in net.pins if p.component in board.placements]
        if len(placed_pins) < 2:
            continue  # нема що з'єднувати доріжкою (0 чи 1 розміщений вивід)

        uf = _UnionFind()
        for track in board.tracks_on_net(net.name):
            for a, b in track.segments():
                uf.union(_node(a, track.layer), _node(b, track.layer))
        for via in board.vias_on_net(net.name):
            uf.union(_node(via.position, Layer.TOP), _node(via.position, Layer.BOTTOM))

        def pin_key(pin_ref: PinRef) -> tuple[str, str, int]:
            return ("pin", pin_ref.component, pin_ref.pin)

        for pin_ref in placed_pins:
            pos = board.pin_position(pin_ref.component, pin_ref.pin)
            key = pin_key(pin_ref)
            uf.union(key, _node(pos, Layer.TOP))
            uf.union(key, _node(pos, Layer.BOTTOM))

        reference = placed_pins[0]
        for other in placed_pins[1:]:
            if not uf.connected(pin_key(reference), pin_key(other)):
                gaps.append(RatsnestGap(net=net.name, pin_a=reference, pin_b=other))
    return gaps


# --- геометричні хелпери для перевірки зазорів -----------------------------


def _point_segment_distance(p: Point, a: Point, b: Point) -> float:
    abx, abz = b.x - a.x, b.z - a.z
    len2 = abx * abx + abz * abz
    if len2 == 0:
        return p.distance_to(a)
    t = ((p.x - a.x) * abx + (p.z - a.z) * abz) / len2
    t = max(0.0, min(1.0, t))
    closest = Point(a.x + t * abx, a.z + t * abz)
    return p.distance_to(closest)


def _orientation(a: Point, b: Point, c: Point) -> float:
    return (b.x - a.x) * (c.z - a.z) - (b.z - a.z) * (c.x - a.x)


def _on_segment(a: Point, b: Point, c: Point) -> bool:
    return min(a.x, b.x) - 1e-9 <= c.x <= max(a.x, b.x) + 1e-9 and min(a.z, b.z) - 1e-9 <= c.z <= max(a.z, b.z) + 1e-9


def _segments_intersect(a1: Point, a2: Point, b1: Point, b2: Point) -> bool:
    d1, d2 = _orientation(b1, b2, a1), _orientation(b1, b2, a2)
    d3, d4 = _orientation(a1, a2, b1), _orientation(a1, a2, b2)
    if ((d1 > 0) != (d2 > 0)) and d1 != 0 and d2 != 0 and ((d3 > 0) != (d4 > 0)) and d3 != 0 and d4 != 0:
        return True
    if d1 == 0 and _on_segment(b1, b2, a1):
        return True
    if d2 == 0 and _on_segment(b1, b2, a2):
        return True
    if d3 == 0 and _on_segment(a1, a2, b1):
        return True
    if d4 == 0 and _on_segment(a1, a2, b2):
        return True
    return False


def _segment_distance(a1: Point, a2: Point, b1: Point, b2: Point) -> float:
    """Найкоротша відстань між двома відрізками, мм."""
    if _segments_intersect(a1, a2, b1, b2):
        return 0.0
    return min(
        _point_segment_distance(a1, b1, b2),
        _point_segment_distance(a2, b1, b2),
        _point_segment_distance(b1, a1, a2),
        _point_segment_distance(b2, a1, a2),
    )


def _track_distance_mm(track_a: Track, track_b: Track) -> float:
    """Найкоротша відстань між двома доріжками (мінімум по всіх парах відрізків)."""
    return min(
        _segment_distance(a1, a2, b1, b2) for a1, a2 in track_a.segments() for b1, b2 in track_b.segments()
    )


@dataclass
class ClearanceViolation:
    """Порушення мінімального зазору між доріжками двох різних ланцюгів."""

    net_a: str
    net_b: str
    distance_mm: float
    required_mm: float

    def __str__(self) -> str:
        return f"{self.net_a} / {self.net_b}: зазор {self.distance_mm:.3f} мм < потрібних {self.required_mm:.3f} мм"


def clearance_violations(board: Board, netlist: Netlist, *, default_voltage_v: float = 5.0) -> list[ClearanceViolation]:
    """Перевіряє мінімальний зазор (IPC-2221, `min_clearance_mm`) між
    доріжками різних ланцюгів на ОДНОМУ й тому ж шарі (доріжки на різних
    шарах фізично не заважають одна одній).

    Потрібна напруга різниці потенціалів між ланцюгами: якщо в обох
    ланцюгів задано `Net.voltage_v`, використовується їхня різниця;
    інакше — консервативне значення `default_voltage_v`.
    """
    voltage_by_net = {net.name: net.voltage_v for net in netlist.nets}
    worst_by_pair: dict[frozenset[str], float] = {}

    for track_a, track_b in combinations(board.tracks, 2):
        if track_a.net == track_b.net or track_a.layer != track_b.layer:
            continue
        pair = frozenset({track_a.net, track_b.net})
        distance = _track_distance_mm(track_a, track_b)
        if pair not in worst_by_pair or distance < worst_by_pair[pair]:
            worst_by_pair[pair] = distance

    violations: list[ClearanceViolation] = []
    for pair, distance in worst_by_pair.items():
        net_a, net_b = sorted(pair)
        va, vb = voltage_by_net.get(net_a), voltage_by_net.get(net_b)
        voltage_diff = abs(va - vb) if va is not None and vb is not None else default_voltage_v
        required = min_clearance_mm(voltage_diff)
        if distance < required:
            violations.append(ClearanceViolation(net_a=net_a, net_b=net_b, distance_mm=distance, required_mm=required))
    return violations
