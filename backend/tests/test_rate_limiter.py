"""
tests/test_rate_limiter.py — Unit tests for the per-IP sliding-window rate limiter.

Tests cover:
  - Each category limit triggers 429 on the (N+1)th request.
  - Retry-After header is present and positive on 429 responses.
  - Requests below the limit are allowed without error.
  - Separate IPs are tracked independently.
  - Unknown category raises ValueError, not HTTPException.

Requirements: 3.8, 3.9
"""

from __future__ import annotations

import pytest

from fastapi import HTTPException

# Import module to reset state between tests.
import services.rate_limiter as rl_module
from services.rate_limiter import CATEGORY_LIMITS, WINDOW_SECONDS, check_rate_limit


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear all rate-limit counters before each test."""
    rl_module._reset_store()
    yield
    rl_module._reset_store()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _exhaust_limit(category: str, ip: str) -> None:
    """Make exactly `limit` requests for *category* from *ip* without error."""
    limit = CATEGORY_LIMITS[category]
    for _ in range(limit):
        check_rate_limit(category, ip)


# ── Per-category limit enforcement ───────────────────────────────────────────

class TestLoginLimit:
    """login category: limit = 10 per 15-minute window."""

    CATEGORY = "login"
    LIMIT = CATEGORY_LIMITS["login"]

    def test_requests_within_limit_succeed(self):
        for _ in range(self.LIMIT):
            check_rate_limit(self.CATEGORY, "1.2.3.4")  # no exception

    def test_request_at_limit_plus_one_raises_429(self):
        _exhaust_limit(self.CATEGORY, "1.2.3.4")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(self.CATEGORY, "1.2.3.4")
        assert exc_info.value.status_code == 429

    def test_retry_after_header_present_and_positive(self):
        _exhaust_limit(self.CATEGORY, "1.2.3.4")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(self.CATEGORY, "1.2.3.4")
        headers = exc_info.value.headers or {}
        assert "Retry-After" in headers
        assert int(headers["Retry-After"]) > 0

    def test_different_ips_tracked_independently(self):
        _exhaust_limit(self.CATEGORY, "10.0.0.1")
        # A different IP should not be affected.
        check_rate_limit(self.CATEGORY, "10.0.0.2")  # no exception


class TestFileUploadLimit:
    """file_upload category: limit = 20 per 15-minute window."""

    CATEGORY = "file_upload"
    LIMIT = CATEGORY_LIMITS["file_upload"]

    def test_request_at_limit_plus_one_raises_429(self):
        _exhaust_limit(self.CATEGORY, "1.2.3.4")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(self.CATEGORY, "1.2.3.4")
        assert exc_info.value.status_code == 429

    def test_retry_after_header_present_and_positive(self):
        _exhaust_limit(self.CATEGORY, "1.2.3.4")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(self.CATEGORY, "1.2.3.4")
        headers = exc_info.value.headers or {}
        assert "Retry-After" in headers
        assert int(headers["Retry-After"]) > 0


class TestAiQueryLimit:
    """ai_query category: limit = 30 per 15-minute window."""

    CATEGORY = "ai_query"
    LIMIT = CATEGORY_LIMITS["ai_query"]

    def test_request_at_limit_plus_one_raises_429(self):
        _exhaust_limit(self.CATEGORY, "1.2.3.4")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(self.CATEGORY, "1.2.3.4")
        assert exc_info.value.status_code == 429

    def test_retry_after_header_present_and_positive(self):
        _exhaust_limit(self.CATEGORY, "1.2.3.4")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(self.CATEGORY, "1.2.3.4")
        headers = exc_info.value.headers or {}
        assert "Retry-After" in headers
        assert int(headers["Retry-After"]) > 0


class TestContactFormLimit:
    """contact_form category: limit = 20 per 15-minute window."""

    CATEGORY = "contact_form"
    LIMIT = CATEGORY_LIMITS["contact_form"]

    def test_request_at_limit_plus_one_raises_429(self):
        _exhaust_limit(self.CATEGORY, "1.2.3.4")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(self.CATEGORY, "1.2.3.4")
        assert exc_info.value.status_code == 429

    def test_retry_after_header_present_and_positive(self):
        _exhaust_limit(self.CATEGORY, "1.2.3.4")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(self.CATEGORY, "1.2.3.4")
        headers = exc_info.value.headers or {}
        assert "Retry-After" in headers
        assert int(headers["Retry-After"]) > 0


# ── General behaviour ─────────────────────────────────────────────────────────

class TestGeneralBehaviour:

    def test_unknown_category_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown rate-limit category"):
            check_rate_limit("does_not_exist", "1.2.3.4")

    def test_retry_after_is_at_least_one_second(self):
        """Even if the window is almost elapsed, Retry-After must be >= 1."""
        category = "login"
        _exhaust_limit(category, "5.5.5.5")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(category, "5.5.5.5")
        retry = int(exc_info.value.headers["Retry-After"])
        assert retry >= 1

    def test_retry_after_does_not_exceed_window(self):
        """Retry-After should never exceed the full 15-minute window."""
        category = "login"
        _exhaust_limit(category, "6.6.6.6")
        with pytest.raises(HTTPException) as exc_info:
            check_rate_limit(category, "6.6.6.6")
        retry = int(exc_info.value.headers["Retry-After"])
        assert retry <= WINDOW_SECONDS

    def test_counter_resets_after_window(self):
        """After manually backdating timestamps, a new request should succeed."""
        import time
        from collections import deque

        category = "login"
        ip = "7.7.7.7"
        limit = CATEGORY_LIMITS[category]

        # Pre-populate the store with timestamps that are outside the window.
        past = time.monotonic() - WINDOW_SECONDS - 1
        with rl_module._lock:
            rl_module._store[category][ip] = deque([past] * limit)

        # A new request should succeed because all old timestamps are expired.
        check_rate_limit(category, ip)  # no exception

    def test_categories_are_isolated(self):
        """Exhausting one category does not affect another for the same IP."""
        _exhaust_limit("login", "8.8.8.8")
        # file_upload should still be open for the same IP.
        check_rate_limit("file_upload", "8.8.8.8")  # no exception


# ── RateLimiter dependency class ──────────────────────────────────────────────

class TestRateLimiterDependency:

    def test_invalid_category_raises_value_error_at_construction(self):
        from services.rate_limiter import RateLimiter
        with pytest.raises(ValueError, match="Unknown rate-limit category"):
            RateLimiter("bad_category")

    def test_valid_category_construction_succeeds(self):
        from services.rate_limiter import RateLimiter
        limiter = RateLimiter("login")
        assert limiter.category == "login"

    def test_callable_raises_429_when_limit_exceeded(self):
        """RateLimiter.__call__ should raise HTTPException(429) after the limit."""
        from unittest.mock import MagicMock
        from services.rate_limiter import RateLimiter

        limiter = RateLimiter("contact_form")
        limit = CATEGORY_LIMITS["contact_form"]

        # Build a fake Request with a known IP.
        mock_request = MagicMock()
        mock_request.headers = {}
        mock_request.client.host = "9.9.9.9"

        # Exhaust the limit.
        for _ in range(limit):
            limiter(mock_request)  # no exception

        # One more should raise 429.
        with pytest.raises(HTTPException) as exc_info:
            limiter(mock_request)
        assert exc_info.value.status_code == 429
