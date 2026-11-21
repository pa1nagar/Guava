"""
Permission matrix for /api/admin/knowledge: anonymous, authenticated non-admin (farmer),
reviewer and admin against EVERY route. The route list comes from app.routes, so a new
route without a guard fails these tests until it is classified below.
"""
import pytest
from fastapi.testclient import TestClient

import services.rate_limiter as rl_module
from main import app
from services.auth import get_user_id
from services.knowledge import access
from services.knowledge.repo import get_repo
from tests.knowledge_helpers import (
    ADMIN2_ID, ADMIN_ID, FARMER_ID, NOCRED_ID, REVIEWER_ID, members_repo, principal,
)

PREFIX = "/api/admin/knowledge"
HDR = {"Authorization": "Bearer test-token"}
ADMIN_ONLY, SHARED = True, False

# (method, path) -> admin only?
CLASSIFIED = {
    ("GET", "/me"): SHARED,
    ("GET", "/dashboard"): SHARED,
    ("GET", "/items"): SHARED,
    ("POST", "/items"): ADMIN_ONLY,
    ("GET", "/items/{item_id}"): SHARED,
    ("PUT", "/items/{item_id}"): ADMIN_ONLY,
    ("GET", "/items/{item_id}/versions/{number}"): SHARED,
    ("POST", "/items/{item_id}/proposals"): SHARED,
    ("POST", "/items/{item_id}/proposals/{number}/accept"): ADMIN_ONLY,
    ("POST", "/items/{item_id}/proposals/{number}/decline"): ADMIN_ONLY,
    ("POST", "/items/{item_id}/submit"): SHARED,
    ("POST", "/items/{item_id}/approve"): SHARED,
    ("POST", "/items/{item_id}/reject"): SHARED,
    ("POST", "/items/{item_id}/request-changes"): SHARED,
    ("POST", "/items/{item_id}/retire"): ADMIN_ONLY,
    ("POST", "/items/{item_id}/restore"): ADMIN_ONLY,
    ("POST", "/items/{item_id}/comments"): SHARED,
    ("GET", "/audit"): SHARED,
    ("POST", "/import-seed"): ADMIN_ONLY,
    ("POST", "/sweep-expired"): ADMIN_ONLY,
    ("GET", "/export.csv"): ADMIN_ONLY,
    ("GET", "/export.json"): ADMIN_ONLY,
    ("GET", "/published"): SHARED,
    ("GET", "/reviewers"): ADMIN_ONLY,
    ("POST", "/reviewers"): ADMIN_ONLY,
    ("POST", "/reviewers/{user_id}/deactivate"): ADMIN_ONLY,
    ("POST", "/reviewers/{user_id}/reactivate"): ADMIN_ONLY,
}


def _routes():
    out = []
    for route in app.routes:
        path = getattr(route, "path", "")
        if path.startswith(PREFIX):
            for m in sorted((route.methods or set()) - {"HEAD", "OPTIONS"}):
                out.append((m, path[len(PREFIX):]))
    return out


ROUTES = _routes()


def _url(path):
    return PREFIX + (path.replace("{item_id}", "GUA-VAR-0001").replace("{number}", "1")
                     .replace("{user_id}", "11111111-2222-4333-8444-555555555555"))


@pytest.fixture(autouse=True)
def _clean():
    rl_module._reset_store()
    yield
    rl_module._reset_store()
    app.dependency_overrides.pop(get_user_id, None)
    app.dependency_overrides.pop(get_repo, None)


@pytest.fixture
def repo():
    r = members_repo()
    app.dependency_overrides[get_repo] = lambda: r
    return r


def _call(method, path, user_id=None):
    if user_id is None:
        app.dependency_overrides.pop(get_user_id, None)
        headers = {}
    else:
        app.dependency_overrides[get_user_id] = lambda: user_id
        headers = HDR
    return TestClient(app, raise_server_exceptions=False).request(method, _url(path), json={}, headers=headers)


def test_every_route_is_classified_and_only_get_post_put_exist():
    assert len(ROUTES) == len(CLASSIFIED)
    assert set(ROUTES) == set(CLASSIFIED), "classify new routes in CLASSIFIED"
    assert {m for m, _ in ROUTES} <= {"GET", "POST", "PUT"}


@pytest.mark.parametrize("method,path", ROUTES)
def test_anonymous_gets_401(repo, method, path):
    r = _call(method, path, None)
    assert r.status_code == 401, (method, path, r.status_code)
    assert r.headers["cache-control"] == "no-store"


@pytest.mark.parametrize("method,path", ROUTES)
def test_authenticated_non_admin_gets_403(repo, method, path):
    r = _call(method, path, FARMER_ID)
    assert r.status_code == 403, (method, path, r.status_code)
    assert r.json() == {"detail": "Forbidden"}


@pytest.mark.parametrize("method,path", ROUTES)
def test_admin_is_let_in(repo, method, path):
    r = _call(method, path, ADMIN_ID)
    assert r.status_code not in (401, 403), (method, path, r.status_code, r.text[:200])
    assert r.status_code < 500


@pytest.mark.parametrize("method,path", ROUTES)
def test_reviewer_only_reaches_shared_routes(repo, method, path):
    r = _call(method, path, REVIEWER_ID)
    if CLASSIFIED[(method, path)] is ADMIN_ONLY:
        assert r.status_code == 403, (method, path, r.status_code)
        assert r.json() == {"detail": "Forbidden"}
    else:
        assert r.status_code not in (401, 403), (method, path, r.status_code, r.text[:200])


def test_forbidden_body_is_identical_for_every_kind_of_non_admin(repo):
    repo.add_admin(ADMIN2_ID, "admin", active=False)
    bodies = {_call("GET", "/dashboard", u).text for u in (FARMER_ID, ADMIN2_ID, "99999999-9999-4999-8999-999999999999")}
    assert len(bodies) == 1


def test_deactivation_takes_effect_on_the_next_request(repo):
    assert _call("GET", "/me", REVIEWER_ID).status_code == 200
    repo.admins[REVIEWER_ID]["active"] = False
    assert _call("GET", "/me", REVIEWER_ID).status_code == 403


def test_inactive_admin_is_403(repo):
    repo.admins[ADMIN_ID]["active"] = False
    assert _call("GET", "/me", ADMIN_ID).status_code == 403


def test_storage_outage_is_503_not_403_and_not_500(repo):
    repo.fail = True
    r = _call("GET", "/me", ADMIN_ID)
    assert r.status_code == 503 and r.json() == {"detail": "Service unavailable"}


# -- bootstrap and invites ----------------------------------------------------------------

NEWBIE = "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee"


def _empty_repo():
    from tests.fake_knowledge_repo import FakeKnowledgeRepo
    r = FakeKnowledgeRepo()
    app.dependency_overrides[get_repo] = lambda: r
    return r


def test_bootstrap_makes_the_listed_confirmed_email_the_first_admin(monkeypatch):
    r = _empty_repo()
    r.add_auth_user(NEWBIE, "Boss@Example.test", confirmed=True)
    monkeypatch.setenv("ADMIN_BOOTSTRAP_EMAILS", "x@example.test, boss@example.test")
    resp = _call("GET", "/me", NEWBIE)
    assert resp.status_code == 200 and resp.json()["role"] == "admin"
    assert r.audit_log[-1]["action"] == "admin_bootstrap"


def test_bootstrap_needs_a_confirmed_email(monkeypatch):
    r = _empty_repo()
    r.add_auth_user(NEWBIE, "boss@example.test", confirmed=False)
    monkeypatch.setenv("ADMIN_BOOTSTRAP_EMAILS", "boss@example.test")
    assert _call("GET", "/me", NEWBIE).status_code == 403
    assert r.admins == {}


def test_bootstrap_does_nothing_once_an_active_admin_exists(monkeypatch, repo):
    repo.add_auth_user(NEWBIE, "boss@example.test", confirmed=True)
    monkeypatch.setenv("ADMIN_BOOTSTRAP_EMAILS", "boss@example.test")
    assert _call("GET", "/me", NEWBIE).status_code == 403
    assert NEWBIE not in repo.admins


def test_bootstrap_is_off_without_the_env_var(monkeypatch):
    r = _empty_repo()
    r.add_auth_user(NEWBIE, "boss@example.test", confirmed=True)
    monkeypatch.delenv("ADMIN_BOOTSTRAP_EMAILS", raising=False)
    assert _call("GET", "/me", NEWBIE).status_code == 403


def test_a_user_not_on_the_list_is_not_bootstrapped(monkeypatch):
    r = _empty_repo()
    r.add_auth_user(NEWBIE, "someone@example.test", confirmed=True)
    monkeypatch.setenv("ADMIN_BOOTSTRAP_EMAILS", "boss@example.test")
    assert _call("GET", "/me", NEWBIE).status_code == 403


def test_invite_is_consumed_on_first_use(monkeypatch, repo):
    monkeypatch.delenv("ADMIN_BOOTSTRAP_EMAILS", raising=False)
    repo.add_auth_user(NEWBIE, "expert@example.test", confirmed=True)
    invite = repo.add_invite("Expert@example.test", "reviewer", display_name="Dr Expert", credential="PhD")
    resp = _call("GET", "/me", NEWBIE)
    assert resp.status_code == 200
    assert resp.json()["role"] == "reviewer" and resp.json()["credential"] == "PhD"
    assert invite["consumed_at"] is not None
    assert repo.audit_log[-1]["action"] == "invite_consumed"
    assert _call("GET", "/me", NEWBIE).status_code == 200  # now a normal member


def test_expired_or_unconfirmed_invites_do_not_work(monkeypatch, repo):
    monkeypatch.delenv("ADMIN_BOOTSTRAP_EMAILS", raising=False)
    repo.add_auth_user(NEWBIE, "expert@example.test", confirmed=True)
    repo.add_invite("expert@example.test", expires_at="2000-01-01T00:00:00+00:00")
    assert _call("GET", "/me", NEWBIE).status_code == 403
    other = "ffffffff-ffff-4fff-8fff-ffffffffffff"
    repo.add_auth_user(other, "second@example.test", confirmed=False)
    repo.add_invite("second@example.test")
    assert _call("GET", "/me", other).status_code == 403


# -- reviewer management guards --------------------------------------------------------------

def test_last_active_admin_cannot_be_deactivated_and_nobody_can_deactivate_themselves(repo):
    from services.knowledge import service as svc
    from services.knowledge.config import KnowledgeError
    other_admin = principal("admin", ADMIN2_ID, "Other Admin")
    with pytest.raises(KnowledgeError) as e:
        svc.set_member_active(repo, other_admin, ADMIN_ID, False)
    assert e.value.status_code == 409 and "last" in e.value.detail
    with pytest.raises(KnowledgeError) as e:
        svc.set_member_active(repo, principal("admin", ADMIN_ID), ADMIN_ID, False)
    assert e.value.status_code == 409
    assert repo.admins[ADMIN_ID]["active"] is True


def test_admin_can_deactivate_and_reactivate_a_reviewer_and_it_is_audited(repo):
    r = _call("POST", "/reviewers/{user_id}/deactivate".replace("{user_id}", NOCRED_ID), ADMIN_ID)
    assert r.status_code == 200 and repo.admins[NOCRED_ID]["active"] is False
    assert _call("GET", "/me", NOCRED_ID).status_code == 403
    r = _call("POST", "/reviewers/{user_id}/reactivate".replace("{user_id}", NOCRED_ID), ADMIN_ID)
    assert r.status_code == 200 and repo.admins[NOCRED_ID]["active"] is True
    assert [a["action"] for a in repo.audit_log] == ["member_deactivate", "member_reactivate"]
