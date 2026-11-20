"""
test_routes_no_500.py - every non-public route, called without credentials,
answers with a client error (401/403/404/405/422), never 500.
"""
import re

import pytest
from fastapi.testclient import TestClient

from main import app

SKIP_EXACT = {"/docs", "/openapi.json", "/redoc", "/docs/oauth2-redirect", "/health", "/ready", "/api/contact",
              "/api/constants/activity-types"}
SKIP_PREFIX = ("/api/public/",)
ALLOWED = (401, 403, 404, 405, 422)
# Admin routes answer 503 when their secret is not configured (disabled, not open).
ALLOWED_ADMIN = ALLOWED + (503,)


def _cases():
    cases = []
    for route in app.routes:
        path = getattr(route, "path", None)
        methods = getattr(route, "methods", None)
        if not path or not methods:
            continue
        if path in SKIP_EXACT or path.startswith(SKIP_PREFIX):
            continue
        for m in sorted(methods - {"HEAD", "OPTIONS"}):
            cases.append((m, path))
    return cases


CASES = _cases()


def test_there_are_routes_to_check():
    assert len(CASES) > 20


@pytest.mark.parametrize("method,path", CASES)
def test_unauthenticated_call_is_not_500(method, path):
    url = re.sub(r"\{[^}]+\}", "00000000-0000-0000-0000-000000000000", path)
    client = TestClient(app, raise_server_exceptions=False)
    resp = client.request(method, url, json={})
    allowed = ALLOWED_ADMIN if path.startswith("/api/admin/") else ALLOWED
    assert resp.status_code in allowed, (method, path, resp.status_code)