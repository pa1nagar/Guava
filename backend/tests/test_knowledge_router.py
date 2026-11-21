"""
/api/admin/knowledge endpoints. The repository is an in-memory fake; get_user_id and
get_repo are overridden. No database and no network.
"""
import csv
import io

import pytest
from fastapi.testclient import TestClient

import services.rate_limiter as rl_module
from main import app
from services.auth import get_user_id
from services.knowledge.repo import get_repo
from tests.knowledge_helpers import (
    ADMIN_ID, FARMER_ID, NOCRED_ID, REVIEWER2_ID, REVIEWER_ID, item_dict, members_repo,
)

BASE = "/api/admin/knowledge"
HDR = {"Authorization": "Bearer test-token"}
ID = "GUA-VAR-0001"


@pytest.fixture(autouse=True)
def _reset_limiter():
    rl_module._reset_store()
    yield
    rl_module._reset_store()


@pytest.fixture
def repo():
    r = members_repo()
    app.dependency_overrides[get_repo] = lambda: r
    app.dependency_overrides[get_user_id] = lambda: ADMIN_ID
    yield r
    app.dependency_overrides.pop(get_repo, None)
    app.dependency_overrides.pop(get_user_id, None)


@pytest.fixture
def client():
    return TestClient(app, raise_server_exceptions=False)


def as_user(user_id):
    app.dependency_overrides[get_user_id] = lambda: user_id


def create(client, **over):
    r = client.post(f"{BASE}/items", json={"item": item_dict(**over)}, headers=HDR)
    assert r.status_code == 201, r.text
    return r.json()["item"]


def act(client, action, row, reason=None, item_id=ID):
    return client.post(f"{BASE}/items/{item_id}/{action}",
                       json={"expected_row_version": row["row_version"], "reason": reason}, headers=HDR)


# -- create, read, edit ------------------------------------------------------------------

def test_me(client, repo):
    r = client.get(f"{BASE}/me", headers=HDR)
    assert r.status_code == 200
    assert r.json() == {"user_id": ADMIN_ID, "role": "admin", "email": "admin@example.test",
                        "display_name": "Asha Admin", "credential": None}


def test_create_then_read_back(client, repo):
    row = create(client)
    assert row["status"] == "DRAFT" and row["row_version"] == 1
    detail = client.get(f"{BASE}/items/{ID}", headers=HDR).json()
    assert detail["current"]["payload"]["id"] == ID
    assert detail["allowed_actions"] and "submit" in detail["allowed_actions"]
    assert [a["action"] for a in detail["audit"]] == ["create"]
    assert client.get(f"{BASE}/items/{ID}/versions/1", headers=HDR).json()["version"] == 1
    assert client.get(f"{BASE}/items/{ID}/versions/7", headers=HDR).status_code == 404


def test_duplicate_create_is_409(client, repo):
    create(client)
    r = client.post(f"{BASE}/items", json={"item": item_dict()}, headers=HDR)
    assert r.status_code == 409


def test_edit_and_stale_row_version_409(client, repo):
    row = create(client)
    body = {"item": item_dict(statement_en="A corrected guava variety statement for Madhya Pradesh."),
            "expected_row_version": row["row_version"], "reason": "fix"}
    ok = client.put(f"{BASE}/items/{ID}", json=body, headers=HDR)
    assert ok.status_code == 200 and ok.json()["item"]["current_version"] == 2
    stale = client.put(f"{BASE}/items/{ID}", json={**body, "item": item_dict(
        statement_en="Yet another statement for this guava variety item.")}, headers=HDR)
    assert stale.status_code == 409
    assert len(repo.list_versions(ID)) == 2


def test_unknown_item_is_404_with_generic_body(client, repo):
    r = client.get(f"{BASE}/items/GUA-VAR-0099", headers=HDR)
    assert r.status_code == 404 and r.json() == {"detail": "Not found"}


# -- validation -----------------------------------------------------------------------------

BAD_BODIES = {
    "unknown_field": lambda: {"item": item_dict(), "admin": True},
    "unknown_item_field": lambda: {"item": item_dict(status="APPROVED")},
    "bad_url": lambda: {"item": item_dict(sources=[{**item_dict()["sources"][0], "url": "javascript:alert(1)"}])},
    "long_quote": lambda: {"item": item_dict(sources=[{**item_dict()["sources"][0], "quote": " ".join(["w"] * 31)}])},
    "no_sources": lambda: {"item": item_dict(sources=[])},
    "chemical_not_high": lambda: {"item": item_dict(involves_chemical=True, risk_level="LOW")},
    "bad_id": lambda: {"item": item_dict("lowercase-id")},
    "huge_statement": lambda: {"item": item_dict(statement_en="x" * 5000)},
    "not_json_object": lambda: [],
}


@pytest.mark.parametrize("name", sorted(BAD_BODIES))
def test_validation_gives_422_without_echoing_input(client, repo, name):
    r = client.post(f"{BASE}/items", json=BAD_BODIES[name](), headers=HDR)
    assert r.status_code == 422
    assert "javascript:alert" not in r.text and "xxxx" not in r.text
    assert r.headers["cache-control"] == "no-store"
    assert repo.items == {}


def test_bad_path_id_and_query_values_are_422(client, repo):
    assert client.get(f"{BASE}/items/not-an-id", headers=HDR).status_code == 422
    assert client.get(f"{BASE}/items?page_size=1000", headers=HDR).status_code == 422
    assert client.get(f"{BASE}/items?page=0", headers=HDR).status_code == 422
    assert client.get(f"{BASE}/items?status=EVIL", headers=HDR).status_code == 422
    assert client.get(f"{BASE}/items?q={'a' * 101}", headers=HDR).status_code == 422
    assert client.get(f"{BASE}/audit?item_id=x", headers=HDR).status_code == 422


def test_action_requires_expected_row_version_and_reason_where_needed(client, repo):
    row = create(client)
    assert client.post(f"{BASE}/items/{ID}/submit", json={}, headers=HDR).status_code == 422
    assert act(client, "retire", row, None).status_code == 422
    assert act(client, "retire", row, "ab").status_code == 422
    assert repo.get_item(ID)["status"] == "DRAFT"


# -- list ------------------------------------------------------------------------------------------

def test_list_filters_search_and_paging(client, repo):
    create(client)
    create(client, item_id="GUA-PEST-0001", topic="pests", risk_level="HIGH", involves_chemical=True,
           cibrc_check_required=True, subtopic="fruit_fly")
    create(client, item_id="GUA-VAR-0002", region="MH")
    r = client.get(f"{BASE}/items?page_size=2", headers=HDR).json()
    assert r["total"] == 3 and len(r["items"]) == 2 and r["page_size"] == 2
    assert len(client.get(f"{BASE}/items?page_size=2&page=2", headers=HDR).json()["items"]) == 1
    assert [i["id"] for i in client.get(f"{BASE}/items?risk_level=HIGH", headers=HDR).json()["items"]] == ["GUA-PEST-0001"]
    assert [i["id"] for i in client.get(f"{BASE}/items?region=MH", headers=HDR).json()["items"]] == ["GUA-VAR-0002"]
    assert [i["id"] for i in client.get(f"{BASE}/items?q=fruit_fly", headers=HDR).json()["items"]] == ["GUA-PEST-0001"]
    assert client.get(f"{BASE}/items?status=APPROVED", headers=HDR).json()["total"] == 0


def test_dashboard_counts(client, repo):
    create(client)
    d = client.get(f"{BASE}/dashboard", headers=HDR).json()
    assert d["total"] == 1 and d["by_status"]["DRAFT"] == 1 and d["by_status"]["APPROVED"] == 0
    assert set(d["by_status"]) == {"DRAFT", "IN_REVIEW", "CHANGES_REQUESTED", "APPROVED", "REJECTED", "RETIRED"}


# -- review flow -------------------------------------------------------------------------------------

def test_full_review_flow_and_published_list(client, repo):
    row = create(client)
    row = act(client, "submit", row).json()["item"]
    assert row["status"] == "IN_REVIEW"
    as_user(REVIEWER_ID)
    row = act(client, "approve", row).json()["item"]
    assert row["status"] == "APPROVED" and row["expires_at"]
    pub = client.get(f"{BASE}/published", headers=HDR).json()["items"]
    assert [p["id"] for p in pub] == [ID]
    as_user(ADMIN_ID)
    row = act(client, "retire", row, "found to be wrong").json()["item"]
    assert row["status"] == "RETIRED" and row["retired_reason"] == "found to be wrong"
    assert client.get(f"{BASE}/published", headers=HDR).json()["items"] == []
    row = act(client, "restore", row, "was right after all").json()["item"]
    assert row["status"] == "DRAFT" and row["retired_reason"] is None
    detail = client.get(f"{BASE}/items/{ID}", headers=HDR).json()
    assert [a["action"] for a in reversed(detail["audit"])] == ["create", "submit", "approve", "retire", "restore"]


def test_wrong_status_is_409_and_stale_version_is_409(client, repo):
    row = create(client)
    assert act(client, "approve", row).status_code == 409
    assert client.post(f"{BASE}/items/{ID}/submit", json={"expected_row_version": 5}, headers=HDR).status_code == 409


def test_high_risk_approval_over_http(client, repo):
    create(client, item_id="GUA-PEST-0001", topic="pests", risk_level="HIGH", involves_chemical=True,
           cibrc_check_required=True)
    row = repo.get_item("GUA-PEST-0001")
    row = act(client, "submit", row, item_id="GUA-PEST-0001").json()["item"]
    r = act(client, "approve", row, item_id="GUA-PEST-0001")  # admin
    assert r.status_code == 403 and "reviewer" in r.json()["detail"]
    as_user(NOCRED_ID)
    assert act(client, "approve", row, item_id="GUA-PEST-0001").status_code == 403
    as_user(REVIEWER2_ID)
    assert act(client, "approve", row, item_id="GUA-PEST-0001").status_code == 200
    assert repo.approvals[-1]["approver_credential"] == "Scientist, MPKV Rahuri"


def test_reviewer_proposal_flow(client, repo):
    row = create(client)
    as_user(REVIEWER_ID)
    prop = client.post(f"{BASE}/items/{ID}/proposals", json={
        "item": item_dict(statement_en="A reviewer's better wording of this guava statement."), "reason": "clearer"},
        headers=HDR)
    assert prop.status_code == 201 and prop.json()["proposal_version"] == 2
    assert repo.get_item(ID)["current_version"] == 1
    as_user(ADMIN_ID)
    r = client.post(f"{BASE}/items/{ID}/proposals/2/accept", json={"expected_row_version": row["row_version"]}, headers=HDR)
    assert r.status_code == 200 and r.json()["item"]["current_version"] == 3
    again = client.post(f"{BASE}/items/{ID}/proposals/2/decline",
                        json={"expected_row_version": r.json()["item"]["row_version"], "reason": "too late"}, headers=HDR)
    assert again.status_code == 409


def test_comments(client, repo):
    create(client)
    as_user(REVIEWER_ID)
    r = client.post(f"{BASE}/items/{ID}/comments", json={"body": "Please add the page number."}, headers=HDR)
    assert r.status_code == 201
    assert client.post(f"{BASE}/items/{ID}/comments", json={"body": ""}, headers=HDR).status_code == 422
    assert client.post(f"{BASE}/items/{ID}/comments", json={"body": "x" * 4001}, headers=HDR).status_code == 422
    detail = client.get(f"{BASE}/items/{ID}", headers=HDR).json()
    assert detail["comments"][0]["author_name"] == "Dr Ravi Rao"


def test_audit_list_is_paged_and_filterable(client, repo):
    row = create(client)
    create(client, item_id="GUA-VAR-0002")
    act(client, "submit", row)
    r = client.get(f"{BASE}/audit?page_size=2", headers=HDR).json()
    assert r["total"] == 3 and len(r["entries"]) == 2 and r["entries"][0]["action"] == "submit"
    assert client.get(f"{BASE}/audit?item_id=GUA-VAR-0002", headers=HDR).json()["total"] == 1


# -- seed import, sweep -------------------------------------------------------------------------------

def test_import_seed_over_http(client, repo):
    dry = client.post(f"{BASE}/import-seed", json={"dry_run": True}, headers=HDR).json()
    assert dry["dry_run"] is True and dry["created"] > 0 and repo.items == {}
    real = client.post(f"{BASE}/import-seed", json={"dry_run": False}, headers=HDR).json()
    assert real["created"] == dry["created"] and len(repo.items) == dry["created"]
    again = client.post(f"{BASE}/import-seed", json={}, headers=HDR).json()
    assert again["created"] == 0 and again["skipped_identical"] == dry["created"]
    assert client.post(f"{BASE}/import-seed", json={"path": "/etc/passwd"}, headers=HDR).status_code == 422


def test_sweep_expired_route(client, repo):
    assert client.post(f"{BASE}/sweep-expired", headers=HDR).json() == {"expired": []}


# -- export ---------------------------------------------------------------------------------------------

def test_csv_export_neutralises_formulas(client, repo):
    create(client, subtopic="=SUM(A1)", statement_en="=HYPERLINK(\"http://evil.test\",\"click\")  guava",
           statement_hi="+cmd|' /C calc'!A0 अमरूद")
    r = client.get(f"{BASE}/export.csv", headers=HDR)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    assert "attachment" in r.headers["content-disposition"] and r.headers["cache-control"] == "no-store"
    rows = list(csv.DictReader(io.StringIO(r.text)))
    assert len(rows) == 1
    for col in ("subtopic", "statement_en", "statement_hi"):
        assert rows[0][col].startswith("'"), col
    for cell in rows[0].values():
        assert not cell.startswith(("=", "+", "-", "@"))
    assert repo.audit_log[-1]["action"] == "export"


def test_json_export_has_payloads(client, repo):
    create(client)
    items = client.get(f"{BASE}/export.json", headers=HDR).json()["items"]
    assert items[0]["id"] == ID and items[0]["payload"]["statement_en"].startswith("Guava")


def test_safe_cell_unit():
    from services.knowledge.export import safe_cell
    for bad in ("=1+1", "+1", "-1+2", "@SUM(1)", "\t=1", "\r=1"):
        assert safe_cell(bad).startswith("'")
    assert safe_cell("normal") == "normal" and safe_cell(None) == "" and safe_cell(True) == "true"
    assert safe_cell(5) == 5


# -- reviewers --------------------------------------------------------------------------------------------

def test_reviewer_management(client, repo):
    repo.add_auth_user("99999999-9999-4999-8999-999999999999", "known@example.test")
    r = client.post(f"{BASE}/reviewers", json={"email": "Known@Example.test", "display_name": "Dr K", "credential": "PhD"}, headers=HDR)
    assert r.status_code == 201 and r.json()["result"] == "added"
    assert repo.admins["99999999-9999-4999-8999-999999999999"]["role"] == "reviewer"
    r = client.post(f"{BASE}/reviewers", json={"email": "new@example.test", "display_name": "Dr N"}, headers=HDR)
    assert r.json()["result"] == "invited" and len(repo.invites) == 1
    assert client.post(f"{BASE}/reviewers", json={"email": "new@example.test", "display_name": "Dr N"}, headers=HDR).status_code == 409
    listing = client.get(f"{BASE}/reviewers", headers=HDR).json()
    assert len(listing["members"]) >= 5 and listing["invites"]


def test_existing_admin_cannot_be_turned_into_a_reviewer(client, repo):
    repo.add_auth_user(ADMIN_ID, "admin@example.test")
    r = client.post(f"{BASE}/reviewers", json={"email": "admin@example.test", "display_name": "Demoted"}, headers=HDR)
    assert r.status_code == 409 and repo.admins[ADMIN_ID]["role"] == "admin"


@pytest.mark.parametrize("body", [{"email": "no-at-sign", "display_name": "x"},
                                  {"email": "a@b.co", "display_name": ""},
                                  {"email": "a@b.co", "display_name": "x", "role": "admin"}])
def test_reviewer_body_validation(client, repo, body):
    assert client.post(f"{BASE}/reviewers", json=body, headers=HDR).status_code == 422


def test_cannot_deactivate_self_or_unknown_user(client, repo):
    assert client.post(f"{BASE}/reviewers/{ADMIN_ID}/deactivate", headers=HDR).status_code == 409
    assert client.post(f"{BASE}/reviewers/{FARMER_ID}/deactivate", headers=HDR).status_code == 404
    assert client.post(f"{BASE}/reviewers/not-a-uuid/deactivate", headers=HDR).status_code == 422


# -- rate limits, headers, outages --------------------------------------------------------------------------

@pytest.mark.parametrize("category,method,path,body", [
    ("knowledge_read", "GET", "/me", None),
    ("knowledge_write", "POST", "/sweep-expired", None),
    ("knowledge_export", "GET", "/export.csv", None),
    ("knowledge_import", "POST", "/import-seed", {"dry_run": True}),
])
def test_rate_limit_429(client, repo, monkeypatch, category, method, path, body):
    monkeypatch.setitem(rl_module.CATEGORY_LIMITS, category, 2)
    codes = [client.request(method, BASE + path, json=body, headers=HDR) for _ in range(3)]
    assert [c.status_code for c in codes[:2]] == [200, 200]
    assert codes[2].status_code == 429 and "Retry-After" in codes[2].headers
    assert codes[2].headers["cache-control"] == "no-store"


def test_category_limits_are_registered():
    assert rl_module.CATEGORY_LIMITS["knowledge_read"] == 120
    assert rl_module.CATEGORY_LIMITS["knowledge_write"] == 40
    assert rl_module.CATEGORY_LIMITS["knowledge_export"] == 10
    assert rl_module.CATEGORY_LIMITS["knowledge_import"] == 5


def test_no_store_on_success_and_error_responses(client, repo):
    create(client)
    for r in (client.get(f"{BASE}/me", headers=HDR), client.get(f"{BASE}/items/GUA-VAR-0099", headers=HDR),
              client.get(f"{BASE}/items?page=0", headers=HDR)):
        assert r.headers["cache-control"] == "no-store"
    as_user(FARMER_ID)
    assert client.get(f"{BASE}/me", headers=HDR).headers["cache-control"] == "no-store"


def test_storage_failure_gives_generic_503_and_no_internals(client, repo):
    create(client)
    repo.fail = True
    as_user(ADMIN_ID)
    r = client.get(f"{BASE}/dashboard", headers=HDR)
    assert r.status_code == 503  # the member lookup itself fails first
    repo.fail = False
    repo.admins[ADMIN_ID]["active"] = True
    original = repo.list_items

    def boom(*a, **k):
        from services.knowledge.repo import RepoError
        raise RepoError("select knowledge_items password=secret")
    repo.list_items = boom
    r = client.get(f"{BASE}/items", headers=HDR)
    repo.list_items = original
    assert r.status_code == 503 and r.json() == {"detail": "Service unavailable"}
    assert "secret" not in r.text


def test_conflict_from_the_database_layer_is_409(client, repo, monkeypatch):
    row = create(client)
    from services.knowledge.repo import ConflictError

    def race(payload):
        raise ConflictError("row_version_conflict")
    monkeypatch.setattr(repo, "commit_change", race)
    r = act(client, "submit", row)
    assert r.status_code == 409 and r.json()["detail"].startswith("The record was changed")


def test_item_actions_never_use_delete_or_patch(client, repo):
    create(client)
    for method in ("DELETE", "PATCH"):
        assert client.request(method, f"{BASE}/items/{ID}", headers=HDR).status_code == 405
