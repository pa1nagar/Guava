"""
ai.py — AI assistant proxy endpoint.

Endpoint:
    POST /api/ai/ask

Flow:
  1. Verify JWT (Depends(get_user_id))
  2. Enforce ai_query rate limit (30 per 15-minute window per IP)
  3. classify_risk() — if HIGH, return HIGH_RISK_RESPONSE immediately
  4. build_context() — assemble the farmer's own records as a context string
                        (never includes GPS or another farmer's data)
  5. generate_response() — call Gemini server-side
  6. Return response with limitations prepended (Requirement 14.6)

Gemini failure is non-fatal: generate_response() returns the degraded
fallback message rather than raising, so the rest of the app keeps working
(Requirement 14.7).

The GEMINI_API_KEY is never included in the response or logged at INFO level.

Requirements: 14.1, 14.2, 14.3, 14.4, 14.5, 14.6, 14.7, 14.8, 14.9
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from services.auth import get_user_id
from services.db import get_db
from services.rate_limiter import RateLimiter
from services.ai_proxy import (
    HIGH_RISK_RESPONSE,
    build_context,
    classify_risk,
    generate_response,
    prepend_limitations,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# ai_query rate limit: 30 requests per 15-minute window per IP (Requirement 3.8)
_ai_rate_limiter = RateLimiter("ai_query")


# ── Request / Response models ─────────────────────────────────────────────────

class AIAskRequest(BaseModel):
    """Request body for POST /api/ai/ask."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=2000,
        description="The farmer's question (1–2000 characters).",
    )
    farm_id: Optional[str] = Field(
        None,
        description="Optional: UUID of the farm to use as context.",
    )
    plot_id: Optional[str] = Field(
        None,
        description="Optional: UUID of the plot to use as context.",
    )


class AIAskResponse(BaseModel):
    """Response body for POST /api/ai/ask."""

    response: str = Field(
        ...,
        description=(
            "The AI response, or a HIGH-risk refusal, or a degraded fallback "
            "message when Gemini is unavailable."
        ),
    )
    risk_level: str = Field(
        ...,
        description="'HIGH' if the question was refused; 'LOW' if answered.",
    )
    is_high_risk_refusal: bool = Field(
        ...,
        description="True when the HIGH-risk gate fired and refused to answer.",
    )


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post(
    "/ai/ask",
    response_model=AIAskResponse,
    summary="Ask the Smart Farmer AI assistant a question",
    description=(
        "Sends a farmer question through the HIGH-risk gate, then to Gemini "
        "with the farmer's own context injected server-side. "
        "HIGH-risk questions (pesticides, dosages, tank mixes) are refused "
        "immediately without contacting Gemini. "
        "Gemini failures return a degraded message — never HTTP 5xx."
    ),
    tags=["AI"],
)
def ask_ai(
    payload: AIAskRequest,
    request: Request,
    user_id: str = Depends(get_user_id),
    _rate_limited: None = Depends(_ai_rate_limiter),
) -> AIAskResponse:
    """POST /api/ai/ask — farmer question → AI response.

    Authentication:
        Requires a valid JWT (verified by get_user_id).

    Rate limiting:
        30 requests per 15-minute window per IP (ai_query category).
        Exceeded limit → HTTP 429 with Retry-After header.

    HIGH-risk gate:
        If classify_risk(question) == 'HIGH', returns HIGH_RISK_RESPONSE
        immediately without building context or calling Gemini.
        (Requirement 14.5)

    Context isolation:
        build_context() fetches only the records owned by the authenticated
        farmer. GPS coordinates are never included. (Requirement 14.1)

    Gemini failure:
        generate_response() catches all exceptions and returns the degraded
        fallback message. (Requirement 14.7)

    Returns:
        AIAskResponse with the response text, risk level, and a flag
        indicating whether the HIGH-risk gate fired.
    """
    question = payload.question.strip()
    farm_id = payload.farm_id
    plot_id = payload.plot_id

    # ── Step 1: HIGH-risk gate ────────────────────────────────────────────────
    risk_level = classify_risk(question)
    if risk_level == "HIGH":
        logger.info(
            "HIGH-risk question blocked for user_id=%s (first 50 chars): %.50s",
            user_id,
            question,
        )
        return AIAskResponse(
            response=HIGH_RISK_RESPONSE,
            risk_level="HIGH",
            is_high_risk_refusal=True,
        )

    # ── Step 2: Build context from the farmer's own records ───────────────────
    missing_context: list[str] = []
    context = "No farm context available."
    try:
        db = get_db()
        context = build_context(
            user_id=user_id,
            farm_id=farm_id,
            plot_id=plot_id,
            db=db,
        )
        # If context only says "No farm context available.", flag it.
        if context == "No farm context available.":
            missing_context.append("farm records")
    except Exception as exc:
        logger.error("build_context failed for user_id=%s: %s", user_id, exc)
        missing_context.append("farm records")

    # ── Step 3: Call Gemini server-side ───────────────────────────────────────
    # generate_response() never raises — it returns the degraded fallback
    # message on any Gemini error. (Requirement 14.7)
    response_text = generate_response(
        question=question,
        context=context,
        missing_context=missing_context,
    )

    return AIAskResponse(
        response=response_text,
        risk_level="LOW",
        is_high_risk_refusal=False,
    )
