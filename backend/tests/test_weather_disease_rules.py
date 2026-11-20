"""
test_weather_disease_rules.py - the disease alert rules give monitoring advice
only: no chemical names, no doses, and every rule says what its basis is.
"""
import re

from services import weather

DOSE_RE = re.compile(r"\d+\s*(g|mg|ml|kg|l|litre|liter|litres|liters|%)(?![a-z])", re.IGNORECASE)
CHEMICAL_WORDS = (
    "copper", "oxychloride", "sulphur", "sulfur", "mancozeb", "chlorpyrifos",
    "imidacloprid", "carbendazim", "thiophanate", "hexaconazole", "propiconazole",
    "azoxystrobin", "streptocycline", "malathion", "cypermethrin", "dimethoate",
    "methyl eugenol", "bordeaux", "fungicide", "pesticide", "insecticide",
)


def _texts(rule_or_risk):
    return [rule_or_risk["action"], rule_or_risk["basis"]]


def test_rules_have_no_dose_or_chemical():
    assert weather.DISEASE_RISK_RULES
    for rule in weather.DISEASE_RISK_RULES:
        for text in _texts(rule):
            assert not DOSE_RE.search(text), (rule["disease"], text)
            low = text.lower()
            for word in CHEMICAL_WORDS:
                assert word not in low, (rule["disease"], word)


def test_every_rule_has_basis_estimate_flag_and_kvk_note():
    for rule in weather.DISEASE_RISK_RULES:
        assert rule["basis"] == weather.DISEASE_RISK_BASIS
        assert rule["is_estimate"] is True
        assert "KVK" in rule["action"]


def test_rule_fires_on_crafted_input_and_carries_basis():
    # Warm, wet day: anthracnose / fruit rot rule.
    risks = weather._disease_risks_for_day(tmax=28, tmin=20, rain_mm=10, rain_prob=80)
    names = [r["disease"] for r in risks]
    assert "Anthracnose / Fruit rot" in names
    for r in risks:
        assert r["basis"] and r["is_estimate"] is True
        assert not DOSE_RE.search(r["action"])


def test_no_rule_fires_on_mild_dry_input():
    assert weather._disease_risks_for_day(tmax=20, tmin=10, rain_mm=0, rain_prob=0) == []


def test_irrigation_advisory_labelled_as_estimate():
    for et0, lpd in ((None, 5), (8.0, 0), (9.0, 5), (5.0, 5), (2.0, 5)):
        adv = weather._irrigation_advisory(et0, lpd)
        assert adv["is_estimate"] is True and adv["basis"], (et0, lpd)
        assert "20%" not in adv["message"]