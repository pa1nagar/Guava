"""
test_gap_engine_no_hardcoded.py — Source-level guard against a hard-coded
plant-count default in the gap engine.

Requirement 1.8: every farm-specific value used in calculations — including
tree count — must be derived from the authenticated Farmer's Farm or Plot
record. The gap engine must NEVER fall back to a hard-coded constant such as
2,100 trees.

Requirement 18.4: Gap_Engine unit tests must cover the absence of any
hard-coded 2,100-tree constant.

These tests read the source of ``services/gap_engine.py`` and assert that
the literal ``2100`` does not appear anywhere in the file, which catches both
an explicit default assignment and any constant that would silently
substitute for the caller-supplied ``plant_count``.

**Validates: Requirements 1.8**
"""

import pathlib

import pytest

import services.gap_engine as gap_engine


def _gap_engine_source() -> str:
    """Return the raw source text of gap_engine.py."""
    return pathlib.Path(gap_engine.__file__).read_text(encoding="utf-8")


def test_no_hardcoded_2100_in_source():
    """The literal 2100 must not appear anywhere in gap_engine.py.

    If it did, it would indicate a hard-coded default plant count that violates
    Requirement 1.8 — every farm-specific value must come from the Farmer's
    Plot record, not a magic constant.
    """
    source = _gap_engine_source()
    assert "2100" not in source, (
        "gap_engine.py must not contain a hard-coded 2100-tree constant "
        "(Requirement 1.8 / 18.4)."
    )


def test_gap_engine_consumes_supplied_plant_count():
    """Doubling plant_count must roughly double expected cumulative totals.

    This proves the engine uses the caller-supplied plant_count rather than
    substituting a fixed default — a behavioural guard against any hidden
    2,100-tree regression.
    """
    stages = [
        {
            "stage_id": "s1",
            "month_start": 0,
            "month_end": 5,
            "quantities": {
                "irrigation_litres_per_plant_per_day": 3,
                "fertilizer_grams_per_plant_per_week": 5,
            },
        }
    ]

    gaps_100 = gap_engine.compute_gaps(
        stages, months_elapsed=3, plant_count=100, activities=[]
    )
    gaps_200 = gap_engine.compute_gaps(
        stages, months_elapsed=3, plant_count=200, activities=[]
    )

    fert_100 = next(g for g in gaps_100 if g.activity_type == "Fertilizer")
    fert_200 = next(g for g in gaps_200 if g.activity_type == "Fertilizer")

    assert fert_200.expected_kg_or_litres == pytest.approx(
        fert_100.expected_kg_or_litres * 2, rel=0.01
    )


def test_gap_engine_docstring_documents_plot_sourcing():
    """The module docstring must mention Plot record sourcing (Requirement 1.8).

    This verifies that the documentation explicitly notes the caller now
    passes ``plant_count`` sourced from the Plot record.
    """
    doc = gap_engine.__doc__ or ""
    assert "Plot" in doc, (
        "gap_engine.py module docstring must document that plant_count is "
        "sourced from the Plot record (Requirement 1.8)."
    )
