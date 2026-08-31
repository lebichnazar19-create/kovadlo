"""Зведений текстовий звіт по платі: BOM, перевірка схеми, доріжки, ratsnest, зазори."""

from __future__ import annotations

from .pcb_board import Board
from .pcb_checks import clearance_violations, unrouted_connections
from .pcb_netlist import Netlist
from .pcb_norms import (
    DEFAULT_TEMPERATURE_RISE_C,
    required_track_width_mm,
    track_resistance_ohm,
    track_voltage_drop_v,
)


def _bom_lines(netlist: Netlist) -> list[str]:
    """Специфікація компонентів на закупівлю: однакові деталі згруповані
    (тип, назва, номінал, посадкове місце) з кількістю та позначеннями."""
    groups: dict[tuple[str, str, str, str], list[str]] = {}
    for ref, component in netlist.components.items():
        key = (component.kind.value, component.name, component.value_str(), component.footprint.name)
        groups.setdefault(key, []).append(ref)

    lines: list[str] = []
    for (kind, name, value, footprint), refs in sorted(groups.items()):
        refs_str = ", ".join(sorted(refs))
        lines.append(f"  {len(refs)} x {name} ({kind}), {value}, {footprint} — {refs_str}")
    return lines


def format_board_report(
    board: Board,
    netlist: Netlist,
    *,
    net_currents_a: dict[str, float] | None = None,
    temperature_rise_c: float = DEFAULT_TEMPERATURE_RISE_C,
    default_voltage_v: float = 5.0,
) -> str:
    """Формує текстовий звіт по платі. Лише текст — жодної графіки.

    `net_currents_a` — очікуваний струм кожного ланцюга, А (якщо відомий);
    для ланцюгів без зазначеного струму перевірка ширини доріжки за
    IPC-2221 пропускається (лишається лише геометрія й опір).
    """
    net_currents_a = net_currents_a or {}
    lines: list[str] = []

    lines.append(f"Плата «{board.name}»" if board.name else "Плата")
    lines.append(f"  площа: {board.area_mm2 / 100:.2f} см², периметр: {board.perimeter_mm / 10:.1f} см")
    lines.append("")

    lines.append("Специфікація компонентів (BOM):")
    lines.extend(_bom_lines(netlist))
    lines.append("")

    lines.append("Перевірка схеми:")
    dangling = netlist.dangling_pins()
    if dangling:
        lines.append(f"  Висячі виводи ({len(dangling)}):")
        for pin_ref in dangling:
            lines.append(f"    - {pin_ref}")
    else:
        lines.append("  Висячих виводів немає.")

    pg_shorts = netlist.power_ground_shorts()
    if pg_shorts:
        lines.append(f"  КОРОТКЕ ЗАМИКАННЯ живлення на землю ({len(pg_shorts)}):")
        for short in pg_shorts:
            lines.append(f"    - {short}")
    else:
        other_shorts = [s for s in netlist.short_circuits() if s not in pg_shorts]
        if other_shorts:
            lines.append(f"  Інші конфлікти ланцюгів ({len(other_shorts)}):")
            for short in other_shorts:
                lines.append(f"    - {short}")
        else:
            lines.append("  Коротких замикань не знайдено.")
    lines.append("")

    lines.append("Доріжки:")
    if not board.tracks:
        lines.append("  Доріжок ще немає.")
    else:
        for i, track in enumerate(board.tracks, start=1):
            resistance_ohm = track_resistance_ohm(track.length_mm, track.width_mm)
            line = (
                f"  {i}. ланцюг «{track.net}», шар {track.layer.value}, "
                f"довжина {track.length_mm:.1f} мм, ширина {track.width_mm:.2f} мм, "
                f"опір {resistance_ohm * 1000:.1f} мОм"
            )
            current_a = net_currents_a.get(track.net)
            if current_a is not None:
                required_mm = required_track_width_mm(current_a, temperature_rise_c=temperature_rise_c)
                drop_v = track_voltage_drop_v(current_a, track.length_mm, track.width_mm)
                verdict = "OK" if track.width_mm >= required_mm else "ЗАВУЗЬКА"
                line += (
                    f", при {current_a:.2f} А потрібно ≥{required_mm:.2f} мм ({verdict}), "
                    f"падіння напруги {drop_v * 1000:.1f} мВ"
                )
            lines.append(line)
    lines.append("")

    lines.append("Ratsnest (з'єднання нетлиста ↔ доріжки):")
    gaps = unrouted_connections(netlist, board)
    if gaps:
        for gap in gaps:
            lines.append(f"  - {gap}")
    else:
        lines.append("  Усі з'єднання нетлиста реалізовано доріжками.")
    lines.append("")

    lines.append("Зазори між доріжками (IPC-2221, орієнтовно — див. застереження в pcb_norms.py):")
    violations = clearance_violations(board, netlist, default_voltage_v=default_voltage_v)
    if violations:
        for violation in violations:
            lines.append(f"  - {violation}")
    else:
        lines.append("  Порушень мінімальних зазорів не знайдено.")

    return "\n".join(lines)
