"""
test_planner.py — Tests for services/planner.py

Gemini is MOCKED in all tests — no live API calls.

Covers:
  - generate_plan_structured returns validated dict on success
  - generate_plan_structured returns None on Gemini failure
  - generate_plan_structured returns None on invalid JSON
  - generate_plan_structured returns None on schema mismatch
  - build_structured_prompt contains required sections
  - _validate_response accepts valid structure
  - _validate_response rejects missing keys
  - _extract_json handles markdown fences
"""

import json
import pytest
from unittest.mock import MagicMock, patch
from services.planner import (
    generate_plan_structured,
    build_structured_prompt,
    _validate_response,
    _extract_json,
)

# ── Fixtures ──────────────────────────────────────────────────────────────────

VALID_STAGE = {
    "stage_id": "vegetative_growth",
    "label": "Vegetative Growth",
    "description": "Trees are putting on branches and leaves.",
    "irrigation": "Water every day. Give 4 litres per plant.",
    "fertigation": "Give 7 grams of 19-19-19 per plant per week.",
    "pest_checks": "Look for wilted shoot tips.",
    "quantities": {
        "irrigation_litres_per_plant_per_day": 4,
        "fertilizer_grams_per_plant_per_week": 7,
        "fertilizer_name": "19-19-19 WSF",
        "fertilizer_type": "Fertilizer",
    },
    "ipm": [
        {"pest": "Stem borer", "check": "Inspect shoot tips", "action": "Remove affected shoot"}
    ],
}

VALID_SCALED = {
    "plant_count": 2100,
    "total_irrigation_litres_per_day": 8400.0,
    "total_fertilizer_kg_per_week": 14.7,
    "fertilizer_name": "19-19-19 WSF",
}

VALID_GEMINI_RESPONSE = {
    "summary": "Your trees are in the vegetative growth stage.",
    "tasks": [
        {
            "category": "irrigation",
            "title": "Daily Irrigation",
            "description": "Water all 2100 plants. Total: 8400 litres per day.",
            "quantity": 8400.0,
            "unit": "litres/day",
        },
        {
            "category": "fertilizer",
            "title": "Weekly Feeding",
            "description": "Apply 14.7 kg of 19-19-19 WSF this week.",
            "quantity": 14.7,
            "unit": "kg/week",
        },
        {
            "category": "ipm",
            "title": "Check: Stem borer",
            "description": "Inspect shoot tips. Remove affected shoot.",
            "quantity": None,
            "unit": None,
        },
    ],
    "warnings": [],
    "notes": [],
}


# ── Tests for _validate_response ─────────────────────────────────────────────

class TestValidateResponse:

    def test_valid_response_passes(self):
        assert _validate_response(VALID_GEMINI_RESPONSE) is True

    def test_missing_summary_fails(self):
        bad = {k: v for k, v in VALID_GEMINI_RESPONSE.items() if k != "summary"}
        assert _validate_response(bad) is False

    def test_missing_tasks_fails(self):
        bad = {k: v for k, v in VALID_GEMINI_RESPONSE.items() if k != "tasks"}
        assert _validate_response(bad) is False

    def test_tasks_not_list_fails(self):
        bad = {**VALID_GEMINI_RESPONSE, "tasks": "not a list"}
        assert _validate_response(bad) is False

    def test_task_missing_category_fails(self):
        bad_task = {"title": "T", "description": "D"}  # missing category
        bad = {**VALID_GEMINI_RESPONSE, "tasks": [bad_task]}
        assert _validate_response(bad) is False

    def test_not_a_dict_fails(self):
        assert _validate_response("string") is False
        assert _validate_response([]) is False
        assert _validate_response(None) is False


# ── Tests for _extract_json ───────────────────────────────────────────────────

class TestExtractJson:

    def test_plain_json(self):
        raw = json.dumps(VALID_GEMINI_RESPONSE)
        result = _extract_json(raw)
        assert result["summary"] == VALID_GEMINI_RESPONSE["summary"]

    def test_json_in_markdown_fence(self):
        raw = f"```json\n{json.dumps(VALID_GEMINI_RESPONSE)}\n```"
        result = _extract_json(raw)
        assert result is not None
        assert "summary" in result

    def test_invalid_json_returns_none(self):
        assert _extract_json("not valid json {{{{") is None

    def test_empty_string_returns_none(self):
        assert _extract_json("") is None


# ── Tests for build_structured_prompt ────────────────────────────────────────

class TestBuildStructuredPrompt:

    def test_prompt_contains_stage_label(self):
        prompt = build_structured_prompt(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")
        assert "Vegetative Growth" in prompt

    def test_prompt_contains_plant_count(self):
        prompt = build_structured_prompt(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")
        assert "2100" in prompt

    def test_prompt_contains_scaled_irrigation(self):
        prompt = build_structured_prompt(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")
        assert "8400" in prompt

    def test_prompt_contains_scaled_fertilizer_kg(self):
        prompt = build_structured_prompt(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")
        assert "14.7" in prompt

    def test_prompt_contains_system_instruction(self):
        prompt = build_structured_prompt(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")
        assert "SYSTEM_INSTRUCTION" in prompt
        assert "Do not invent" in prompt

    def test_prompt_contains_location(self):
        prompt = build_structured_prompt(VALID_STAGE, 2100, VALID_SCALED, "Madhya Pradesh", "Dhar")
        assert "Dhar" in prompt
        assert "Madhya Pradesh" in prompt

    def test_prompt_contains_ipm(self):
        prompt = build_structured_prompt(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")
        # The IPM item's 'check' text appears in the prompt.
        assert "Inspect shoot tips" in prompt
        # The action text also appears.
        assert "Remove affected shoot" in prompt


# ── Tests for generate_plan_structured ───────────────────────────────────────

class TestGeneratePlanStructured:

    def test_returns_dict_on_valid_gemini_response(self, mocker):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(VALID_GEMINI_RESPONSE)
        mock_model.generate_content.return_value = mock_response

        mocker.patch("services.planner._MODEL", mock_model)

        result = generate_plan_structured(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")
        assert result is not None
        assert result["summary"] == VALID_GEMINI_RESPONSE["summary"]
        assert len(result["tasks"]) == 3

    def test_returns_none_on_gemini_exception(self, mocker):
        mock_model = MagicMock()
        mock_model.generate_content.side_effect = Exception("API unavailable")

        mocker.patch("services.planner._MODEL", mock_model)

        result = generate_plan_structured(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")
        assert result is None

    def test_returns_none_on_invalid_json(self, mocker):
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = "This is not JSON at all."
        mock_model.generate_content.return_value = mock_response

        mocker.patch("services.planner._MODEL", mock_model)

        result = generate_plan_structured(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")
        assert result is None

    def test_returns_none_on_schema_mismatch(self, mocker):
        bad_response = {"unexpected_key": "value", "tasks": "not a list"}
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(bad_response)
        mock_model.generate_content.return_value = mock_response

        mocker.patch("services.planner._MODEL", mock_model)

        result = generate_plan_structured(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")
        assert result is None

    def test_gemini_called_with_prompt(self, mocker):
        """Verify Gemini receives a prompt string (not empty)."""
        mock_model = MagicMock()
        mock_response = MagicMock()
        mock_response.text = json.dumps(VALID_GEMINI_RESPONSE)
        mock_model.generate_content.return_value = mock_response

        mocker.patch("services.planner._MODEL", mock_model)

        generate_plan_structured(VALID_STAGE, 2100, VALID_SCALED, "MP", "Dhar")

        call_args = mock_model.generate_content.call_args
        prompt_arg = call_args[0][0]
        assert isinstance(prompt_arg, str)
        assert len(prompt_arg) > 100
