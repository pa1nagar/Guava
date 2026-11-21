"""Seed import: bundled file only, schema-validated, idempotent, dry-run, never overwrites reviewed items."""
import copy
import json

import pytest

from services.knowledge import config as cfg
from services.knowledge import seed_import
from services.knowledge import service as svc
from tests.knowledge_helpers import ADMIN, REVIEWER, T0, make_item, members_repo

SEED = json.loads(seed_import.SEED_PATH.read_text(encoding="utf-8"))["items"]


def test_import_creates_every_seed_item_as_draft():
    repo = members_repo()
    out = seed_import.run(repo, ADMIN, now=T0)
    assert out["invalid"] == 0, out["invalid_ids"]
    assert out["created"] == len(SEED) > 0
    assert (out["updated"], out["skipped_reviewed"], out["skipped_identical"]) == (0, 0, 0)
    items = repo.all_items()
    assert len(items) == len(SEED)
    assert {i["status"] for i in items} == {"DRAFT"}
    assert all(i["created_by"] == cfg.SEED_ACTOR for i in items)
    assert all(i["risk_level"] == "HIGH" for i in items if repo.get_version(i["id"], 1)["payload"]["involves_chemical"])
    assert repo.audit_log[-1]["action"] == "seed_import" and repo.audit_log[-1]["actor_id"] == ADMIN.user_id


def test_import_is_idempotent():
    repo = members_repo()
    seed_import.run(repo, ADMIN, now=T0)
    versions, audit = len(repo.versions), len(repo.audit_log)
    out = seed_import.run(repo, ADMIN, now=T0)
    assert out["created"] == 0 and out["updated"] == 0 and out["skipped_identical"] == len(SEED)
    assert len(repo.versions) == versions
    assert len(repo.audit_log) == audit + 1  # only the summary row


def test_dry_run_reports_but_writes_nothing():
    repo = members_repo()
    out = seed_import.run(repo, ADMIN, dry_run=True, now=T0)
    assert out["dry_run"] is True and out["created"] == len(SEED)
    assert repo.commits == 0 and repo.items == {} and len(repo.audit_log) == 0
    seed_import.run(repo, ADMIN, now=T0)
    n = repo.commits
    again = seed_import.run(repo, ADMIN, dry_run=True, now=T0)
    assert again["skipped_identical"] == len(SEED) and repo.commits == n


def _patched(monkeypatch, mutate):
    items = copy.deepcopy(SEED)
    mutate(items)
    monkeypatch.setattr(seed_import, "load_seed", lambda: items)
    return items


def test_untouched_draft_is_refreshed_with_a_new_version(monkeypatch):
    repo = members_repo()
    seed_import.run(repo, ADMIN, now=T0)
    target = SEED[0]["id"]

    def change(items):
        items[0]["statement_en"] = items[0]["statement_en"] + " Updated wording from the seed."
    _patched(monkeypatch, change)
    out = seed_import.run(repo, ADMIN, now=T0)
    assert out["updated"] == 1 and out["skipped_identical"] == len(SEED) - 1
    versions = repo.list_versions(target)
    assert [v["version"] for v in versions] == [1, 2]
    assert versions[1]["change_reason"] == "seed update" and "Updated wording" in versions[1]["payload"]["statement_en"]
    assert "Updated wording" not in versions[0]["payload"]["statement_en"]
    assert repo.get_item(target)["current_version"] == 2


def test_human_edited_item_is_never_overwritten(monkeypatch):
    repo = members_repo()
    seed_import.run(repo, ADMIN, now=T0)
    target = SEED[0]["id"]
    row = repo.get_item(target)
    payload = repo.get_version(target, 1)["payload"]
    edited = {**payload, "statement_en": "An expert rewrote this statement for clarity."}
    from services.knowledge.models import ItemIn
    svc.edit_item(repo, ADMIN, target, ItemIn.model_validate(edited), row["row_version"], "expert edit", now=T0)

    _patched(monkeypatch, lambda items: items[0].update(statement_en=items[0]["statement_en"] + " Seed changed."))
    out = seed_import.run(repo, ADMIN, now=T0)
    assert out["skipped_reviewed"] == 1 and out["updated"] == 0
    assert repo.get_version(target, repo.get_item(target)["current_version"])["payload"]["statement_en"] == \
        "An expert rewrote this statement for clarity."


@pytest.mark.parametrize("move", ["submit", "retire"])
def test_item_that_left_draft_or_was_touched_is_not_overwritten(monkeypatch, move):
    repo = members_repo()
    seed_import.run(repo, ADMIN, now=T0)
    target = SEED[1]["id"]
    row = repo.get_item(target)
    if move == "submit":
        svc.transition(repo, ADMIN, target, "submit", row["row_version"], None, now=T0)
    else:
        row = svc.transition(repo, ADMIN, target, "retire", row["row_version"], "duplicate", now=T0)
        svc.transition(repo, ADMIN, target, "restore", row["row_version"], "it was fine", now=T0)  # DRAFT again
    before = repo.get_version(target, repo.get_item(target)["current_version"])["payload"]

    _patched(monkeypatch, lambda items: items[1].update(statement_en=items[1]["statement_en"] + " Seed changed."))
    out = seed_import.run(repo, ADMIN, now=T0)
    assert out["skipped_reviewed"] == 1
    assert repo.get_version(target, repo.get_item(target)["current_version"])["payload"] == before


def test_reviewed_and_approved_items_are_untouched(monkeypatch):
    repo = members_repo()
    seed_import.run(repo, ADMIN, now=T0)
    low = next(i for i in repo.all_items() if i["risk_level"] == "LOW")
    row = svc.transition(repo, ADMIN, low["id"], "submit", low["row_version"], None, now=T0)
    svc.transition(repo, REVIEWER, low["id"], "approve", row["row_version"], None, now=T0)
    idx = next(n for n, i in enumerate(SEED) if i["id"] == low["id"])
    _patched(monkeypatch, lambda items: items[idx].update(statement_en=items[idx]["statement_en"] + " Seed changed."))
    out = seed_import.run(repo, ADMIN, now=T0)
    assert out["skipped_reviewed"] == 1
    assert repo.get_item(low["id"])["status"] == "APPROVED"


def test_invalid_items_are_counted_and_skipped(monkeypatch):
    repo = members_repo()

    def break_some(items):
        items[0]["sources"][0]["quote"] = " ".join(["word"] * 40)         # quote too long
        items[1]["sources"][0]["url"] = "javascript:alert(1)"           # not http(s)
        items[2]["status"] = "APPROVED"                                  # seed must be DRAFT
        items[3]["surprise"] = True                                      # unknown field
        items[4]["involves_chemical"] = True
        items[4]["risk_level"] = "LOW"                                   # chemical must be HIGH
    _patched(monkeypatch, break_some)
    out = seed_import.run(repo, ADMIN, now=T0)
    assert out["invalid"] == 5 and out["created"] == len(SEED) - 5
    assert len(out["invalid_ids"]) == 5
    assert repo.get_item(SEED[0]["id"]) is None


def test_import_reads_only_the_bundled_file():
    assert seed_import.SEED_PATH.name == "guava_seed.json"
    assert seed_import.SEED_PATH.parent.name == "knowledge" and seed_import.SEED_PATH.parent.parent.name == "data"
    import inspect
    # no path or upload argument: the caller cannot point the importer elsewhere
    assert list(inspect.signature(seed_import.run).parameters) == ["repo", "principal", "dry_run", "now"]


def test_missing_seed_file_is_a_503(monkeypatch, tmp_path):
    monkeypatch.setattr(seed_import, "SEED_PATH", tmp_path / "nope.json")
    with pytest.raises(cfg.KnowledgeError) as e:
        seed_import.load_seed()
    assert e.value.status_code == 503
