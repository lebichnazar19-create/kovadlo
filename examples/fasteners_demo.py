"""
Приклад: каталог кріплення (`kovadlo/fasteners.py`) — повний комплект
фурнітури шафи для смітників зі STEELMAN (той самий каркас, що й у
`examples/bom_demo.py`: профільна труба 40×40×2 мм на 4 вертикальні
рамки + 2 донні рамки).

Показує `FastenerCatalog.summary`: специфікація складання (`usages`)
формується по вузлах збирання (як у реальному кресленні — скільки
кожного кріплення пішло на кожен вузол), а `summary` зводить її до
підсумкової кількості на кожен код каталогу — без цього довелось би
рахувати вручну, скільки G24 пішло сумарно на всі 4 вертикальні рамки.

Лише розрахунок і текстовий вивід — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.fasteners_demo
"""

from __future__ import annotations

from kovadlo import Fastener, FastenerCatalog, FastenerKind, FastenerUsage

# --- каталог: усе кріплення, яке взагалі трапляється в комплекті -----------

CATALOG = FastenerCatalog(
    [
        Fastener(code="G24", name="Гвинт з внутрішнім шестигранником", size="M6×16", kind=FastenerKind.SCREW),
        Fastener(code="G26", name="Саморіз для ДСП/металу", size="4.0×30", kind=FastenerKind.SCREW),
        Fastener(code="G28", name="Гвинт кріплення завіси", size="3.5×16", kind=FastenerKind.SCREW),
        Fastener(code="G25", name="Гвинт кріплення ручки", size="M4×30", kind=FastenerKind.SCREW),
        Fastener(code="G27", name="Гвинт кріплення магніту", size="3×12", kind=FastenerKind.SCREW),
        Fastener(code="A13", name="Кілок технологічний", size="⌀8×30", kind=FastenerKind.DOWEL),
        Fastener(code="A14", name="Завіса накладна", size="⌀35, 110°", kind=FastenerKind.HINGE),
        Fastener(code="A15", name="Амортизатор дверцят", size="⌀10", kind=FastenerKind.DAMPER),
        Fastener(code="A16", name="Заглушка на трубу 40×40", size="40×40", kind=FastenerKind.CAP),
        Fastener(code="A17", name="Магніт дверний", size="⌀16", kind=FastenerKind.MAGNET),
        # "гачок" і "ланцюжок" (обмежувач кута відкривання кришки) — пара
        # деталей без власного типу в FastenerKind; найближчі наявні:
        # гачок — HANDLE (така сама фурнітура-зачеп на поверхні), ланцюжок
        # — DAMPER (обмежує рух, як і демпфер, лише механічно).
        Fastener(code="A18", name="Гачок обмежувача кришки", size="M4", kind=FastenerKind.HANDLE),
        Fastener(code="A19", name="Ручка меблева", size="L=150", kind=FastenerKind.HANDLE),
        Fastener(code="A20", name="Ланцюжок обмежувача кришки", size="L=300", kind=FastenerKind.DAMPER),
        Fastener(code="T10", name="Ключ шестигранний (імбусовий)", size="H5", kind=FastenerKind.TOOL),
        Fastener(code="L60", name="Заглушка декоративна на отвір", size="⌀15", kind=FastenerKind.CAP),
    ]
)

# --- специфікація складання: скільки кожного коду пішло на комплект --------

USAGES = [
    FastenerUsage(CATALOG.find_by_code("G24"), 48),
    FastenerUsage(CATALOG.find_by_code("G26"), 18),
    FastenerUsage(CATALOG.find_by_code("G28"), 10),
    FastenerUsage(CATALOG.find_by_code("G25"), 4),
    FastenerUsage(CATALOG.find_by_code("G27"), 4),
    FastenerUsage(CATALOG.find_by_code("A13"), 8),
    FastenerUsage(CATALOG.find_by_code("A14"), 4),
    FastenerUsage(CATALOG.find_by_code("A15"), 4),
    FastenerUsage(CATALOG.find_by_code("A16"), 6),
    FastenerUsage(CATALOG.find_by_code("A17"), 4),
    FastenerUsage(CATALOG.find_by_code("A18"), 2),
    FastenerUsage(CATALOG.find_by_code("A19"), 2),
    FastenerUsage(CATALOG.find_by_code("A20"), 2),
    FastenerUsage(CATALOG.find_by_code("T10"), 1),
    FastenerUsage(CATALOG.find_by_code("L60"), 4),
]


def print_usage_table(usages: list[FastenerUsage]) -> None:
    header = f"{'Код':<6}{'Назва':<35}{'Розмір':<12}{'Тип':<14}{'К-сть':>6}"
    print(header)
    print("-" * len(header))
    for usage in usages:
        f = usage.fastener
        print(f"{f.code:<6}{f.name:<35}{f.size:<12}{f.kind.value:<14}{usage.count:>6}")


def main() -> None:
    print(f"Каталог кріплення: {len(CATALOG.fasteners)} позицій.\n")

    summary = CATALOG.summary(USAGES)
    print(f"Специфікація комплекту — {len(summary)} позицій:\n")
    print_usage_table(summary)

    total_units = sum(usage.count for usage in summary)
    print(f"\nРазом одиниць кріплення: {total_units} шт.")


if __name__ == "__main__":
    main()
