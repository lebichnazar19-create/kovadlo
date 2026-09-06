"""
Приклад: специфікація деталей (BOM, модуль 12+) — каркас шафи для
смітників зі STEELMAN, профільна труба 40×40×2 мм, сталь.

Каркас на два відсіки (по одному контейнеру в кожному):
  - дві донні рамки — по одній на відсік, рівень підлоги;
  - середня рама — вертикальний розділювач між відсіками;
  - дві бічні панелі (ліва/права) — зовнішні стінки;
  - задня панель — глухий тил, перед відкритий для завантаження.

Мета прикладу — показати `build_bill_of_materials` (модуль 12,
`kovadlo/bom.py`): 24 окремі відрізки труби зводяться до кількох
позицій специфікації, бо однакова довжина в різних вузлах каркаса —
одна й та сама деталь на складі (вертикальні стояки бічних/середньої/
задньої панелей усі заввишки з каркас — і всі вони одна позиція).

Лише розрахунок і текстовий вивід — жодної графіки.

Запуск з кореня репозиторію:
    python -m examples.bom_demo
"""

from __future__ import annotations

from kovadlo import Beam, Material, Point3, RectTubeProfile, build_bill_of_materials

STEEL = Material(name="Сталь конструкційна S235JR", density_kg_m3=7850)
PROFILE = RectTubeProfile(width=40, height=40, wall_thickness=2)  # профільна труба STEELMAN 40x40x2

WIDTH_MM = 1200.0        # загальна ширина каркаса
DEPTH_MM = 600.0         # глибина (від переду до задньої панелі)
HEIGHT_MM = 1400.0       # висота бічної/середньої/задньої панелі
HALF_WIDTH_MM = 580.0    # ширина одного відсіку (загальна ширина мінус середня рама)


def _tube(name: str, start: Point3, end: Point3) -> Beam:
    return Beam(start=start, end=end, profile=PROFILE, material=STEEL, name=name)


def bottom_frame(prefix: str, x0: float) -> list[Beam]:
    """Донна рамка одного відсіку: прямокутник HALF_WIDTH×DEPTH на рівні підлоги."""
    x1 = x0 + HALF_WIDTH_MM
    near_left, near_right = Point3(x0, 0, 0), Point3(x1, 0, 0)
    far_left, far_right = Point3(x0, 0, DEPTH_MM), Point3(x1, 0, DEPTH_MM)
    return [
        _tube(f"{prefix}: передній край", near_left, near_right),
        _tube(f"{prefix}: задній край", far_left, far_right),
        _tube(f"{prefix}: лівий бік", near_left, far_left),
        _tube(f"{prefix}: правий бік", near_right, far_right),
    ]


def vertical_frame(prefix: str, corner: Point3, along: str, length_mm: float) -> list[Beam]:
    """Вертикальна рамка (бічна/задня панель, середня рама): прямокутник
    `length_mm`×HEIGHT_MM, що стоїть вертикально; `along` — вісь "x" чи
    "z", уздовж якої йде нижня/верхня перекладина."""
    if along == "x":
        far = Point3(corner.x + length_mm, corner.y, corner.z)
    else:
        far = Point3(corner.x, corner.y, corner.z + length_mm)
    top_near = Point3(corner.x, HEIGHT_MM, corner.z)
    top_far = Point3(far.x, HEIGHT_MM, far.z)
    return [
        _tube(f"{prefix}: лівий стояк", corner, top_near),
        _tube(f"{prefix}: правий стояк", far, top_far),
        _tube(f"{prefix}: нижня перекладина", corner, far),
        _tube(f"{prefix}: верхня перекладина", top_near, top_far),
    ]


def build_cabinet_frame() -> list[Beam]:
    beams: list[Beam] = []
    beams += bottom_frame("Донна рамка 1", x0=0.0)
    beams += bottom_frame("Донна рамка 2", x0=HALF_WIDTH_MM)
    beams += vertical_frame("Середня рама", Point3(HALF_WIDTH_MM, 0, 0), along="z", length_mm=DEPTH_MM)
    beams += vertical_frame("Ліва бічна панель", Point3(0, 0, 0), along="z", length_mm=DEPTH_MM)
    beams += vertical_frame("Права бічна панель", Point3(WIDTH_MM, 0, 0), along="z", length_mm=DEPTH_MM)
    beams += vertical_frame("Задня панель", Point3(0, 0, DEPTH_MM), along="x", length_mm=WIDTH_MM)
    return beams


def print_bom_table(lines) -> None:
    header = f"{'№':<4}{'Назва':<20}{'Розмір':<24}{'Матеріал':<30}{'К-сть':>6}"
    print(header)
    print("-" * len(header))
    for line in lines:
        print(f"{line.position:<4}{line.name:<20}{line.size:<24}{line.material_name:<30}{line.count:>6}")


def main() -> None:
    beams = build_cabinet_frame()
    print(f"Каркас шафи для смітників: {len(beams)} відрізків труби.\n")

    lines = build_bill_of_materials(beams)
    print(f"Специфікація (BOM) — {len(lines)} унікальні позиції:\n")
    print_bom_table(lines)

    total_pieces = sum(line.count for line in lines)
    total_weight_kg = sum(beam.weight_kg for beam in beams)
    print(f"\nРазом деталей: {total_pieces} шт., загальна вага каркаса: {total_weight_kg:.1f} кг")


if __name__ == "__main__":
    main()
