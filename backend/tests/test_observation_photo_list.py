"""
test_observation_photo_list.py — GET /api/farmers/me/observations returns saved photos.

Uses a small in-memory fake of the Supabase client that applies .eq() and .in_() filters, so the
owner-only behaviour is tested for real instead of being assumed.
"""
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

import routers.observations as obs_router


class _Result:
    def __init__(self, data):
        self.data = data


class _Query:
    def __init__(self, rows):
        self._rows = list(rows)

    def select(self, *_a, **_k):
        return self

    def eq(self, col, val):
        self._rows = [r for r in self._rows if r.get(col) == val]
        return self

    def in_(self, col, vals):
        self._rows = [r for r in self._rows if r.get(col) in vals]
        return self

    def order(self, col, desc=False):
        self._rows.sort(key=lambda r: r.get(col) or 0, reverse=desc)
        return self

    def execute(self):
        return _Result(self._rows)


class _Bucket:
    def __init__(self, fail):
        self._fail = fail

    def create_signed_url(self, key, seconds):
        if self._fail:
            raise RuntimeError("Bucket not found")
        return {"signedURL": f"https://storage.test/sign/{key}?t=1"}


class _Storage:
    def __init__(self, fail):
        self._fail = fail

    def from_(self, _bucket):
        return _Bucket(self._fail)


class _FakeDb:
    def __init__(self, tables, storage_fails=False):
        self._tables = tables
        self.storage = _Storage(storage_fails)
        self.photo_queries = 0

    def table(self, name):
        if name == "observation_photos":
            self.photo_queries += 1
        return _Query(self._tables.get(name, []))


def _obs(oid, user):
    return {"id": oid, "user_id": user, "observed_date": "2026-11-01", "ai_analysis_label": None,
            "created_at": "2026-11-01T00:00:00"}


def _photo(pid, oid, user, ai=False):
    return {"id": pid, "observation_id": oid, "user_id": user, "storage_key": f"observations/{oid}/{pid}.jpg",
            "is_ai_version": ai, "created_at": "2026-11-01T00:00:00"}


def _get(db, user="user-a"):
    app = FastAPI()
    app.include_router(obs_router.router, prefix="/api")
    app.dependency_overrides[obs_router.get_user_id] = lambda: user
    with patch("routers.observations.get_db", return_value=db):
        return TestClient(app).get("/api/farmers/me/observations")


def test_list_returns_photos_for_owner_with_original_first():
    db = _FakeDb({
        "observations": [_obs("o1", "user-a")],
        "observation_photos": [_photo("p2", "o1", "user-a", ai=True), _photo("p1", "o1", "user-a")],
    })
    resp = _get(db)
    assert resp.status_code == 200
    photos = resp.json()[0]["photos"]
    assert [p["id"] for p in photos] == ["p1", "p2"]
    assert photos[0]["is_ai_version"] is False
    assert photos[0]["signed_url"].startswith("https://storage.test/sign/observations/o1/p1.jpg")


def test_list_uses_one_photo_query_for_all_observations():
    db = _FakeDb({
        "observations": [_obs("o1", "user-a"), _obs("o2", "user-a"), _obs("o3", "user-a")],
        "observation_photos": [_photo("p1", "o1", "user-a"), _photo("p2", "o3", "user-a")],
    })
    resp = _get(db)
    assert resp.status_code == 200
    assert db.photo_queries == 1


def test_list_photos_empty_when_none():
    db = _FakeDb({"observations": [_obs("o1", "user-a")], "observation_photos": []})
    resp = _get(db)
    assert resp.status_code == 200
    assert resp.json()[0]["photos"] == []


def test_signed_url_is_none_when_storage_fails():
    db = _FakeDb(
        {"observations": [_obs("o1", "user-a")], "observation_photos": [_photo("p1", "o1", "user-a")]},
        storage_fails=True,
    )
    resp = _get(db)
    assert resp.status_code == 200
    photos = resp.json()[0]["photos"]
    assert len(photos) == 1
    assert photos[0]["signed_url"] is None


def test_other_users_photos_never_appear():
    db = _FakeDb({
        "observations": [_obs("o1", "user-a")],
        # A photo row that claims the same observation id but belongs to someone else.
        "observation_photos": [_photo("p-other", "o1", "user-b"), _photo("p-mine", "o1", "user-a")],
    })
    resp = _get(db, user="user-a")
    ids = [p["id"] for p in resp.json()[0]["photos"]]
    assert ids == ["p-mine"]


def test_other_users_observation_is_not_listed():
    db = _FakeDb({
        "observations": [_obs("o1", "user-b")],
        "observation_photos": [_photo("p1", "o1", "user-b")],
    })
    resp = _get(db, user="user-a")
    assert resp.status_code == 200
    assert resp.json() == []
