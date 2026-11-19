"""
config.py - every threshold used by Sell smart, each with a written basis.

Rule: a number is allowed here only if it is (a) a unit or logic fact, (b) an
existing repo constant, (c) a published statistical convention, (d) derived by
arithmetic from those or from feed facts, or (e) an input sanity cap.

Constants that already exist in services.mandi_prices are imported here, in
this one place, and nowhere else in the package.
"""

from __future__ import annotations

from services.mandi_prices import (  # noqa: F401  (re-exported single import site)
    MIN_TREND_DAYS,
    QUINTAL_KG,
    STALE_DAYS,
    is_stale,
    per_kg,
)

OUTLIER_MODIFIED_Z = 3.5
MIN_ROBUST_N = 3
FAIRNESS_MIN_MANDIS = MIN_ROBUST_N
TREND_WINDOWS = (7, 14, 30)
VOLATILITY_WINDOW_DAYS = 30
SEASONAL_MIN_YEARS = 2
SEASONAL_MIN_SPAN_DAYS = 730
# Restated from routers.prices.NEARBY_MAX_KM so this package has no web imports;
# a test asserts the two stay equal.
DEFAULT_RADIUS_KM = 300.0

MAX_RADIUS_KM = 1500.0
MAX_COMMISSION_PCT = 100.0
MAX_ALERTS_PER_FARMER = 20
MAX_NAME_LENGTH = 120

# Cross-section price band is the median +/- OUTLIER_MODIFIED_Z robust deviations
# (see quality.py); UNIT_FACTOR is the quintal vs kg slip.
UNIT_FACTOR = 100

THRESHOLDS: dict[str, dict] = {
    "QUINTAL_KG": {
        "value": QUINTAL_KG,
        "basis": "Unit fact. Agmarknet prices are Rs per quintal and one quintal is 100 kg. Reused from services.mandi_prices.",
    },
    "UNIT_FACTOR": {
        "value": UNIT_FACTOR,
        "basis": "Derived from the unit fact: the only unit slip in this feed is quintal vs kg, a factor of exactly 100.",
    },
    "OUTLIER_MODIFIED_Z": {
        "value": OUTLIER_MODIFIED_Z,
        "basis": "Published convention: Iglewicz and Hoaglin (1993) modified z-score 0.6745 x (x - median) / MAD, flag above 3.5. Skipped when MAD is 0.",
    },
    "MIN_ROBUST_N": {
        "value": MIN_ROBUST_N,
        "basis": "Arithmetic: the smallest sample whose median survives one bad value (breakdown point). Minimum observations in any median window, minimum mandis for a 'based on N mandis' claim.",
    },
    "MIN_TREND_DAYS": {
        "value": MIN_TREND_DAYS,
        "basis": "Existing repo constant in services.mandi_prices: minimum distinct saved days before any trend text. Also the volatility minimum.",
    },
    "STALE_DAYS": {
        "value": STALE_DAYS,
        "basis": "Existing repo constant in services.mandi_prices. Fresh means trade date within STALE_DAYS. Also the maximum gap when pairing a sale date to the nearest saved price date.",
    },
    "TREND_WINDOWS": {
        "value": TREND_WINDOWS,
        "basis": "Specified by the owner: 7, 14 and 30 day windows. Change is the median of the latest window vs the median of the previous window of equal length.",
    },
    "VOLATILITY_WINDOW_DAYS": {
        "value": VOLATILITY_WINDOW_DAYS,
        "basis": "The longest owner-specified trend window (30 days). Volatility is median absolute deviation divided by median, reported as a number, never as a forecast.",
    },
    "SEASONAL_MIN_YEARS": {
        "value": SEASONAL_MIN_YEARS,
        "basis": "Owner rule: a seasonal view needs at least 2 years of saved data. A month is shown only if at least this many distinct years each have MIN_ROBUST_N observations in it.",
    },
    "SEASONAL_MIN_SPAN_DAYS": {
        "value": SEASONAL_MIN_SPAN_DAYS,
        "basis": "Derived: 2 years x 365 days. Earliest meaningful date = first saved date + this many days.",
    },
    "DEFAULT_RADIUS_KM": {
        "value": DEFAULT_RADIUS_KM,
        "basis": "Existing repo constant NEARBY_MAX_KM in routers.prices (district-centre to district-centre distance); restated here to avoid importing the web layer.",
    },
    "MAX_RADIUS_KM": {
        "value": MAX_RADIUS_KM,
        "basis": "Input sanity cap, not analytics: longer than any road trip between two guava mandis in the feed states.",
    },
    "MAX_COMMISSION_PCT": {
        "value": MAX_COMMISSION_PCT,
        "basis": "Input sanity cap: a percentage cannot exceed 100.",
    },
    "MAX_ALERTS_PER_FARMER": {
        "value": MAX_ALERTS_PER_FARMER,
        "basis": "Input abuse cap, not analytics: bounds rows and notifications per farmer.",
    },
    "MAX_NAME_LENGTH": {
        "value": MAX_NAME_LENGTH,
        "basis": "Input sanity cap on market and district name length.",
    },
    "ALERT_COOLDOWN": {
        "value": "one notification per crossing, at most one per trade date",
        "basis": "Derived from feed cadence: one price per mandi per trade date and two ingestions a day, so the same trade date is seen twice. Re-arms after the price returns to 'not met'.",
    },
    "FAIRNESS_MIN_MANDIS": {
        "value": MIN_ROBUST_N,
        "basis": "Same median-survival argument as MIN_ROBUST_N: fewer mandis than this gives 'not enough market data that day'.",
    },
}


def threshold_value(name: str):
    return THRESHOLDS[name]["value"]
