"""Fake API responses for the signed-in app pages (farm, plan, tasks, observations, inventory, report).

Shapes follow the response models in backend/routers/*.py. All values are made-up test data.
Three scenarios: ok (data everywhere), empty (valid but empty), error (HTTP 500 on every /api call).
"""
import copy

HIGH_RISK_TEXT = ("Smart Farmer cannot verify the safety and approval status of this recommendation "
                  "- please consult your agronomist or product label.")

TODAY = "2026-11-20"

FARMER = {
    "id": "u1", "crop": "guava", "plant_count": 120, "state": "Test State", "district": "Test District",
    "sowing_date": "2025-06-15", "expected_yield_kg": None, "vendor_recommendation_consent": False,
}

PLAN = {
    "stage_id": "fruit_development", "stage_label": "Fruit Development", "months_elapsed": 17, "days_elapsed": 520,
    "is_final_stage": False,
    "summary": "You are in the Fruit Development stage (9 months since planting). Reference tasks are shown below.",
    "tasks": [
        {"category": "fertilizer", "title": "Apply test fertilizer", "description": "Test description for the fertilizer task.",
         "quantity": 12.5, "unit": "kg"},
        {"category": "irrigation", "title": "Irrigation", "description": "Water every day. Give 10 litres per plant each day.",
         "quantity": 3000, "unit": "litres/day (total for all plants)"},
        {"category": "ipm", "title": "Check: Stem borer", "description": "Inspect shoot tips for wilting or dead tips. Remove affected shoot, insert wire into entry hole to kill larva",
         "quantity": None, "unit": None},
    ],
    "warnings": [], "notes": ["Plan generated from reference data (AI explanation unavailable)."], "from_cache": False,
}

FARMS = [
    {"id": "f1", "name": "Test Farm One", "locality": "Test Village", "district": "Test District", "state": "Test State",
     "country": "India", "timezone": "Asia/Kolkata", "approx_lat": None, "approx_lon": None, "area_value": 2.5,
     "area_unit": "acres", "soil_description": None, "irrigation_method": "Drip", "water_source": None, "notes": None,
     "is_active": True, "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"},
]
PLOTS = [
    {"id": "p1", "farm_id": "f1", "name": "Block A", "area_value": 1.5, "area_unit": "acres", "crop": "Guava",
     "variety": "Test Variety", "planting_date": "2025-06-15", "planting_method": None, "row_spacing_m": 3,
     "within_row_spacing_m": 2, "plant_count": 120, "survival_count": None, "notes": None,
     "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"},
]
PLANT_HISTORY = [{"id": "h1", "plot_id": "p1", "prior_count": 100, "new_count": 120, "changed_at": "2026-03-01T00:00:00"}]

TASKS = [
    {"id": "t1", "title": "Apply test fertilizer to Block A", "due_date": "2026-11-20T00:00:00", "plot_id": None,
     "farm_id": None, "description": "Test description", "source": "manual", "priority": "medium", "status": "due",
     "risk_level": None, "content_record_id": None, "is_ai_generated": False,
     "created_at": "2026-11-01T00:00:00", "updated_at": "2026-11-01T00:00:00"},
    {"id": "t2", "title": "Review test AI suggestion <b>x</b>", "due_date": None, "plot_id": None, "farm_id": None,
     "description": None, "source": "ai", "priority": "high", "status": "needs-review", "risk_level": "HIGH",
     "content_record_id": None, "is_ai_generated": True,
     "created_at": "2026-11-01T00:00:00", "updated_at": "2026-11-01T00:00:00"},
    {"id": "t3", "title": "Prune test rows", "due_date": "2026-11-11T00:00:00", "plot_id": None, "farm_id": None, "description": None,
     "source": "manual", "priority": "low", "status": "completed", "risk_level": None, "content_record_id": None,
     "is_ai_generated": False, "created_at": "2026-11-01T00:00:00", "updated_at": "2026-11-01T00:00:00"},
    {"id": "t4", "title": "Clean test drip lines", "due_date": "2026-11-12T00:00:00", "plot_id": None, "farm_id": None, "description": None,
     "source": "manual", "priority": "low", "status": "completed", "risk_level": None, "content_record_id": None,
     "is_ai_generated": False, "created_at": "2026-11-01T00:00:00", "updated_at": "2026-11-01T00:00:00"},
    {"id": "t5", "title": "Check test fence", "due_date": "2026-11-13T00:00:00", "plot_id": None, "farm_id": None, "description": None,
     "source": "manual", "priority": "low", "status": "due", "risk_level": None, "content_record_id": None,
     "is_ai_generated": False, "created_at": "2026-11-01T00:00:00", "updated_at": "2026-11-01T00:00:00"},
]

INVENTORY = [
    {"id": "i1", "product_name": "Test NPK 19-19-19", "active_ingredient": "19-19-19", "formulation": None,
     "manufacturer": "Test Maker", "batch_number": None, "expiry_date": "2020-01-01", "quantity_on_hand": 5.0,
     "unit": "kg", "purchase_price": 120.0, "label_photo_key": None, "safety_doc_ref": None,
     "supplier_name": "Test Shop", "farm_id": None, "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"},
    {"id": "i2", "product_name": "Test Compost", "active_ingredient": None, "formulation": None, "manufacturer": None,
     "batch_number": None, "expiry_date": None, "quantity_on_hand": 0.0, "unit": "bags", "purchase_price": None,
     "label_photo_key": None, "safety_doc_ref": None, "supplier_name": None, "farm_id": None,
     "created_at": "2026-01-01T00:00:00", "updated_at": "2026-01-01T00:00:00"},
]

# Same-origin 1x1 PNG (tests/e2e/fixtures/photo.png), served by browser_check.py, so photos need no network.
TEST_PHOTO_URL = "https://guavaa.netlify.app/__fixtures__/photo.png"

OBSERVATIONS = [
    {"id": "o1", "user_id": "u1", "plot_id": None, "observed_date": "2026-11-18", "plant_part": "leaves",
     "symptom_description": "Test yellow leaves on <script>alert(1)</script> one corner", "onset_date": None,
     "spread_pattern": "one corner", "severity": "medium", "trees_sampled": 20, "trees_affected": 3,
     "weather_notes": None, "recent_input_notes": None, "observer_name": "Test Farmer", "ai_analysis": None,
     "ai_analysis_label": "Preliminary observation — not a diagnosis", "created_at": "2026-11-18T00:00:00",
     "photos": [{"id": "p1", "is_ai_version": False, "created_at": "2026-11-18T00:00:00", "signed_url": TEST_PHOTO_URL},
                {"id": "p2", "is_ai_version": False, "created_at": "2026-11-18T00:00:00", "signed_url": None}]},
]

ACTIVITIES = [
    {"id": "a1", "activity_type": "Fertilizer", "quantity": 10.0, "unit": "kg", "cost": 1200.0, "notes": None,
     "status": "recorded", "plot_id": None, "method": None, "actor": None, "photo_storage_key": None,
     "logged_date": "2026-11-10", "created_at": "2026-11-10T00:00:00"},
    {"id": "a2", "activity_type": "Labour", "quantity": 4.0, "unit": "hours", "cost": 800.0,
     "notes": "Test pruning the north rows before the rains start", "status": "recorded", "plot_id": None,
     "method": None, "actor": None, "photo_storage_key": None,
     "logged_date": "2026-11-12", "created_at": "2026-11-12T00:00:00"},
]
SPENDING = {"total_cost": 2000.0, "by_type": {"Fertilizer": 1200.0, "Labour": 800.0, "Irrigation": 0.0}}
GAPS = [{"activity_type": "Fertilizer", "expected": 20.0, "actual": 10.0, "unit": "kg", "status": "behind",
         "message": "You may be behind on fertilizer for this stage."}]
FIN_SUMMARY = {"total_cost": 2000.0, "cost_by_type": {"Fertilizer": 1200.0, "Labour": 800.0}, "revenue": 9500.0,
               "profit_or_loss": 7500.0, "net_realisation": 9500.0, "break_even_price_per_kg": 4.5, "has_harvest": True, "currency": "INR",
               "break_even_note": None}
ACTIVITY_TYPES = {"activity_types": ["Fertilizer", "Irrigation", "Pesticide", "Labour", "Other"]}

BASIS = ("Rule of thumb on forecast temperature and rain; not from a published source. "
         "It is a prompt to inspect the orchard, not a diagnosis.")
INSIGHTS = {
    "location": {"district": "Test District", "state": "Test State"},
    "current_stage": {"stage_id": "fruit_development"},
    "weather": {
        "fetched": True,
        "current": {"temperature": 29.5, "weathercode": 2, "weather_desc": "Partly cloudy", "windspeed": 8.2},
        "irrigation": {"status": "normal", "et0": 4.1, "etc": 3.5,
                       "message": "ET0 is 4.1 mm/day — normal water demand. Maintain reference schedule.",
                       "basis": "Estimate. Flat crop coefficient 0.85 for all growth stages, and the demand bands (above 6 and above 3 mm/day) are rules of thumb, not from a source. Check the soil before changing your schedule.",
                       "is_estimate": True},
        "forecast": [{"date": "2026-11-2%d" % i, "weathercode": 1, "tmax": 31, "tmin": 18, "rain_mm": 0 if i % 2 else 4.2,
                      "rain_prob": 10 * i} for i in range(1, 8)],
        "disease_risks": [
            {"disease": "Fruit rot", "risk": "High", "colour": "red",
             "action": "Warm, wet weather favours fruit rot. Walk the orchard, remove and bury rotting fruit, and keep the canopy open to air. Ask your local agriculture officer (KVK) before any spray.",
             "basis": BASIS, "is_estimate": True},
            {"disease": "Powdery mildew", "risk": "Medium", "colour": "amber",
             "action": "Monitor young shoots for a white powder on the leaves. Remove badly affected shoots. Ask your local agriculture officer (KVK) before any spray.",
             "basis": BASIS, "is_estimate": True},
        ],
    },
    "market": {"harvest_timing": {"harvest_month_name": "April", "estimated_harvest_date": "2027-04-01",
                                  "harvest_month_saved_days": 0, "harvest_month_avg_per_kg": None, "is_estimate": True,
                                  "basis": "Estimated date: a calendar assumption of 17 months x 30 days after sowing, not a measurement. Prices shown are saved past prices, not a forecast."},
               "price_history": {"distinct_days": 1}},
    "future_stages": [
        {"label": "Harvest", "month_start": 18, "description": "Test description of the next stage.",
         "fertilizer_name": "Test fertilizer", "fertilizer_kg_per_month": 5, "irrigation_litres_per_day": 2400,
         "ipm_checks": ["Fruit fly", "Fruit rot"]},
    ],
    "climate": {
        "fetched": True, "gdd_cumulative": 4200, "gdd_vs_calendar": "on_track", "gdd_note": "Heat accumulation is consistent with the calendar-based stage.",
        "gdd_thresholds": {"fruit_development": 3500, "harvest": 5000}, "gdd_basis":
        "Estimate typed in by the app developer; no published source. Compare with the calendar stage, do not use alone.",
        "gdd_is_estimate": True, "anomaly_temperature": 0.8, "anomaly_rainfall_mm": -12,
        "anomaly_summary": "This month is 0.8°C warmer than the 30-year average and 12mm less rainfall than normal.",
        "waterlogging_risk": "low", "waterlogging_message": "Rainfall within normal range. No waterlogging risk.",
        "monsoon_cumulative_mm": 640, "monsoon_deficit_pct": -5.5,
    },
    "compliance": {"score": 72, "interpretation": "Moderate compliance (72/100). Consider catching up on fertilizer in the next stage to protect yield.",
                   "logged_fert_kg": 10, "expected_fert_kg": 14},
    "fertilizer_forecast": [
        {"stage_label": "Harvest", "fertilizer": "Test fertilizer A", "total_kg": 30, "rate_per_kg": 20.0,
         "cost_estimate": 600.0, "rate_basis": "Reference prices typed in by the app developer, undated, not live market rates; check your dealer price.",
         "is_estimate": True, "months": 2},
        {"stage_label": "Post-Harvest", "fertilizer": "Test fertilizer B (no price)", "total_kg": 12, "rate_per_kg": None,
         "cost_estimate": None, "rate_basis": "Reference prices typed in by the app developer, undated, not live market rates; check your dealer price.",
         "is_estimate": True, "months": 1},
    ],
}

REPORT = {
    "crop": "guava", "sowing_date": "2025-06-15", "plant_count": 120, "stage_coverage": ["fruit_development"],
    "stages_with_no_activity": ["Pre-Bloom"], "total_cost": 2000.0, "cost_by_type": {"Fertilizer": 1200.0, "Labour": 800.0},
    "revenue": 9500.0, "profit_or_loss": 7500.0, "net_realisation": 9500.0, "break_even_price_per_kg": None,
    "break_even_note": "Break-even needs an expected yield.", "has_harvest": True, "harvest_record": None,
    "scenario_record": None,
    "activity_history": [{"date": "2026-11-10", "activity_type": "Fertilizer", "quantity": 10.0, "unit": "kg",
                          "cost": 1200.0, "notes": "Test <i>note</i>"}],
    "expenses_by_category": {}, "market_prices": [], "currency": "INR",
}

AI_OK = {"response": "Test answer guava trees need steady moisture while fruits grow.", "risk_level": "LOW",
         "is_high_risk_refusal": False}
AI_REFUSAL = {"response": HIGH_RISK_TEXT, "risk_level": "HIGH", "is_high_risk_refusal": True}

# (substring of the request path, fixture). First match wins, so specific paths come first.
OK_ROUTES = [
    ("/plant-count-history", PLANT_HISTORY),
    ("/plots", PLOTS),
    ("/api/farmers/me/farms", FARMS),
    ("/api/farmers/me/tasks/today", [TASKS[0]]),
    ("/api/farmers/me/tasks", TASKS),
    ("/api/farmers/me/inventory", INVENTORY),
    ("/api/farmers/me/observations", OBSERVATIONS),
    ("/api/farmers/me/activities", ACTIVITIES),
    ("/api/farmers/me/spending", SPENDING),
    ("/api/farmers/me/gaps", GAPS),
    ("/api/farmers/me/financial-summary", FIN_SUMMARY),
    ("/api/farmers/me/insights", INSIGHTS),
    ("/api/farmers/me/report", REPORT),
    ("/api/farmers/me/vendor-recommendations", []),
    ("/api/farmers/me", FARMER),
    ("/api/plan", PLAN),
    ("/api/constants/activity-types", ACTIVITY_TYPES),
]


def _empty_variant(path_needle, data):
    if path_needle == "/api/farmers/me/insights":
        d = copy.deepcopy(data)
        d["weather"]["disease_risks"] = []
        d["future_stages"] = []
        d["fertilizer_forecast"] = []
        return d
    if path_needle == "/api/plan":
        d = copy.deepcopy(data)
        d["tasks"] = []
        d["notes"] = []
        return d
    if path_needle == "/api/farmers/me/spending":
        return {"total_cost": 0, "by_type": {}}
    if path_needle == "/api/farmers/me/gaps":
        return []
    if path_needle == "/api/farmers/me/financial-summary":
        d = copy.deepcopy(data)
        d.update(total_cost=0, cost_by_type={}, break_even_price_per_kg=None)
        return d
    if path_needle == "/api/farmers/me/report":
        d = copy.deepcopy(data)
        d.update(total_cost=0, cost_by_type={}, activity_history=[], stages_with_no_activity=[], break_even_note=None)
        return d
    if isinstance(data, list):
        return []
    return data


def response_for(path: str, method: str, body: str, scenario: str):
    """Return (status, json_body) for a mocked API call."""
    if path.startswith("/health"):
        return 200, {"status": "ok"}
    if scenario == "error":
        return 500, {"detail": "Internal error (test)"}
    if method == "POST" and path.startswith("/api/ai/ask"):
        low = (body or "").lower()
        refuse = any(w in low for w in ("dose", "spray", "pesticide", "mix"))
        return 200, (AI_REFUSAL if refuse else AI_OK)
    if method in ("POST", "PUT", "DELETE", "PATCH"):
        if "/photos" in path:
            return 200, {"storage_key": "k", "mime_type": "image/png", "size_bytes": 10, "is_ai_version": False}
        return 200, {"id": "new1"}
    for needle, data in OK_ROUTES:
        if needle in path:
            if scenario == "empty":
                data = _empty_variant(needle, data)
            return 200, data
    return 200, {}
