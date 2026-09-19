"""
planner.py — Gemini plan generation (structured JSON output).

Gemini's ONLY job is to produce farmer-friendly explanation text.
All quantities, stage names, and agricultural facts come from the
backend. Gemini must not invent or alter any numeric value.

Contract enforced by the system prompt:
  - Use ONLY the supplied reference data.
  - Do not invent fertilizer names, doses, or timings.
  - Do not change any number.
  - Return valid JSON matching the required schema.
  - If information is missing, use null, not a guess.

Gemini failure is non-fatal: callers fall back to deterministic tasks.

Note on model initialisation:
  The Gemini client is created lazily on first use so that tests can
  import and mock this module without needing GEMINI_API_KEY set.
"""

import json
import logging
import os
import re

import google.generativeai as genai

logger = logging.getLogger(__name__)

# ── Gemini setup — deferred until first call ──────────────────────────────────
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
_MODEL = None  # initialised lazily in _get_model()


def _get_model():
    """Return (and lazily initialise) the Gemini model.

    Raises RuntimeError at call time if GEMINI_API_KEY is absent.
    This allows test imports and mocking without a live key.
    """
    global _MODEL
    if _MODEL is None:
        if not _GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY environment variable is not set. "
                "Add it to your .env file and restart the server."
            )
        genai.configure(api_key=_GEMINI_API_KEY)
        _MODEL = genai.GenerativeModel(
            "gemini-1.5-flash",
            generation_config=genai.GenerationConfig(
                response_mime_type="application/json",
                temperature=0.2,       # low temperature → less hallucination
                max_output_tokens=1024,
            ),
        )
    return _MODEL


# ── Required output schema ────────────────────────────────────────────────────
_REQUIRED_TOP_KEYS = {"summary", "tasks", "warnings", "notes"}
_REQUIRED_TASK_KEYS = {"category", "title", "description"}


def _validate_response(data: dict) -> bool:
    """Return True if the Gemini response matches the required schema."""
    if not isinstance(data, dict):
        return False
    if not _REQUIRED_TOP_KEYS.issubset(data.keys()):
        return False
    if not isinstance(data.get("tasks"), list):
        return False
    for task in data["tasks"]:
        if not isinstance(task, dict):
            return False
        if not _REQUIRED_TASK_KEYS.issubset(task.keys()):
            return False
    return True


def _extract_json(text: str) -> dict | None:
    """Extract a JSON object from a string that may contain markdown fences."""
    if not text or not text.strip():
        return None
    cleaned = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return None


def build_structured_prompt(
    stage: dict,
    plant_count: int,
    scaled: dict,
    state: str,
    district: str,
) -> str:
    """Build the full Gemini prompt for a given stage.

    All quantities are pre-scaled; Gemini must only use these values.
    """
    q = stage.get("quantities", {})
    ipm_items = stage.get("ipm", [])
    ipm_text = "\n".join(
        f"  - Check: {i['check']}. Action: {i['action']}"
        for i in ipm_items
    )

    prompt = f"""SYSTEM_INSTRUCTION:
You are an agricultural assistant helping Indian farmers understand their crop care plan.
You must use ONLY the reference data provided below. Do not add any advice, product names,
quantities, doses, or instructions that are not present in the reference data.
Do not change any number. Do not perform any calculation. Do not invent anything.
Write in simple, plain language that a farmer with little formal education can understand.
Use short sentences. No jargon. No Latin names. Respond in English only.
If information is missing, use null in the JSON output — never invent a value.

The farmer is located in {district}, {state}.
The farmer has {plant_count} guava plants.

REFERENCE_DATA:
Stage: {stage["label"]}
What is happening: {stage["description"]}
Irrigation guidance: {stage["irrigation"]}
  Total irrigation for all {plant_count} plants: {scaled["total_irrigation_litres_per_day"]} litres per day
  Per plant: {q.get("irrigation_litres_per_plant_per_day", 0)} litres per day
Fertilizer guidance: {stage["fertigation"]}
  Total fertilizer for all {plant_count} plants: {scaled["total_fertilizer_kg_per_week"]} kg per week
  Per plant: {q.get("fertilizer_grams_per_plant_per_week", 0)} grams per week
  Fertilizer type: {scaled["fertilizer_name"]}
Pest/disease checks:
{ipm_text if ipm_text else "  No specific pest checks listed for this stage."}

TASK:
Using ONLY the reference data above, produce a JSON object with this exact structure:
{{
  "summary": "<one sentence describing what is happening to the crop right now, in plain farmer language>",
  "tasks": [
    {{
      "category": "irrigation",
      "title": "<short action title>",
      "description": "<plain-language explanation of what to do, using the exact quantities from reference data>",
      "quantity": <number or null>,
      "unit": "<unit string or null>"
    }},
    {{
      "category": "fertilizer",
      "title": "<short action title>",
      "description": "<plain-language explanation>",
      "quantity": <number or null>,
      "unit": "<unit string or null>"
    }},
    {{
      "category": "ipm",
      "title": "<short pest/disease check title>",
      "description": "<plain-language explanation of what to check and what to do>",
      "quantity": null,
      "unit": null
    }}
  ],
  "warnings": ["<any important caution from the reference data, or empty array>"],
  "notes": ["<any additional notes from the reference data, or empty array>"]
}}

Rules:
- Use the exact numerical quantities from REFERENCE_DATA above. Do not round differently.
- Do not add tasks beyond irrigation, fertilizer, and IPM checks present in reference data.
- Do not fabricate pest names, product names, or chemical names not in the reference data.
- The output must be valid JSON only. No markdown, no explanation text outside the JSON.
"""
    return prompt


def generate_plan_structured(
    stage: dict,
    plant_count: int,
    scaled: dict,
    state: str,
    district: str,
) -> dict | None:
    """Call Gemini and return a validated structured plan dict.

    Returns:
        dict   matching the required schema on success.
        None   if Gemini is unavailable or returns invalid data.

    Never raises — callers use None as a signal to fall back to
    deterministic tasks.
    """
    prompt = build_structured_prompt(stage, plant_count, scaled, state, district)
    try:
        model = _get_model()
        response = model.generate_content(prompt)
        raw = response.text.strip()
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc)
        return None

    data = _extract_json(raw)
    if data is None:
        logger.warning("Gemini returned non-JSON response: %.200s", raw)
        return None

    if not _validate_response(data):
        logger.warning("Gemini response failed schema validation: %s", list(data.keys()))
        return None

    return data


# ── Legacy plain-text entry point (backward compatibility) ───────────────────

def _scale_fertigation(fertigation_text: str, plant_count: int) -> str:
    """Replace numeric gram quantities with plant_count-scaled totals."""
    def replacer(match: re.Match) -> str:
        value = float(match.group(1))
        total = value * plant_count
        formatted = int(total) if total == int(total) else round(total, 1)
        return f"{formatted} grams total (for all {plant_count} plants)"
    return re.sub(r"(\d+(?:\.\d+)?)\s+grams?\s+per plant", replacer, fertigation_text)


def generate_plan(stage: dict, plant_count: int) -> str:
    """Legacy plain-text plan generation. Kept for compatibility."""
    scaled_fertigation = _scale_fertigation(stage["fertigation"], plant_count)
    prompt = f"""SYSTEM:
You are an agricultural assistant helping Indian farmers. Use ONLY the reference data. The farmer has {plant_count} plants.

REFERENCE DATA:
Stage: {stage["label"]}
What is happening: {stage["description"]}
Irrigation: {stage["irrigation"]}
Feeding (scaled for {plant_count} plants): {scaled_fertigation}
Pest check: {stage["pest_checks"]}

TASK:
Write a care plan as four short plain-text paragraphs: situation, irrigation, feeding, pest check."""
    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc)
        raise RuntimeError("Gemini unavailable") from exc
