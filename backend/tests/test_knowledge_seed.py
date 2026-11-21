"""Validation of the guava knowledge seed (backend/data/knowledge/guava_seed.json).

Pins the honesty rules: every item is DRAFT, every cited source was opened,
every quote is under 30 words, chemical items are HIGH risk and need a CIB&RC check.
"""
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator, FormatChecker

DATA_DIR = Path(__file__).resolve().parent.parent / "data" / "knowledge"
READ_ACCESS = {"opened_read", "opened_partial"}
NOT_READ_ACCESS = {"found_not_opened", "pdf_unreadable"}


@pytest.fixture(scope="module")
def seed():
    return json.loads((DATA_DIR / "guava_seed.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def schema():
    return json.loads((DATA_DIR / "guava_seed.schema.json").read_text(encoding="utf-8"))


def _word_count(text):
    return len(text.split())


def test_schema_is_valid_draft_2020_12(schema):
    Draft202012Validator.check_schema(schema)


def test_seed_validates_against_schema(seed, schema):
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(seed), key=lambda e: list(e.path))
    assert not errors, "\n".join(f"{list(e.path)}: {e.message}" for e in errors[:10])


def test_seed_has_items_and_gaps(seed):
    assert len(seed["items"]) > 0
    assert len(seed["gaps"]) > 0
    assert len(seed["bibliography"]) > 0


def test_ids_are_unique(seed):
    ids = [i["id"] for i in seed["items"]]
    assert len(ids) == len(set(ids))


def test_quotes_are_under_30_words(seed):
    for item in seed["items"]:
        for src in item["sources"]:
            assert _word_count(src["quote"]) < 30, (item["id"], src["quote"])
        for conflict in item["conflicts"]:
            assert _word_count(conflict["quote"]) < 30, (item["id"], conflict["quote"])


def test_chemical_items_are_high_and_need_cibrc_check(seed):
    for item in seed["items"]:
        if item["involves_chemical"]:
            assert item["risk_level"] == "HIGH", item["id"]
            assert item["cibrc_check_required"] is True, item["id"]


def test_every_cited_source_was_opened(seed):
    for item in seed["items"]:
        for src in item["sources"]:
            assert src["access"] in READ_ACCESS, (item["id"], src["url"])


def test_every_cited_url_is_in_bibliography(seed):
    bib_urls = {b["url"] for b in seed["bibliography"]}
    for item in seed["items"]:
        for src in item["sources"]:
            assert src["url"] in bib_urls, (item["id"], src["url"])
        for conflict in item["conflicts"]:
            assert conflict["url"] in bib_urls, (item["id"], conflict["url"])


def test_cited_access_matches_bibliography(seed):
    access_by_url = {b["url"]: b["access"] for b in seed["bibliography"]}
    for item in seed["items"]:
        for src in item["sources"]:
            assert access_by_url[src["url"]] == src["access"], (item["id"], src["url"])


def test_unread_bibliography_entries_are_cited_by_no_item(seed):
    unread = {b["url"] for b in seed["bibliography"] if b["access"] in NOT_READ_ACCESS}
    cited = set()
    for item in seed["items"]:
        cited.update(s["url"] for s in item["sources"])
        cited.update(c["url"] for c in item["conflicts"])
    assert not (unread & cited), unread & cited


def test_status_draft_and_hindi_flags(seed):
    for item in seed["items"]:
        assert item["status"] == "DRAFT", item["id"]
        assert item["hi_machine_translated"] is True, item["id"]
        assert item["hi_reviewed"] is False, item["id"]


def test_conflicts_index_references_existing_items(seed):
    ids = {i["id"] for i in seed["items"]}
    for entry in seed["conflicts_index"]:
        for item_id in entry["item_ids"]:
            assert item_id in ids, item_id
