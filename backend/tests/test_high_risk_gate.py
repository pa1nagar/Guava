"""
tests/test_high_risk_gate.py — Unit tests for the HIGH-risk AI content gate.

Task 31.1 — Covers:
  - All HIGH_RISK_KEYWORDS each trigger 'HIGH' classification
  - Benign queries return 'LOW'
  - Mixed-case variants are classified as 'HIGH'
  - Embedded keyword variants (keyword in middle of sentence) are classified as 'HIGH'

Requirements: 14.5
"""

from __future__ import annotations

import pytest

from services.ai_proxy import classify_risk, HIGH_RISK_KEYWORDS


# ═════════════════════════════════════════════════════════════════════════════
# Exact keyword matches
# ═════════════════════════════════════════════════════════════════════════════

class TestExactKeywordMatches:
    """Every keyword in HIGH_RISK_KEYWORDS must trigger HIGH classification."""

    @pytest.mark.parametrize("keyword", sorted(HIGH_RISK_KEYWORDS))
    def test_each_keyword_returns_high(self, keyword: str):
        """Each keyword in the frozenset must classify as HIGH when present."""
        question = f"What should I do about {keyword} for my guava trees?"
        result = classify_risk(question)
        assert result == "HIGH", (
            f"Expected 'HIGH' for keyword {keyword!r}, got {result!r}"
        )

    def test_fertilizer_dose(self):
        assert classify_risk("How much fertilizer dose should I apply?") == "HIGH"

    def test_pesticide(self):
        assert classify_risk("Which pesticide works for guava wilt?") == "HIGH"

    def test_fungicide(self):
        assert classify_risk("I need a fungicide recommendation for my crop.") == "HIGH"

    def test_insecticide(self):
        assert classify_risk("Is there an insecticide for fruit fly?") == "HIGH"

    def test_herbicide(self):
        assert classify_risk("What herbicide should I use between rows?") == "HIGH"

    def test_tank_mix(self):
        assert classify_risk("Can I use a tank mix of two products?") == "HIGH"

    def test_chemical(self):
        assert classify_risk("What chemical can I use on my guava?") == "HIGH"

    def test_phosphoric_acid(self):
        assert classify_risk("How do I inject phosphoric acid via drip?") == "HIGH"

    def test_drench(self):
        assert classify_risk("Should I drench the root zone with water?") == "HIGH"

    def test_spray_dose(self):
        assert classify_risk("Tell me the spray dose for copper sulphate.") == "HIGH"

    def test_apply_ml(self):
        assert classify_risk("How many ml should I apply ml per litre?") == "HIGH"

    def test_inject(self):
        assert classify_risk("Can I inject nutrients through drip irrigation?") == "HIGH"


# ═════════════════════════════════════════════════════════════════════════════
# Benign query cases — must return LOW
# ═════════════════════════════════════════════════════════════════════════════

class TestBenignQueries:
    """Questions with no HIGH-risk keywords must return 'LOW'."""

    def test_watering_schedule(self):
        assert classify_risk("When should I water my guava plants?") == "LOW"

    def test_harvest_timing(self):
        assert classify_risk("How do I know when guava is ready to harvest?") == "LOW"

    def test_pruning_question(self):
        assert classify_risk("Should I prune my guava trees this month?") == "LOW"

    def test_crop_age_question(self):
        assert classify_risk("My crop was planted 8 months ago. What stage is it?") == "LOW"

    def test_yield_question(self):
        assert classify_risk("What is the expected yield for guava per tree?") == "LOW"

    def test_weather_question(self):
        assert classify_risk("How does rain affect guava flowering?") == "LOW"

    def test_spacing_question(self):
        assert classify_risk("What is the ideal spacing for guava trees?") == "LOW"

    def test_financial_question(self):
        assert classify_risk("How can I improve my income from guava?") == "LOW"

    def test_empty_except_spaces(self):
        """Whitespace-only question is LOW (no keywords present)."""
        assert classify_risk("     ") == "LOW"

    def test_empty_string(self):
        assert classify_risk("") == "LOW"

    def test_unrelated_domain(self):
        assert classify_risk("How do I set up a drip irrigation schedule?") == "LOW"

    def test_observation_question(self):
        assert classify_risk("I see yellow leaves on some trees — what could cause this?") == "LOW"


# ═════════════════════════════════════════════════════════════════════════════
# Case-insensitivity
# ═════════════════════════════════════════════════════════════════════════════

class TestMixedCaseVariants:
    """Keywords must be detected regardless of letter casing."""

    def test_all_uppercase_pesticide(self):
        assert classify_risk("PESTICIDE RECOMMENDATION NEEDED") == "HIGH"

    def test_title_case_fungicide(self):
        assert classify_risk("I need a Fungicide for my trees.") == "HIGH"

    def test_mixed_case_herbicide(self):
        assert classify_risk("What HerBiCiDe should I use?") == "HIGH"

    def test_mixed_case_tank_mix(self):
        assert classify_risk("What about a TANK MIX?") == "HIGH"

    def test_mixed_case_chemical(self):
        assert classify_risk("Suggest a CHEMICAL treatment.") == "HIGH"

    def test_mixed_case_phosphoric_acid(self):
        assert classify_risk("Is Phosphoric Acid safe for drip?") == "HIGH"

    def test_mixed_case_insecticide(self):
        assert classify_risk("Is there an Insecticide for aphids?") == "HIGH"

    def test_uppercase_drench(self):
        assert classify_risk("Should I DRENCH the soil?") == "HIGH"

    def test_mixed_case_spray_dose(self):
        assert classify_risk("What is the Spray Dose?") == "HIGH"

    def test_mixed_case_fertilizer_dose(self):
        assert classify_risk("FERTILIZER DOSE for nitrogen?") == "HIGH"


# ═════════════════════════════════════════════════════════════════════════════
# Embedded keyword variants (keyword inside a longer sentence)
# ═════════════════════════════════════════════════════════════════════════════

class TestEmbeddedKeywordVariants:
    """Keywords embedded in the middle of text must still trigger HIGH."""

    def test_pesticide_embedded_mid_sentence(self):
        assert classify_risk(
            "My neighbour said I should check for pesticide residue before selling."
        ) == "HIGH"

    def test_fungicide_embedded_in_clause(self):
        assert classify_risk(
            "After the rain I was wondering if a fungicide application is needed."
        ) == "HIGH"

    def test_chemical_embedded(self):
        assert classify_risk(
            "The leaves look burned — could it be a chemical issue?"
        ) == "HIGH"

    def test_tank_mix_at_end(self):
        assert classify_risk(
            "My input dealer suggested making a tank mix."
        ) == "HIGH"

    def test_inject_embedded(self):
        assert classify_risk(
            "Some farmers inject nutrients into the drip line."
        ) == "HIGH"

    def test_apply_ml_embedded(self):
        assert classify_risk(
            "The label says apply ml per 100 litres of water."
        ) == "HIGH"

    def test_drench_embedded(self):
        assert classify_risk(
            "I read that some farmers drench roots with copper solution."
        ) == "HIGH"

    def test_insecticide_embedded(self):
        assert classify_risk(
            "Is there any safe insecticide that won't hurt bees?"
        ) == "HIGH"

    def test_herbicide_at_start(self):
        assert classify_risk(
            "Herbicide use in orchards — is it safe near the tree base?"
        ) == "HIGH"


# ═════════════════════════════════════════════════════════════════════════════
# Multiple keywords in one question
# ═════════════════════════════════════════════════════════════════════════════

class TestMultipleKeywords:
    """A question with multiple keywords must still return HIGH (any one is enough)."""

    def test_multiple_keywords(self):
        assert classify_risk(
            "Can I combine a fungicide with a pesticide in a tank mix?"
        ) == "HIGH"

    def test_safe_prefix_then_keyword(self):
        """Safe words before a risky keyword must not hide the keyword."""
        assert classify_risk(
            "My watering schedule is fine but I need a spray dose."
        ) == "HIGH"
