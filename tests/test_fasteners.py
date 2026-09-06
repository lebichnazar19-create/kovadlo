"""Тести каталогу кріплення (kovadlo/fasteners.py)."""

import pytest

from kovadlo.fasteners import Fastener, FastenerCatalog, FastenerKind, FastenerUsage

SCREW = Fastener(code="G24", name="Гвинт з внутрішнім шестигранником", size="M6×16", kind=FastenerKind.SCREW)
NUT = Fastener(code="N10", name="Гайка шестигранна", size="M6", kind=FastenerKind.NUT)
WASHER = Fastener(code="W05", name="Шайба плоска", size="M6", kind=FastenerKind.WASHER)


# ------------------------------------------------------------------- Fastener

def test_fastener_fields():
    assert SCREW.code == "G24"
    assert SCREW.name == "Гвинт з внутрішнім шестигранником"
    assert SCREW.size == "M6×16"
    assert SCREW.kind is FastenerKind.SCREW


def test_fastener_rejects_empty_code():
    with pytest.raises(ValueError):
        Fastener(code="", name="Щось", size="M6", kind=FastenerKind.SCREW)


def test_fastener_is_frozen():
    with pytest.raises(AttributeError):
        SCREW.code = "OTHER"


# -------------------------------------------------------------- FastenerUsage

def test_fastener_usage_fields():
    usage = FastenerUsage(fastener=SCREW, count=8)
    assert usage.fastener is SCREW
    assert usage.count == 8


def test_fastener_usage_rejects_non_positive_count():
    with pytest.raises(ValueError):
        FastenerUsage(fastener=SCREW, count=0)
    with pytest.raises(ValueError):
        FastenerUsage(fastener=SCREW, count=-1)


# ------------------------------------------------------------ FastenerCatalog

def test_catalog_find_by_code():
    catalog = FastenerCatalog([SCREW, NUT])
    assert catalog.find_by_code("G24") is SCREW
    assert catalog.find_by_code("N10") is NUT
    assert catalog.find_by_code("nope") is None


def test_catalog_rejects_duplicate_codes_on_construction():
    duplicate = Fastener(code="G24", name="Інший гвинт", size="M8×20", kind=FastenerKind.SCREW)
    with pytest.raises(ValueError):
        FastenerCatalog([SCREW, duplicate])


def test_catalog_add():
    catalog = FastenerCatalog([SCREW])
    catalog.add(NUT)
    assert catalog.find_by_code("N10") is NUT


def test_catalog_add_rejects_duplicate_code():
    catalog = FastenerCatalog([SCREW])
    duplicate = Fastener(code="G24", name="Інший гвинт", size="M8×20", kind=FastenerKind.SCREW)
    with pytest.raises(ValueError):
        catalog.add(duplicate)


def test_catalog_starts_empty_by_default():
    assert FastenerCatalog().fasteners == []


# ------------------------------------------------------------------- summary

def test_summary_sums_counts_for_same_code():
    catalog = FastenerCatalog([SCREW, NUT, WASHER])
    usages = [
        FastenerUsage(SCREW, 4),
        FastenerUsage(NUT, 4),
        FastenerUsage(SCREW, 4),  # той самий вузол ще раз — той самий код
    ]
    result = catalog.summary(usages)

    by_code = {usage.fastener.code: usage.count for usage in result}
    assert by_code == {"G24": 8, "N10": 4}


def test_summary_preserves_first_occurrence_order():
    catalog = FastenerCatalog([SCREW, NUT, WASHER])
    usages = [FastenerUsage(WASHER, 2), FastenerUsage(SCREW, 1), FastenerUsage(WASHER, 3)]
    result = catalog.summary(usages)
    assert [usage.fastener.code for usage in result] == ["W05", "G24"]
    assert result[0].count == 5


def test_summary_is_stable_across_repeated_calls():
    catalog = FastenerCatalog([SCREW, NUT])
    usages = [FastenerUsage(SCREW, 4), FastenerUsage(NUT, 2), FastenerUsage(SCREW, 2)]
    assert catalog.summary(usages) == catalog.summary(usages)


def test_summary_empty_usages_gives_empty_list():
    catalog = FastenerCatalog([SCREW])
    assert catalog.summary([]) == []


def test_summary_rejects_usage_of_unknown_code():
    catalog = FastenerCatalog([SCREW])
    unknown = Fastener(code="X99", name="Невідоме", size="M6", kind=FastenerKind.SCREW)
    with pytest.raises(ValueError):
        catalog.summary([FastenerUsage(unknown, 1)])
