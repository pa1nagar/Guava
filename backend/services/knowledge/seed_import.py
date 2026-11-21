"""
seed_import.py - load the bundled guava seed into the knowledge tables as DRAFT.

Reads only backend/data/knowledge/guava_seed.json (never an upload). Each item is
checked against the seed JSON schema and the ItemIn rules. Idempotent. An item
that was reviewed or edited by a person is never overwritten (D8): it may only be
refreshed while it is still DRAFT and every version and audit entry on it came
from this importer.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from pydantic import ValidationError

from services.knowledge import config as cfg
from services.knowledge import diff as diff_mod
from services.knowledge import service as svc
from services.knowledge.access import Principal
from services.knowledge.models import ItemIn
from services.knowledge.repo import KnowledgeRepo

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "knowledge"
SEED_PATH = DATA_DIR / "guava_seed.json"
SCHEMA_PATH = DATA_DIR / "guava_seed.schema.json"
_SEED_ACTIONS = frozenset({"seed_create", "seed_update"})
MAX_INVALID_IDS = 20


def load_seed() -> list[dict]:
    try:
        return json.loads(SEED_PATH.read_text(encoding="utf-8"))["items"]
    except (OSError, ValueError, KeyError):
        raise cfg.KnowledgeError(503, "The bundled seed file is not available")


def _item_validator():
    import jsonschema
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    sub = {"$schema": schema["$schema"], "$defs": schema["$defs"], "$ref": "#/$defs/item"}
    return jsonschema.Draft202012Validator(sub)


def _validate(raw: dict, validator) -> Optional[ItemIn]:
    if next(validator.iter_errors(raw), None) is not None:
        return None
    body = {k: v for k, v in raw.items() if k != "status"}
    try:
        return ItemIn.model_validate(body)
    except ValidationError:
        return None


def _refreshable(repo: KnowledgeRepo, item: dict) -> bool:
    """Still untouched by people: DRAFT, only importer versions, only importer audit entries."""
    if item["status"] != "DRAFT":
        return False
    versions = repo.list_versions(item["id"])
    if any(v.get("is_proposal") or v.get("created_by") != cfg.SEED_ACTOR for v in versions):
        return False
    if repo.list_approvals(item["id"]):
        return False
    audit, _ = repo.list_audit(item["id"], 100, 0)
    return all(a["action"] in _SEED_ACTIONS for a in audit)


def run(repo: KnowledgeRepo, principal: Principal, dry_run: bool = False,
        now: Optional[datetime] = None) -> dict:
    now = now or svc._now()
    validator = _item_validator()
    result = {"created": 0, "updated": 0, "skipped_reviewed": 0, "skipped_identical": 0,
              "invalid": 0, "invalid_ids": [], "dry_run": bool(dry_run)}
    for raw in load_seed():
        item_in = _validate(raw, validator)
        if item_in is None:
            result["invalid"] += 1
            if len(result["invalid_ids"]) < MAX_INVALID_IDS:
                result["invalid_ids"].append(str(raw.get("id"))[:40])
            continue
        payload = item_in.to_payload()
        item_id = payload["id"]
        new_hash = diff_mod.content_hash(payload)
        existing = repo.get_item(item_id)

        if existing is None:
            if not dry_run:
                row = svc.item_row(None, id=item_id, current_version=1, status="DRAFT", approved_at=None,
                                   expires_at=None, retired_reason=None, created_by=cfg.SEED_ACTOR,
                                   **svc.item_fields(payload))
                try:
                    svc.commit(
                        repo, item=row, expected_row_version=None,
                        version=svc.version_row(item_id, 1, payload, cfg.SEED_ACTOR, "seed import", now),
                        audit=svc.audit_row(principal, "seed_create", item_id, None, "DRAFT", None, payload,
                                            "seed import", now),
                    )
                except cfg.KnowledgeError:
                    result["skipped_reviewed"] += 1  # created by a parallel call; leave it
                    continue
            result["created"] += 1
            continue

        current = repo.get_version(item_id, existing["current_version"])
        if current and current.get("content_hash") == new_hash:
            result["skipped_identical"] += 1
            continue
        if not _refreshable(repo, existing):
            result["skipped_reviewed"] += 1
            continue
        if not dry_run:
            number = svc._next_version(repo, item_id)
            row = svc.item_row(existing, current_version=number, **svc.item_fields(payload))
            try:
                svc.commit(
                    repo, item=row, expected_row_version=existing["row_version"],
                    version=svc.version_row(item_id, number, payload, cfg.SEED_ACTOR, "seed update", now),
                    audit=svc.audit_row(principal, "seed_update", item_id, "DRAFT", "DRAFT",
                                        (current or {}).get("payload"), payload, "seed update", now),
                )
            except cfg.KnowledgeError:
                result["skipped_reviewed"] += 1
                continue
        result["updated"] += 1

    if not dry_run:
        svc.commit(
            repo, expected_row_version=None,
            audit=svc.audit_row(principal, "seed_import", None, None, None, None,
                                {k: result[k] for k in ("created", "updated", "skipped_reviewed",
                                                        "skipped_identical", "invalid")},
                                "seed import", now),
        )
    return result
