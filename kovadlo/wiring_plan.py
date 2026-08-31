"""План електропроводки: щиток + групи, зведений текстовий звіт."""

from __future__ import annotations

from dataclasses import dataclass, field

from .electrical_group import Group, GroupCalculation, calculate_group
from .electrical_norms import VOLTAGE_V
from .electrical_point import ConsumptionPoint, PointKind


@dataclass
class WiringPlan:
    """План електропроводки квартири/будинку: щиток (як точка на плані —
    `PointKind.PANEL`) + список груп."""

    panel: ConsumptionPoint
    groups: list[Group] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.panel.kind is not PointKind.PANEL:
            raise ValueError("panel.kind має бути PointKind.PANEL")
        if not self.groups:
            raise ValueError("План має містити хоча б одну групу")

    def calculations(self) -> list[GroupCalculation]:
        """Розрахунок кожної групи плану (номінал автомата, переріз, ПЗВ)."""
        return [calculate_group(group) for group in self.groups]


def format_wiring_report(plan: WiringPlan) -> str:
    """Текстовий звіт: розрахунок по групах + перелік кабелів
    (специфікація на закупівлю). Лише текст — жодної графіки."""
    lines: list[str] = [
        f"Щиток «{plan.panel.name}» — позиція ({plan.panel.position.x:.0f}, {plan.panel.position.z:.0f}) мм",
        "",
    ]
    calcs = plan.calculations()

    for group, calc in zip(plan.groups, calcs):
        lines.append(f"Група «{group.name}» — {group.phase.value}, {VOLTAGE_V[group.phase]:.0f} В")
        for point in group.points:
            lines.append(f"    - {point.name} ({point.kind.value}, {point.power_w:.0f} Вт)")
        lines.extend(
            [
                f"  Сумарна потужність:       {calc.total_power_w:.0f} Вт",
                f"  Розрахунковий струм:      {calc.design_current_a:.2f} А",
                f"  Найдовша траса:           {calc.critical_route_length_m:.2f} м",
                f"  Автоматичний вимикач:     {calc.breaker_rating_a:.0f} А",
                f"  Переріз жили (мідь):      {calc.cross_section_mm2:.1f} мм²",
                (
                    f"  Падіння напруги:          {calc.voltage_drop_percent:.2f}% "
                    f"(допустимо ≤ {group.max_voltage_drop_percent:.0f}%)"
                ),
                (
                    f"  ПЗВ/дифавтомат:           {'ПОТРІБЕН' if calc.rcd_required else 'не обов’язковий'} "
                    f"— {calc.rcd_note}"
                ),
                f"  Кабелю на групу (з запасом на підключення): {calc.total_cable_length_m:.2f} м",
                "",
            ]
        )

    lines.append("Специфікація кабелів на закупівлю:")
    # між колонками — явний пробіл-розділювач, а не лише ширина поля: так
    # довша за ширину поля назва точки/групи не "заїжджає" в сусідню колонку.
    header = f"{'Точка':<24} {'Група':<16} {'Переріз, мм²':>12} {'Довжина із запасом, м':>22}"
    lines.append(header)
    lines.append("-" * len(header))

    total_by_section: dict[float, float] = {}
    for group, calc in zip(plan.groups, calcs):
        for point_name, route in group.routes.items():
            length_with_allowance = route.length_m + group.connection_allowance_m
            lines.append(
                f"{point_name:<24} {group.name:<16} {calc.cross_section_mm2:>12.1f} {length_with_allowance:>22.2f}"
            )
            total_by_section[calc.cross_section_mm2] = (
                total_by_section.get(calc.cross_section_mm2, 0.0) + length_with_allowance
            )

    lines.append("")
    lines.append("Разом кабелю за перерізом (округлення до бухти — окремо, на закупівлі):")
    for section, total_len in sorted(total_by_section.items()):
        lines.append(f"  {section:.1f} мм²: {total_len:.2f} м")

    return "\n".join(lines)
