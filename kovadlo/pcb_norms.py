"""
Нормативні дані та формули для розрахунку друкованих доріжок.

Методика: **IPC-2221** ("Generic Standard for Printed Board Design") —
розділ щодо визначення ширини провідника за струмовим навантаженням і
допустимим нагрівом (загальновідома емпірична формула, що відтворює
графіки IPC-2221 для зовнішніх/внутрішніх шарів), і розділ щодо
мінімальних електричних зазорів між провідниками залежно від напруги
між ними.

**УВАГА — важливе застереження:** конкретні числові значення нижче
(коефіцієнти формули струму, товщина міді за замовчуванням, таблиця
зазорів) — це типові, орієнтовні інженерні значення для ілюстрації
методики, а НЕ дослівна виписка з чинного тексту стандарту (який ще
враховує клас якості плати, висоту над рівнем моря, наявність
покриття тощо). Перед реальним виготовленням плати ці значення
ОБОВ'ЯЗКОВО треба звірити з чинною редакцією IPC-2221 і вимогами
конкретного виробника плат.
"""

from __future__ import annotations

from enum import Enum

MM_PER_MIL = 0.0254  # 1 mil = 1/1000 дюйма
MM2_PER_MIL2 = MM_PER_MIL**2

# Питомий опір міді, Ом·мм²/м, при робочій температурі провідника (трохи
# вище за "холодний" опір 0.0168 при 20°C — запас на нагрів під струмом,
# той самий підхід, що й у модулі 4).
COPPER_RESISTIVITY_OHM_MM2_PER_M = 0.0180

# Товщина міді за замовчуванням, мкм. 35 мкм відповідає поширеній
# "вазі" фольги 1 oz/ft² (типовий зовнішній шар побутової/аматорської плати).
DEFAULT_COPPER_THICKNESS_UM = 35.0

# Максимально допустиме падіння напруги на доріжці за замовчуванням, %.
MAX_TRACK_VOLTAGE_DROP_PERCENT_DEFAULT = 5.0

# Мінімальна практична ширина доріжки (виробничий ліміт більшості
# бюджетних виробників плат), мм.
MIN_TRACK_WIDTH_MM = 0.15


class Layer(Enum):
    """Шар плати."""

    TOP = "верхній"
    BOTTOM = "нижній"


# Коефіцієнти емпіричної формули IPC-2221 (I = k · ΔT^0.44 · A^0.725,
# A — площа перерізу провідника в mil², I — струм в А, ΔT — перевищення
# температури, °C). Тут k — для зовнішніх провідників (на поверхні
# плати, охолодження повітрям); `Layer` у цьому модулі описує лише
# верхній/нижній шар — обидва зовнішні на типовій двошаровій платі,
# внутрішні шари (з іншим, меншим k через гірше охолодження) поза
# межами цього спрощеного інструменту.
IPC2221_K_EXTERNAL = 0.048
IPC2221_EXPONENT_DELTA_T = 0.44
IPC2221_EXPONENT_AREA = 0.725

DEFAULT_TEMPERATURE_RISE_C = 10.0  # типове проектне перевищення температури, °C


def required_cross_section_mil2(current_a: float, *, temperature_rise_c: float) -> float:
    """Необхідна площа перерізу провідника за струмом IPC-2221, mil².

    Обернена форма формули I = k·ΔT^0.44·A^0.725 → A = (I / (k·ΔT^0.44))^(1/0.725).
    """
    if current_a <= 0:
        raise ValueError("Струм має бути додатним")
    if temperature_rise_c <= 0:
        raise ValueError("Допустиме перевищення температури має бути додатним")
    base = current_a / (IPC2221_K_EXTERNAL * temperature_rise_c**IPC2221_EXPONENT_DELTA_T)
    return base ** (1.0 / IPC2221_EXPONENT_AREA)


def required_track_width_mm(
    current_a: float,
    *,
    temperature_rise_c: float = DEFAULT_TEMPERATURE_RISE_C,
    copper_thickness_um: float = DEFAULT_COPPER_THICKNESS_UM,
    min_width_mm: float = MIN_TRACK_WIDTH_MM,
) -> float:
    """Мінімальна ширина доріжки за струмовим навантаженням (IPC-2221),
    з урахуванням виробничого мінімуму `min_width_mm`."""
    area_mil2 = required_cross_section_mil2(current_a, temperature_rise_c=temperature_rise_c)
    thickness_mil = copper_thickness_um / 25.4  # 1 mil = 25.4 мкм
    width_mil = area_mil2 / thickness_mil
    width_mm = width_mil * MM_PER_MIL
    return max(width_mm, min_width_mm)


def track_cross_section_mm2(width_mm: float, copper_thickness_um: float = DEFAULT_COPPER_THICKNESS_UM) -> float:
    """Площа перерізу доріжки, мм² (ширина × товщина міді)."""
    return width_mm * (copper_thickness_um / 1000.0)


def track_resistance_ohm(
    length_mm: float, width_mm: float, *, copper_thickness_um: float = DEFAULT_COPPER_THICKNESS_UM
) -> float:
    """Опір мідної доріжки, Ом: R = ρ·L/A, де A — площа перерізу (мм²), L — довжина (м)."""
    area_mm2 = track_cross_section_mm2(width_mm, copper_thickness_um)
    if area_mm2 <= 0:
        raise ValueError("Ширина доріжки й товщина міді мають бути додатними")
    length_m = length_mm / 1000.0
    return COPPER_RESISTIVITY_OHM_MM2_PER_M * length_m / area_mm2


def track_voltage_drop_v(
    current_a: float, length_mm: float, width_mm: float, *, copper_thickness_um: float = DEFAULT_COPPER_THICKNESS_UM
) -> float:
    """Падіння напруги на доріжці, В: U = I·R."""
    return current_a * track_resistance_ohm(length_mm, width_mm, copper_thickness_um=copper_thickness_um)


# Спрощена таблиця мінімальних електричних зазорів між провідниками
# залежно від напруги між ними, мм (орієнтовно, за духом таблиці
# зазорів IPC-2221 для провідників без покриття на висоті до ~3000 м;
# межі напруги — верхня межа діапазону, зазор — мінімум для цього
# діапазону).
CLEARANCE_TABLE_MM: list[tuple[float, float]] = [
    (15.0, 0.10),
    (30.0, 0.10),
    (50.0, 0.13),
    (100.0, 0.13),
    (150.0, 0.40),
    (170.0, 0.50),
    (250.0, 0.80),
    (300.0, 0.80),
    (500.0, 2.50),
]


def min_clearance_mm(voltage_v: float) -> float:
    """Мінімальний зазор між провідниками при заданій різниці потенціалів
    між ними, мм (спрощена таблиця — див. застереження в docstring модуля)."""
    voltage = abs(voltage_v)
    for max_voltage, clearance in CLEARANCE_TABLE_MM:
        if voltage <= max_voltage:
            return clearance
    raise ValueError(
        f"Напруга {voltage_v:.0f} В перевищує межу спрощеної таблиці зазорів "
        f"({CLEARANCE_TABLE_MM[-1][0]:.0f} В) — потрібна індивідуальна оцінка за повною нормою"
    )
