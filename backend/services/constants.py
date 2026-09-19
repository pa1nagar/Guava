"""
constants.py — Shared application constants.

These are the authoritative definitions used by both backend validation
and surfaced to the frontend. Never define activity types only in JS.
"""

# Allowed activity types for farm_activities.activity_type.
# This list must match the CHECK constraint in schema.sql.
ACTIVITY_TYPES: list[str] = [
    "Fertilizer",
    "Irrigation",
    "Pesticide",
    "Labour",
    "Other",
]

# Maps activity_type to the crop_knowledge quantity field used for
# expected-vs-actual comparison.
ACTIVITY_TYPE_QUANTITY_FIELD: dict[str, str] = {
    "Fertilizer": "total_fertilizer_kg_per_week",
    "Irrigation": "total_irrigation_litres_per_day",
}
