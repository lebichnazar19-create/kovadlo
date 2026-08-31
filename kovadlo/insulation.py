"""
Утеплення (8.4): опір теплопередачі стіни шар за шаром, порівняння з
нормою WT2021, підбір товщини утеплювача, попередження про точку роси.

Норма: орієнтовне граничне значення коефіцієнта теплопередачі зовнішньої
стіни за **WT2021** (польські "Warunki Techniczne" — технічні умови,
яким повинні відповідати будівлі, редакція від 2021 року) — це
узагальнене орієнтовне число, а не повна таблиця норми (яка різниться
для стін/дахів/підлог/вікон і типу будівлі).

Перевірка точки роси — СПРОЩЕНА: температура на межах шарів рахується
за лінійним розподілом падіння температури пропорційно опору кожного
шару (коректно для стаціонарної одновимірної теплопередачі), і
порівнюється з точкою роси внутрішнього повітря (формула Магнуса). Це
НЕ повний аналіз Ґлазера за EN ISO 13788 (там ще враховується опір
дифузії водяної пари кожного шару, а не лише теплопровідність) — лише
орієнтовний скринінг ризику конденсату.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from .material_compare import thermal_layer_option
from .material_spec import MaterialSpec

# Опір тепловіддачі на поверхнях стіни, м²·К/Вт (EN ISO 6946, орієнтовно,
# для горизонтального теплового потоку через вертикальну стіну).
RSI_WALL_M2K_W = 0.13
RSE_WALL_M2K_W = 0.04

# Орієнтовне граничне значення коефіцієнта теплопередачі зовнішньої стіни
# житлової будівлі за WT2021, Вт/(м²·К).
WT2021_MAX_U_WALL_W_M2K = 0.20


@dataclass(frozen=True)
class WallLayer:
    """Один шар конструкції стіни: матеріал (посилання на базу модуля 7 —
    сам об'єкт `MaterialSpec`) і товщина."""

    material: MaterialSpec
    thickness_m: float

    def __post_init__(self) -> None:
        if self.thickness_m <= 0:
            raise ValueError("Товщина шару має бути додатною")
        if self.material.thermal_conductivity_w_mk is None:
            raise ValueError(f"У матеріалу «{self.material.name}» не задана теплопровідність")

    @property
    def thermal_resistance_m2k_w(self) -> float:
        """Опір шару, м²·К/Вт: R = d/λ."""
        return self.thickness_m / self.material.thermal_conductivity_w_mk


def wall_thermal_resistance_m2k_w(
    layers: list[WallLayer], *, rsi: float = RSI_WALL_M2K_W, rse: float = RSE_WALL_M2K_W
) -> float:
    """Сумарний опір теплопередачі стіни, м²·К/Вт: Rsi + Σ(d/λ) + Rse."""
    return rsi + sum(layer.thermal_resistance_m2k_w for layer in layers) + rse


def wall_u_value_w_m2k(layers: list[WallLayer], *, rsi: float = RSI_WALL_M2K_W, rse: float = RSE_WALL_M2K_W) -> float:
    """Коефіцієнт теплопередачі стіни, Вт/(м²·К): U = 1/R."""
    r_total = wall_thermal_resistance_m2k_w(layers, rsi=rsi, rse=rse)
    if r_total <= 0:
        raise ValueError("Сумарний опір стіни має бути додатним")
    return 1.0 / r_total


_U_VALUE_COMPARISON_TOLERANCE = 1e-9  # запобігає хибному "не відповідає" через похибку округлення на межі норми


@dataclass
class InsulationCheck:
    """Результат перевірки стіни на відповідність нормі."""

    u_value_w_m2k: float
    max_u_value_w_m2k: float

    @property
    def meets_norm(self) -> bool:
        return self.u_value_w_m2k <= self.max_u_value_w_m2k + _U_VALUE_COMPARISON_TOLERANCE


def check_against_wt2021(layers: list[WallLayer], *, max_u_w_m2k: float = WT2021_MAX_U_WALL_W_M2K) -> InsulationCheck:
    """Порівнює стіну з орієнтовною нормою WT2021."""
    return InsulationCheck(u_value_w_m2k=wall_u_value_w_m2k(layers), max_u_value_w_m2k=max_u_w_m2k)


def required_insulation_thickness_m(
    base_layers: list[WallLayer],
    insulation_material: MaterialSpec,
    *,
    target_u_w_m2k: float = WT2021_MAX_U_WALL_W_M2K,
    rsi: float = RSI_WALL_M2K_W,
    rse: float = RSE_WALL_M2K_W,
) -> float:
    """Товщина шару утеплювача, яку треба додати до `base_layers`, щоб
    досягти `target_u_w_m2k`."""
    if insulation_material.thermal_conductivity_w_mk is None:
        raise ValueError(f"У матеріалу «{insulation_material.name}» не задана теплопровідність")
    if target_u_w_m2k <= 0:
        raise ValueError("Цільовий коефіцієнт теплопередачі має бути додатним")

    base_r = rsi + rse + sum(layer.thermal_resistance_m2k_w for layer in base_layers)
    target_r = 1.0 / target_u_w_m2k
    needed_r = target_r - base_r
    if needed_r <= 0:
        raise ValueError("Основа стіни вже задовольняє норму без додаткового утеплення")
    return needed_r * insulation_material.thermal_conductivity_w_mk


def insulation_cost_per_m2(insulation_material: MaterialSpec, thickness_m: float) -> float | None:
    """Орієнтовна ціна за м² шару утеплювача заданої товщини — з ціни
    матеріалу бази модуля 7 (`material_compare.thermal_layer_option`,
    перерахована через товщину, а не опір, тому підставляємо
    еквівалентний опір R = d/λ)."""
    if insulation_material.thermal_conductivity_w_mk is None:
        raise ValueError(f"У матеріалу «{insulation_material.name}» не задана теплопровідність")
    equivalent_r = thickness_m / insulation_material.thermal_conductivity_w_mk
    option = thermal_layer_option(insulation_material, equivalent_r)
    return option.cost_per_m2_pln


def dew_point_c(temperature_c: float, relative_humidity_percent: float) -> float:
    """Точка роси, °C (формула Магнуса, орієнтовна апроксимація)."""
    a, b = 17.27, 237.7
    rh = max(1e-6, min(relative_humidity_percent, 100.0)) / 100.0
    alpha = math.log(rh) + (a * temperature_c) / (b + temperature_c)
    return (b * alpha) / (a - alpha)


def layer_interface_temperatures_c(
    layers: list[WallLayer],
    indoor_temp_c: float,
    outdoor_temp_c: float,
    *,
    rsi: float = RSI_WALL_M2K_W,
    rse: float = RSE_WALL_M2K_W,
) -> list[float]:
    """Температура на кожній межі шарів, від внутрішньої поверхні стіни
    до зовнішньої (лінійний розподіл падіння температури пропорційно
    опору — коректно для стаціонарного одновимірного потоку тепла).

    Повертає список довжиною `len(layers) + 1`: [T_внутр.поверхні, T_після_шару_1, ..., T_зовн.поверхні].
    """
    total_r = wall_thermal_resistance_m2k_w(layers, rsi=rsi, rse=rse)
    delta_t = indoor_temp_c - outdoor_temp_c
    temps = [indoor_temp_c - delta_t * (rsi / total_r)]
    cumulative_r = rsi
    for layer in layers:
        cumulative_r += layer.thermal_resistance_m2k_w
        temps.append(indoor_temp_c - delta_t * (cumulative_r / total_r))
    return temps


def condensation_risk_warnings(
    layers: list[WallLayer],
    indoor_temp_c: float,
    indoor_relative_humidity_percent: float,
    outdoor_temp_c: float,
) -> list[str]:
    """Попередження, якщо температура на внутрішній поверхні стіни чи на
    межі всередині "пирога" шарів нижча за точку роси ВНУТРІШНЬОГО
    повітря — орієнтовний скринінг ризику конденсату (див. застереження
    в docstring модуля).

    Зовнішня поверхня стіни (остання межа, перед Rse) із перевірки
    свідомо виключена: вона контактує із зовнішнім повітрям, чия
    вологість тут не задається, тож порівнювати її з ВНУТРІШНЬОЮ точкою
    роси немає сенсу — там завжди холодно взимку, і це нормально, доки
    волога зсередини не встигає туди дійти й сконденсуватися."""
    dew = dew_point_c(indoor_temp_c, indoor_relative_humidity_percent)
    temps = layer_interface_temperatures_c(layers, indoor_temp_c, outdoor_temp_c)
    warnings = []
    for index, temperature in enumerate(temps[:-1]):
        if temperature < dew:
            warnings.append(
                f"межа {index}: температура {temperature:.1f}°C нижча за точку роси "
                f"{dew:.1f}°C — ризик конденсату"
            )
    return warnings
