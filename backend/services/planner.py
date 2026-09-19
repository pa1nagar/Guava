"""
planner.py — Gemini plan generation.

Builds a grounded prompt from crop_knowledge stage data and calls Gemini Flash.
Gemini must use ONLY the provided reference data — it must not invent advice.
"""

import logging
import os
import re

import google.generativeai as genai

logger = logging.getLogger(__name__)

# Fail fast at startup if the key is missing.
_GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if not _GEMINI_API_KEY:
    raise RuntimeError(
        "GEMINI_API_KEY environment variable is not set. "
        "Add it to your .env file and restart the server."
    )

genai.configure(api_key=_GEMINI_API_KEY)
_MODEL = genai.GenerativeModel("gemini-3.6-flash")


def _scale_fertigation(fertigation_text: str, plant_count: int) -> str:
    """Replace numeric quantities in the fertigation text with plant_count-scaled totals.

    Pattern: matches 'N grams' or 'N gram' (integer or decimal) and multiplies by plant_count.
    Leaves the rest of the text unchanged.
    Example: '5 grams per plant' with plant_count=500 → '2500 grams total'
    """
    def replacer(match: re.Match) -> str:
        value = float(match.group(1))
        total = value * plant_count
        # Format as integer if whole number, otherwise 1 decimal place.
        formatted = int(total) if total == int(total) else round(total, 1)
        return f"{formatted} grams total (for all {plant_count} plants)"

    # Match patterns like "5 grams", "7.5 grams", "5 gram"
    scaled = re.sub(r"(\d+(?:\.\d+)?)\s+grams?\s+per plant", replacer, fertigation_text)
    return scaled


def build_prompt(stage: dict, plant_count: int) -> str:
    """Build the full Gemini prompt for a given stage and plant count.

    Three sections: SYSTEM instruction, REFERENCE DATA, TASK.
    Fertigation quantities are pre-scaled to total for all plants.
    """
    scaled_fertigation = _scale_fertigation(stage["fertigation"], plant_count)

    prompt = f"""SYSTEM:
You are an agricultural assistant helping Indian farmers. You must use ONLY the reference data provided below. Do not add any advice, product names, quantities, or instructions that are not present in the reference data. Do not invent anything. Write in simple, plain language that a farmer with little formal education can understand. Use short sentences. No jargon. No Latin names. The farmer has {plant_count} plants.

REFERENCE DATA (use only this, nothing else):
Stage: {stage["label"]}
What is happening: {stage["description"]}
Irrigation: {stage["irrigation"]}
Feeding (scaled for {plant_count} plants): {scaled_fertigation}
Pest check: {stage["pest_checks"]}

TASK:
Write a care plan for this farmer for the current week. Include exactly these four things:
1. One sentence about what is happening to the crop right now.
2. What to do for irrigation this week.
3. What to do for feeding (fertigation) this week. Use the scaled quantities above.
4. One pest-check action for this week.

Output plain text only. No bullet points. No numbered lists. No markdown. No headings. Write it as four short paragraphs, one for each item."""

    return prompt


def generate_plan(stage: dict, plant_count: int) -> str:
    """Call Gemini Flash and return the plain-text care plan.

    Raises:
        RuntimeError("Gemini unavailable") on any API failure.
        The raw Gemini error is logged server-side but never forwarded to callers.
    """
    prompt = build_prompt(stage, plant_count)
    try:
        response = _MODEL.generate_content(prompt)
        return response.text.strip()
    except Exception as exc:
        logger.error("Gemini API call failed: %s", exc)
        raise RuntimeError("Gemini unavailable") from exc
