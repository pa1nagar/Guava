"""
services/rate_limiter.py — Per-IP sliding-window rate limiter.

Implements an in-process sliding-window rate limiter with no Redis dependency.
Each category tracks request timestamps per client IP; timestamps outside the
15-minute window are pruned on every check, keeping memory bounded.

Categories and limits (per 15-minute window per IP):
    login         — 10 requests
    file_upload   — 20 requests
    ai_query      — 30 requests
    contact_form  — 20 requests

Usage (as a FastAPI dependency):
    from services.rate_limiter import RateLimiter

    limiter = RateLimiter("login")

    @router.post("/auth/login")
    def login(request: Request, _: None = Depends(limiter)):
        ...

Note: This module intentionally does NOT use ``from __future__ import
annotations``. ``RateLimiter`` is used as a ``Depends()`` dependency, which
means FastAPI introspects the class instance (not a module-level function).
A class instance has no ``__globals__``, so string-form annotations (which
the future-annotations import produces) cannot be resolved by FastAPI's
``get_typed_signature``. Keeping the ``request: Request`` annotation as a
real type object ensures FastAPI can inject the request without resolution.

Requirements: 3.8, 3.9
"""

import math
import threading
import time
from collections import deque
from typing import Callable

from fastapi import Depends, HTTPException, Request


# ── Window configuration ──────────────────────────────────────────────────────

WINDOW_SECONDS: int = 15 * 60  # 15-minute rolling window

# Per-category maximum requests per IP per window.
CATEGORY_LIMITS: dict[str, int] = {
    "login": 10,
    "file_upload": 20,
    "ai_query": 30,
    "contact_form": 20,
    "market_prices": 60,
    "market_prices_public": 30,
    "admin_ingest": 5,
    "sell_smart_read": 60,
    "sell_smart_write": 20,
    "knowledge_read": 120,
    "knowledge_write": 40,
    "knowledge_export": 10,
    "knowledge_import": 5,
}


# ── Internal state ─────────────────────────────────────────────────────────────

# Structure: _store[category][ip_address] = deque of request timestamps (float)
# All access is serialised through _lock to be thread-safe.
_store: dict[str, dict[str, deque[float]]] = {
    cat: {} for cat in CATEGORY_LIMITS
}
_lock = threading.Lock()


# ── Core check function ────────────────────────────────────────────────────────

def check_rate_limit(category: str, client_ip: str) -> None:
    """Check whether *client_ip* has exceeded the limit for *category*.

    Raises:
        ValueError: if *category* is not a known rate-limit category.
        HTTPException(429): if the per-IP limit has been exceeded, with a
            ``Retry-After`` header indicating seconds until the oldest
            request in the window expires.

    The caller must handle the HTTPException; this function never swallows it.
    This is a pure side-effectful guard — returns None on success.
    """
    if category not in CATEGORY_LIMITS:
        raise ValueError(
            f"Unknown rate-limit category: {category!r}. "
            f"Valid categories: {list(CATEGORY_LIMITS)}"
        )

    limit = CATEGORY_LIMITS[category]
    now = time.monotonic()
    window_start = now - WINDOW_SECONDS

    with _lock:
        if client_ip not in _store[category]:
            _store[category][client_ip] = deque()

        timestamps = _store[category][client_ip]

        # Prune timestamps that have expired (left side of deque = oldest).
        while timestamps and timestamps[0] <= window_start:
            timestamps.popleft()

        if len(timestamps) >= limit:
            # Retry-After: seconds until the oldest request in the window
            # falls outside the window, freeing a slot.
            oldest = timestamps[0]
            retry_after = math.ceil(oldest + WINDOW_SECONDS - now)
            retry_after = max(retry_after, 1)  # always at least 1 second
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit exceeded for category '{category}'. "
                    f"Try again in {retry_after} seconds."
                ),
                headers={"Retry-After": str(retry_after)},
            )

        # Record this request.
        timestamps.append(now)


# ── FastAPI dependency factory ─────────────────────────────────────────────────

class RateLimiter:
    """FastAPI dependency that enforces a per-IP rate limit for a category.

    Usage::

        limiter = RateLimiter("contact_form")

        @router.post("/api/contact")
        def contact(request: Request, _: None = Depends(limiter)):
            ...

    The ``request`` parameter is injected by FastAPI; the client IP is
    extracted from ``request.client.host``, with ``X-Forwarded-For`` checked
    first when the app is behind a proxy.
    """

    def __init__(self, category: str) -> None:
        if category not in CATEGORY_LIMITS:
            raise ValueError(
                f"Unknown rate-limit category: {category!r}. "
                f"Valid categories: {list(CATEGORY_LIMITS)}"
            )
        self.category = category

    def __call__(self, request: Request) -> None:
        """Called by FastAPI on every matching request."""
        client_ip = _extract_ip(request)
        check_rate_limit(self.category, client_ip)


def _extract_ip(request: Request) -> str:
    """Return the best-effort client IP from the request.

    Prefers the first (left-most, most-specific) address in ``X-Forwarded-For``
    when running behind a reverse proxy (Render, Netlify, etc.).
    Falls back to ``request.client.host`` when the header is absent.
    Falls back to ``"unknown"`` as a last resort to avoid crashing.
    """
    forwarded_for = request.headers.get("X-Forwarded-For")
    if forwarded_for:
        # "X-Forwarded-For: client, proxy1, proxy2" — take the leftmost entry.
        return forwarded_for.split(",")[0].strip()
    if request.client and request.client.host:
        return request.client.host
    return "unknown"


# ── Test helpers ───────────────────────────────────────────────────────────────

def _reset_store() -> None:  # pragma: no cover — test helper only
    """Clear all rate-limit state. Used in tests to reset between test cases."""
    with _lock:
        for cat in _store:
            _store[cat].clear()
