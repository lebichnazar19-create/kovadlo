"""
Стандартні записи бази матеріалів — перша версія, по кілька ілюстративних
позицій на кожну категорію з завдання.

**Джерело й точність значень:** усі числа нижче — орієнтовні, типові для
категорії продукту значення з поширених джерел (EN 206 для бетону,
EN 998-2 для мурувальних розчинів, EN 13813 для стяжок, EN 12004 для
клеїв плитки, EN 13888 для фуг, EN 10025/EN 10088 для сталей, довідники
матеріалознавства для кольорових металів і теплоізоляції). Це НЕ дослівна
виписка з норми чи конкретного технічного листа виробника — перед
реальним застосуванням звірте з TDS/картою технічною конкретного
продукту. Ціни вказані для Польщі, орієнтовно на серпень 2026 і
змінюються з часом і постачальником.
"""

from __future__ import annotations

from .material_database import MaterialDatabase
from .material_spec import Coverage, MaterialCategory, MaterialSpec, PriceInfo

_PRICE_DATE = "2026-08"
_PRICE_REGION = "Польща"


def _price(price_pln: float, unit: str, note: str = "", reference_thickness_mm: float | None = None) -> PriceInfo:
    return PriceInfo(
        price_pln=price_pln,
        unit=unit,
        date=_PRICE_DATE,
        region=_PRICE_REGION,
        note=note,
        reference_thickness_mm=reference_thickness_mm,
    )


def build_default_database() -> MaterialDatabase:
    """Повертає нову базу з ілюстративними записами по всіх категоріях
    першої версії (модуль 7)."""
    materials: list[MaterialSpec] = []

    # --- Бетони й розчини ------------------------------------------------
    materials += [
        MaterialSpec(
            name="Бетон C20/25",
            category=MaterialCategory.CONCRETE,
            designation="C20/25",
            density_kg_m3=2400,
            compressive_strength_mpa=25.0,
            thermal_conductivity_w_mk=1.7,
            thermal_expansion_1_per_k=10e-6,
            application="фундаменти, монолітні конструкції",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=False,
            coverage=Coverage(2400, "кг/м³"),
            prices=[_price(420, "м3")],
            source_note="EN 206, орієнтовний клас міцності на кубічних зразках",
        ),
        MaterialSpec(
            name="Бетон C25/30",
            category=MaterialCategory.CONCRETE,
            designation="C25/30",
            density_kg_m3=2400,
            compressive_strength_mpa=30.0,
            thermal_conductivity_w_mk=1.8,
            thermal_expansion_1_per_k=10e-6,
            application="несучі стіни, перекриття, конструкційний бетон",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=False,
            coverage=Coverage(2400, "кг/м³"),
            prices=[_price(460, "м3")],
            source_note="EN 206, орієнтовний клас міцності на кубічних зразках",
        ),
        MaterialSpec(
            name="Мурувальний розчин М5",
            category=MaterialCategory.CONCRETE,
            designation="M5 (EN 998-2)",
            density_kg_m3=1800,
            compressive_strength_mpa=5.0,
            thermal_conductivity_w_mk=0.8,
            application="кладка цегли й блоків",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=False,
            coverage=Coverage(15.0, "кг/м²", note="шов 10 мм, орієнтовно"),
            prices=[_price(18, "упаковка", note="мішок 25 кг"), _price(0.72, "кг")],
            source_note="EN 998-2, типовий будівельний розчин загального призначення",
        ),
        MaterialSpec(
            name="Стяжка підлоги CT-C20-F4",
            category=MaterialCategory.CONCRETE,
            designation="CT-C20-F4 (EN 13813)",
            density_kg_m3=2000,
            compressive_strength_mpa=20.0,
            thermal_conductivity_w_mk=1.4,
            application="вирівнювальна стяжка підлоги під фінішне покриття",
            outdoor_suitable=False,
            frost_resistant=False,
            water_resistant=False,
            coverage=Coverage(20.0, "кг/м²", note="товщина 10 мм, орієнтовно"),
            prices=[_price(1.1, "кг")],
            source_note="EN 13813, цементна стяжка (CT), класи міцності на стиск/згин",
        ),
    ]

    # --- Гіпс і сухі суміші -----------------------------------------------
    materials += [
        MaterialSpec(
            name="Штукатурка гіпсова",
            category=MaterialCategory.GYPSUM,
            designation="B1 (машинне/ручне нанесення)",
            density_kg_m3=950,
            compressive_strength_mpa=2.0,
            thermal_conductivity_w_mk=0.35,
            application="внутрішнє тинькування стін і стель",
            outdoor_suitable=False,
            frost_resistant=False,
            water_resistant=False,
            coverage=Coverage(9.0, "кг/м²", note="шар 10 мм, орієнтовно"),
            prices=[_price(22, "упаковка", note="мішок 30 кг")],
            source_note="типові значення гіпсових тинькувальних сумішей",
        ),
        MaterialSpec(
            name="Шпаклівка фінішна",
            category=MaterialCategory.GYPSUM,
            designation="фінішна, на гіпсовій основі",
            density_kg_m3=1000,
            thermal_conductivity_w_mk=0.3,
            application="фінішне вирівнювання поверхні перед фарбуванням",
            outdoor_suitable=False,
            frost_resistant=False,
            water_resistant=False,
            coverage=Coverage(1.1, "кг/м²", note="на 1 мм товщини, орієнтовно"),
            prices=[_price(3.2, "кг")],
            source_note="типові значення фінішних шпаклівок на гіпсовій основі",
        ),
        MaterialSpec(
            name="Гіпсокартон (плита 12.5 мм)",
            category=MaterialCategory.GYPSUM,
            designation="GKB, тип A, 12.5 мм",
            density_kg_m3=750,
            thermal_conductivity_w_mk=0.21,
            application="обшивка стін і стель, перегородки",
            outdoor_suitable=False,
            frost_resistant=False,
            water_resistant=False,
            coverage=Coverage(3.0, "м²/лист", note="стандартний лист 1.2×2.5 м"),
            prices=[_price(28, "упаковка", note="один лист"), _price(9.3, "м2")],
            source_note="типові значення гіпсокартону типу A за EN 520",
        ),
    ]

    # --- Клеї для плитки ---------------------------------------------------
    materials += [
        MaterialSpec(
            name="Клей плитковий C1T",
            category=MaterialCategory.TILE_ADHESIVE,
            designation="C1T (EN 12004)",
            density_kg_m3=1500,
            application="внутрішні роботи, стандартна кераміка малого/середнього формату",
            outdoor_suitable=False,
            frost_resistant=False,
            water_resistant=False,
            coverage=Coverage(1.3, "кг/м²", note="на 1 мм товщини шару, зубчастий шпатель"),
            prices=[_price(19, "упаковка", note="мішок 25 кг")],
            source_note="EN 12004, клас C1 (нормальний), T — знижене сповзання",
        ),
        MaterialSpec(
            name="Клей плитковий C2TE S1",
            category=MaterialCategory.TILE_ADHESIVE,
            designation="C2TE S1 (EN 12004)",
            density_kg_m3=1450,
            application="зовнішні роботи, тепла підлога, великий формат, морозостійкі умови",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            coverage=Coverage(1.4, "кг/м²", note="на 1 мм товщини шару"),
            prices=[_price(34, "упаковка", note="мішок 25 кг")],
            source_note="EN 12004, клас C2 (покращений) + T + E (подовжений відкритий час) + S1 (деформівний)",
        ),
        MaterialSpec(
            name="Клей плитковий C2S2",
            category=MaterialCategory.TILE_ADHESIVE,
            designation="C2S2 (EN 12004)",
            density_kg_m3=1450,
            application="великоформатна плитка, нежорсткі/деформівні основи, тепла підлога",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            coverage=Coverage(1.5, "кг/м²", note="на 1 мм товщини шару, зубчастий шпатель 10-12 мм"),
            prices=[_price(42, "упаковка", note="мішок 25 кг")],
            source_note="EN 12004, клас C2 (покращений) + S2 (високодеформівний)",
        ),
    ]

    # --- Фуги ---------------------------------------------------------------
    materials += [
        MaterialSpec(
            name="Фуга цементна CG2",
            category=MaterialCategory.GROUT,
            designation="CG2 (EN 13888)",
            density_kg_m3=1600,
            application="шви плитки шириною 1-15 мм, стандартні вологі приміщення",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=False,
            coverage=Coverage(0.4, "кг/м²", note="орієнтовно для плитки 300×300 мм, шов 3 мм"),
            prices=[_price(14, "упаковка", note="пакет 5 кг")],
            source_note="EN 13888, клас CG2 (покращена, менше водопоглинання/стирання)",
        ),
        MaterialSpec(
            name="Фуга епоксидна RG",
            category=MaterialCategory.GROUT,
            designation="RG (EN 13888)",
            density_kg_m3=1700,
            application="басейни, вологі приміщення, хімічно агресивні середовища",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            coverage=Coverage(0.45, "кг/м²", note="орієнтовно для плитки 300×300 мм, шов 3 мм"),
            prices=[_price(65, "упаковка", note="набір 2 кг")],
            source_note="EN 13888, реактивна (епоксидна) фуга класу RG",
        ),
    ]

    # --- Метали ---------------------------------------------------------------
    materials += [
        MaterialSpec(
            name="Сталь конструкційна S235JR",
            category=MaterialCategory.METAL,
            designation="S235JR (EN 10025-2)",
            density_kg_m3=7850,
            compressive_strength_mpa=235.0,
            tensile_strength_mpa=360.0,
            thermal_conductivity_w_mk=50.0,
            electrical_resistivity_ohm_m=1.7e-7,
            thermal_expansion_1_per_k=12e-6,
            melting_point_c=1500,
            application="металоконструкції, каркаси, загального призначення",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=False,
            prices=[_price(5.2, "кг")],
            source_note="EN 10025-2, типові значення для вуглецевої конструкційної сталі",
        ),
        MaterialSpec(
            name="Сталь нержавіюча AISI 304 (1.4301)",
            category=MaterialCategory.METAL,
            designation="1.4301 / AISI 304 (EN 10088)",
            density_kg_m3=8000,
            compressive_strength_mpa=215.0,
            tensile_strength_mpa=530.0,
            thermal_conductivity_w_mk=16.0,
            electrical_resistivity_ohm_m=7.2e-7,
            thermal_expansion_1_per_k=17.3e-6,
            melting_point_c=1425,
            application="корозійностійкі конструкції, харчове й хімічне обладнання",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            prices=[_price(24, "кг")],
            source_note="EN 10088, типові значення для аустенітної нержавіючої сталі",
        ),
        MaterialSpec(
            name="Алюміній (сплав 6060, Т6)",
            category=MaterialCategory.METAL,
            designation="EN AW-6060 T6",
            density_kg_m3=2700,
            tensile_strength_mpa=190.0,
            thermal_conductivity_w_mk=200.0,
            electrical_resistivity_ohm_m=3.3e-8,
            thermal_expansion_1_per_k=23e-6,
            melting_point_c=655,
            application="радіатори охолодження, корпуси, профілі",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            prices=[_price(19, "кг")],
            source_note="типові значення для термооброблюваного алюмінієвого сплаву серії 6xxx",
        ),
        MaterialSpec(
            name="Мідь (метал, Cu-ETP)",
            category=MaterialCategory.METAL,
            designation="Cu-ETP (EN 1976)",
            density_kg_m3=8960,
            tensile_strength_mpa=220.0,
            thermal_conductivity_w_mk=390.0,
            electrical_resistivity_ohm_m=1.78e-8,
            thermal_expansion_1_per_k=17e-6,
            melting_point_c=1085,
            application="теплообмінники, радіатори, електротехнічні деталі загального призначення",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            prices=[_price(38, "кг")],
            source_note="EN 1976, типові значення для міді напівтвердого гарту",
        ),
        MaterialSpec(
            name="Латунь (CuZn37)",
            category=MaterialCategory.METAL,
            designation="CuZn37 (EN 12164)",
            density_kg_m3=8500,
            tensile_strength_mpa=440.0,
            thermal_conductivity_w_mk=120.0,
            electrical_resistivity_ohm_m=6.2e-8,
            thermal_expansion_1_per_k=19e-6,
            melting_point_c=920,
            application="фітинги, корпуси моторів, декоративна фурнітура",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            prices=[_price(29, "кг")],
            source_note="EN 12164, типові значення для латуні загального призначення",
        ),
    ]

    # --- Ізоляція й утеплення -----------------------------------------------
    materials += [
        MaterialSpec(
            name="Мінеральна вата (кам'яна)",
            category=MaterialCategory.INSULATION,
            designation="λ = 0.038 (типовий продукт)",
            density_kg_m3=40,
            thermal_conductivity_w_mk=0.038,
            application="утеплення стін, покрівель, звуко- й вогнестійкість",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=False,
            coverage=Coverage(1.0, "м²/м²", note="на товщину утеплювача"),
            prices=[_price(24, "м2", note="за плиту товщиною 100 мм", reference_thickness_mm=100)],
            source_note="типові значення кам'яної мінеральної вати для фасадів",
        ),
        MaterialSpec(
            name="Пінопласт EPS",
            category=MaterialCategory.INSULATION,
            designation="EPS 70, λ = 0.040",
            density_kg_m3=20,
            thermal_conductivity_w_mk=0.040,
            application="утеплення фасадів, підлог по ґрунту",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            coverage=Coverage(1.0, "м²/м²", note="на товщину утеплювача"),
            prices=[_price(14, "м2", note="за плиту товщиною 100 мм", reference_thickness_mm=100)],
            source_note="типові значення пінополістиролу EPS 70",
        ),
        MaterialSpec(
            name="XPS (екструдований пінополістирол)",
            category=MaterialCategory.INSULATION,
            designation="XPS 300, λ = 0.033",
            density_kg_m3=35,
            compressive_strength_mpa=0.3,
            thermal_conductivity_w_mk=0.033,
            application="фундаменти, цоколі, інверсійні покрівлі — вологі умови",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            coverage=Coverage(1.0, "м²/м²", note="на товщину утеплювача"),
            prices=[_price(28, "м2", note="за плиту товщиною 100 мм", reference_thickness_mm=100)],
            source_note="типові значення екструдованого пінополістиролу для фундаментів",
        ),
        MaterialSpec(
            name="PIR (поліізоціанурат)",
            category=MaterialCategory.INSULATION,
            designation="PIR, фольгована обкладинка, λ = 0.023",
            density_kg_m3=32,
            thermal_conductivity_w_mk=0.023,
            application="тонкошарове утеплення дахів, стін при обмеженій товщині",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            coverage=Coverage(1.0, "м²/м²", note="на товщину утеплювача"),
            prices=[_price(46, "м2", note="за плиту товщиною 100 мм", reference_thickness_mm=100)],
            source_note="типові значення фольгованих плит PIR",
        ),
    ]

    # --- Провідники (для модуля 4) --------------------------------------------
    materials += [
        MaterialSpec(
            name="Мідь (провідникова, відпалена)",
            category=MaterialCategory.CONDUCTOR,
            designation="Cu, м'який відпал (IEC 60228)",
            density_kg_m3=8960,
            electrical_resistivity_ohm_m=1.72e-8,
            thermal_expansion_1_per_k=17e-6,
            melting_point_c=1085,
            application="жили кабелів і провідників, обмотки",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            prices=[_price(40, "кг")],
            source_note="IEC 60228, питомий опір відпаленої міді близько до 100% IACS",
        ),
        MaterialSpec(
            name="Алюміній (провідниковий, АД0)",
            category=MaterialCategory.CONDUCTOR,
            designation="Al 1350 / АД0",
            density_kg_m3=2700,
            electrical_resistivity_ohm_m=2.8e-8,
            thermal_expansion_1_per_k=23e-6,
            melting_point_c=660,
            application="жили силових кабелів великого перерізу, повітряні лінії",
            outdoor_suitable=True,
            frost_resistant=True,
            water_resistant=True,
            prices=[_price(13, "кг")],
            source_note="типові значення для провідникового алюмінію високої чистоти (серія 1xxx)",
        ),
    ]

    return MaterialDatabase(materials=materials)
