"""
constants.py — Shared application constants.

Single source of truth for activity types used by:
  - backend validation (routers/activities.py)
  - frontend dropdown (via GET /api/constants/activity-types)
  - database CHECK constraint (schema.sql)

If you add a type here you MUST also update the CHECK constraint in schema.sql.
"""

# Allowed values for farm_activities.activity_type.
# Must match the CHECK constraint in schema.sql exactly.
ACTIVITY_TYPES: list[str] = [
    "Fertilizer",
    "Irrigation",
    "Pesticide",
    "Labour",
    "Other",
]

# Activity types where cost is always zero (product rule: water is free).
# Backend enforces this regardless of what the frontend submits.
ZERO_COST_ACTIVITY_TYPES: set[str] = {"Irrigation"}

# Maps activity_type to the crop_knowledge quantity field used for
# expected-vs-actual comparison.
ACTIVITY_TYPE_QUANTITY_FIELD: dict[str, str] = {
    "Fertilizer": "total_fertilizer_kg_per_week",
    "Irrigation": "total_irrigation_litres_per_day",
}
