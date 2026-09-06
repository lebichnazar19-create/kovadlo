"""
Каталог кріплення: типова номенклатура (гвинти, болти, гайки, шайби,
дюбелі, петлі, доводжувачі, магніти, заглушки, ручки, інструмент) —
довідник для специфікації складання (доповнює BOM деталей, модуль
`bom.py`, який рахує самі несучі елементи, а не крепіж до них).

Ядро без графіки, лише stdlib.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class FastenerKind(Enum):
    """Тип кріплення/фурнітури."""

    SCREW = "гвинт"
    BOLT = "болт"
    NUT = "гайка"
    WASHER = "шайба"
    DOWEL = "дюбель"
    HINGE = "петля"
    DAMPER = "доводжувач"
    MAGNET = "магніт"
    CAP = "заглушка"
    HANDLE = "ручка"
    TOOL = "інструмент"


@dataclass(frozen=True)
class Fastener:
    """Одна позиція каталогу: код, назва, розмір, тип.

    `code` — унікальний ключ каталогу (напр. "G24"), за яким на
    кріплення посилаються специфікації складання — той самий підхід
    "посилання за іменем", що й у базі матеріалів (модуль 7).
    """

    code: str
    name: str
    size: str
    kind: FastenerKind

    def __post_init__(self) -> None:
        if not self.code:
            raise ValueError("Код кріплення не може бути порожнім")


@dataclass(frozen=True)
class FastenerUsage:
    """Використання кріплення в складанні: яке (`fastener`) і скільки (`count`)."""

    fastener: Fastener
    count: int

    def __post_init__(self) -> None:
        if self.count <= 0:
            raise ValueError("Кількість кріплення має бути додатною")


@dataclass
class FastenerCatalog:
    """Каталог кріплення: записи, унікальні за `code` (той самий
    прийом, що й `MaterialDatabase` для назв матеріалів, модуль 7)."""

    fasteners: list[Fastener] = field(default_factory=list)

    def __post_init__(self) -> None:
        codes = [f.code for f in self.fasteners]
        duplicates = sorted({c for c in codes if codes.count(c) > 1})
        if duplicates:
            raise ValueError(f"Дублікати кодів кріплення в каталозі: {', '.join(duplicates)}")

    def add(self, fastener: Fastener) -> None:
        """Додає кріплення в каталог; помилка, якщо код уже зайнятий."""
        if self.find_by_code(fastener.code) is not None:
            raise ValueError(f"Код «{fastener.code}» вже є в каталозі")
        self.fasteners.append(fastener)

    def find_by_code(self, code: str) -> Fastener | None:
        """Пошук за точним кодом каталогу."""
        for fastener in self.fasteners:
            if fastener.code == code:
                return fastener
        return None

    def summary(self, usages: Iterable[FastenerUsage]) -> list[FastenerUsage]:
        """Об'єднує `usages` з однаковим кодом кріплення в одну позицію
        із сумарною кількістю; порядок — за першою появою коду в
        `usages` (стабільно, через звичайний dict). Кожен код має бути
        в каталозі — інакше `ValueError` (специфікація не має посилатись
        на невідоме каталогу кріплення)."""
        totals: dict[str, int] = {}
        for usage in usages:
            code = usage.fastener.code
            if self.find_by_code(code) is None:
                raise ValueError(f"Кріплення з кодом «{code}» немає в каталозі")
            totals[code] = totals.get(code, 0) + usage.count

        return [FastenerUsage(fastener=self.find_by_code(code), count=count) for code, count in totals.items()]
