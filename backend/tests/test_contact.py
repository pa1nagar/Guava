"""
tests/test_contact.py — Tests for the public contact / join-pilot endpoint.

Covers:
  - Pydantic model validation (pure, no DB):
      * name required, max 100 chars, not blank
      * at least one of email/phone required
      * email format validation
      * phone format validation
  - Endpoint behaviour via a minimal FastAPI app (mocked DB):
      * successful submission (email, phone, both) → 200
      * validation failure → 422
      * rate limit (contact_form: 20 / 15 min) → 429 on the 21st request
      * DB error → 500

Requirements: 2.3, 3.8, 3.9
"""

from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError

import services.rate_limiter as rl_module
from routers import contact as contact_router
from routers.contact import ContactIn


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_rate_limiter():
    """Clear rate-limit counters before and after every test."""
    rl_module._reset_store()
    yield
    rl_module._reset_store()


def _make_app_with_mock_db(monkeypatch, db_raise: bool = False):
    """Build a minimal FastAPI app wired only to the contact router.

    Returns ``(client, inserted_rows)`` where *inserted_rows* captures every
    row passed to ``db.table('contact_submissions').insert(...)``.
    """
    inserted: list[list[dict]] = []

    class _Insert:
        def __init__(self, rows):
            self._rows = rows

        def execute(self):
            if db_raise:
                raise RuntimeError("DB down")
            inserted.append(self._rows)
            return type("R", (), {"data": self._rows})()

    class _Table:
        def __init__(self, name):
            self._name = name

        def insert(self, rows):
            return _Insert(rows)

    class _MockDB:
        def table(self, name):
            return _Table(name)

    monkeypatch.setattr(contact_router, "get_db", lambda: _MockDB())

    app = FastAPI()
    app.include_router(contact_router.router, prefix="/api")
    client = TestClient(app)
    return client, inserted


# ── Model validation (pure) ───────────────────────────────────────────────────

class TestContactInValidation:

    def test_valid_email(self):
        m = ContactIn(name="Ramesh", email="ramesh@example.com")
        assert m.name == "Ramesh"
        assert m.email == "ramesh@example.com"
        assert m.phone is None
        assert m.consent is True

    def test_valid_phone(self):
        m = ContactIn(name="Ramesh", phone="+91 98765 43210")
        assert m.phone == "+91 98765 43210"
        assert m.email is None

    def test_valid_both(self):
        m = ContactIn(name="Ramesh", email="r@e.com", phone="9876543210")
        assert m.email == "r@e.com"
        assert m.phone == "9876543210"

    def test_name_stripped(self):
        m = ContactIn(name="  Ramesh  ", email="r@e.com")
        assert m.name == "Ramesh"

    def test_consent_false_stored(self):
        m = ContactIn(name="Ramesh", email="r@e.com", consent=False)
        assert m.consent is False

    def test_missing_name_rejected(self):
        with pytest.raises(ValidationError):
            ContactIn(email="r@e.com")

    def test_blank_name_rejected(self):
        with pytest.raises(ValidationError):
            ContactIn(name="   ", email="r@e.com")

    def test_name_too_long_rejected(self):
        with pytest.raises(ValidationError):
            ContactIn(name="x" * 101, email="r@e.com")

    def test_name_at_max_length_accepted(self):
        m = ContactIn(name="x" * 100, email="r@e.com")
        assert len(m.name) == 100

    def test_no_contact_method_rejected(self):
        with pytest.raises(ValidationError):
            ContactIn(name="Ramesh")

    def test_empty_email_and_phone_rejected(self):
        with pytest.raises(ValidationError):
            ContactIn(name="Ramesh", email="", phone="")

    def test_invalid_email_rejected(self):
        with pytest.raises(ValidationError):
            ContactIn(name="Ramesh", email="not-an-email")

    def test_email_without_tld_rejected(self):
        with pytest.raises(ValidationError):
            ContactIn(name="Ramesh", email="a@b")

    def test_invalid_phone_rejected(self):
        with pytest.raises(ValidationError):
            ContactIn(name="Ramesh", phone="abc")

    def test_phone_too_short_rejected(self):
        with pytest.raises(ValidationError):
            ContactIn(name="Ramesh", phone="12345")

    def test_email_with_spaces_rejected(self):
        with pytest.raises(ValidationError):
            ContactIn(name="Ramesh", email="a @b.com")


# ── Endpoint behaviour (mocked DB) ────────────────────────────────────────────

class TestContactEndpoint:

    def test_successful_email_submission(self, monkeypatch):
        client, inserted = _make_app_with_mock_db(monkeypatch)
        resp = client.post("/api/contact", json={
            "name": "Ramesh", "email": "ramesh@example.com",
        })
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"
        # One row inserted for the email method.
        assert len(inserted) == 1
        row = inserted[0][0]
        assert row["contact_type"] == "email"
        assert row["contact_value"] == "ramesh@example.com"
        assert row["consent"] is True

    def test_successful_phone_submission(self, monkeypatch):
        client, inserted = _make_app_with_mock_db(monkeypatch)
        resp = client.post("/api/contact", json={
            "name": "Sita", "phone": "9876543210",
        })
        assert resp.status_code == 200
        assert len(inserted) == 1
        row = inserted[0][0]
        assert row["contact_type"] == "phone"
        assert row["contact_value"] == "9876543210"

    def test_both_methods_inserts_two_rows(self, monkeypatch):
        client, inserted = _make_app_with_mock_db(monkeypatch)
        resp = client.post("/api/contact", json={
            "name": "Ramesh", "email": "r@e.com", "phone": "9876543210",
        })
        assert resp.status_code == 200
        assert len(inserted[0]) == 2
        types = {r["contact_type"] for r in inserted[0]}
        assert types == {"email", "phone"}

    def test_consent_false_stored(self, monkeypatch):
        client, inserted = _make_app_with_mock_db(monkeypatch)
        resp = client.post("/api/contact", json={
            "name": "Ramesh", "email": "r@e.com", "consent": False,
        })
        assert resp.status_code == 200
        assert inserted[0][0]["consent"] is False

    def test_missing_name_returns_422(self, monkeypatch):
        client, _ = _make_app_with_mock_db(monkeypatch)
        resp = client.post("/api/contact", json={"email": "r@e.com"})
        assert resp.status_code == 422

    def test_name_too_long_returns_422(self, monkeypatch):
        client, _ = _make_app_with_mock_db(monkeypatch)
        resp = client.post("/api/contact", json={
            "name": "x" * 101, "email": "r@e.com",
        })
        assert resp.status_code == 422

    def test_no_contact_method_returns_422(self, monkeypatch):
        client, _ = _make_app_with_mock_db(monkeypatch)
        resp = client.post("/api/contact", json={"name": "Ramesh"})
        assert resp.status_code == 422

    def test_invalid_email_returns_422(self, monkeypatch):
        client, _ = _make_app_with_mock_db(monkeypatch)
        resp = client.post("/api/contact", json={
            "name": "Ramesh", "email": "not-an-email",
        })
        assert resp.status_code == 422

    def test_db_error_returns_500(self, monkeypatch):
        client, _ = _make_app_with_mock_db(monkeypatch, db_raise=True)
        resp = client.post("/api/contact", json={
            "name": "Ramesh", "email": "r@e.com",
        })
        assert resp.status_code == 500


class TestContactRateLimit:
    """contact_form category: 20 requests / 15 min / IP (Requirement 3.8/3.9)."""

    LIMIT = 20

    def test_requests_within_limit_succeed(self, monkeypatch):
        client, _ = _make_app_with_mock_db(monkeypatch)
        for _ in range(self.LIMIT):
            resp = client.post("/api/contact", json={
                "name": "Ramesh", "email": "r@e.com",
            })
            assert resp.status_code == 200

    def test_request_at_limit_plus_one_returns_429(self, monkeypatch):
        client, _ = _make_app_with_mock_db(monkeypatch)
        for _ in range(self.LIMIT):
            client.post("/api/contact", json={
                "name": "Ramesh", "email": "r@e.com",
            })
        resp = client.post("/api/contact", json={
            "name": "Ramesh", "email": "r@e.com",
        })
        assert resp.status_code == 429
        assert "Retry-After" in resp.headers
        assert int(resp.headers["Retry-After"]) > 0
