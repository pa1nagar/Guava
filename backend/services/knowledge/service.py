"""
service.py - orchestration of every knowledge action over a KnowledgeRepo.

Rules live in status.py (pure); this module reads state, applies the rules and
writes through repo.commit_change(), which stores the item row, version row,
approval row, comment row and the audit row in one transaction. Nothing here
deletes or rewrites history.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from services.knowledge import config as cfg
from services.knowledge import diff as diff_mod
from services.knowledge import status as st
from services.knowledge.access import Principal
from services.knowledge.models import ItemIn, ReviewerIn
from services.knowledge.repo import ConflictError, KnowledgeRepo

KnowledgeError = cfg.KnowledgeError

ITEM_KEYS = (
    "id", "current_version", "status", "risk_level", "topic", "subtopic", "summary", "region",
    "has_conflict", "approved_at", "expires_at", "retired_reason", "created_by",
)
# Actions a reviewer may take; everything else is admin only.
REVIEWER_ACTIONS = frozenset({"submit", "approve", "reject", "request_changes"})
_PROPOSAL_DECISIONS = ("proposal_accept", "proposal_decline")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


# -- row builders (also used by seed_import) -----------------------------------------

def item_fields(payload: dict) -> dict:
    """Searchable columns derived from a version payload."""
    return {
        "topic": payload["topic"],
        "subtopic": payload.get("subtopic"),
        "summary": (payload.get("statement_en") or "")[:200],
        "region": payload["region"],
        "risk_level": payload["risk_level"],
        "has_conflict": bool(payload.get("conflicts")),
    }


def item_row(existing: Optional[dict], **over: Any) -> dict:
    base = {k: (existing or {}).get(k) for k in ITEM_KEYS}
    base.update(over)
    return base


def version_row(item_id: str, number: int, payload: dict, created_by: Optional[str], reason: Optional[str],
                now: datetime, is_proposal: bool = False) -> dict:
    return {
        "item_id": item_id, "version": number, "is_proposal": is_proposal, "payload": payload,
        "content_hash": diff_mod.content_hash(payload), "created_by": created_by,
        "created_at": _iso(now), "change_reason": reason,
    }


def audit_row(principal: Optional[Principal], action: str, item_id: Optional[str], from_status: Optional[str],
              to_status: Optional[str], before: Optional[dict], after: Optional[dict],
              reason: Optional[str], now: datetime) -> dict:
    return {
        "actor_id": principal.user_id if principal else None,
        "actor_role": principal.role if principal else "system",
        "actor_name": principal.actor_name if principal else "system",
        "action": action, "item_id": item_id, "from_status": from_status, "to_status": to_status,
        "before": before, "after": after, "diff": diff_mod.diff(before, after),
        "reason": reason, "created_at": _iso(now),
    }


def commit(repo: KnowledgeRepo, **parts: Any) -> dict:
    """repo.commit_change with the conflict error turned into a client 409."""
    try:
        return repo.commit_change(parts)
    except ConflictError:
        raise KnowledgeError(409, "The record was changed by someone else. Reload and try again")


# -- reads used by several actions ---------------------------------------------------

def _load(repo: KnowledgeRepo, item_id: str) -> dict:
    item = repo.get_item(item_id)
    if not item:
        raise KnowledgeError(404, "Not found")
    return item


def _check_row_version(item: dict, expected: int) -> None:
    if int(item["row_version"]) != int(expected):
        raise KnowledgeError(409, "The record was changed by someone else. Reload and try again")


def _current(repo: KnowledgeRepo, item: dict) -> dict:
    ver = repo.get_version(item["id"], item["current_version"])
    if not ver:
        raise KnowledgeError(409, "The record is inconsistent")
    return ver


def _next_version(repo: KnowledgeRepo, item_id: str) -> int:
    return max((v["version"] for v in repo.list_versions(item_id)), default=0) + 1


def _state(item: dict) -> dict:
    return {k: item.get(k) for k in ("status", "current_version", "approved_at", "expires_at", "retired_reason")}


def pending_proposals(versions: list[dict], approvals: list[dict]) -> list[dict]:
    resolved = {a["version"] for a in approvals if a["decision"] in _PROPOSAL_DECISIONS}
    return [v for v in versions if v.get("is_proposal") and v["version"] not in resolved]


# -- create / edit / propose --------------------------------------------------------------

def create_item(repo: KnowledgeRepo, principal: Principal, item_in: ItemIn, now: Optional[datetime] = None) -> dict:
    now = now or _now()
    payload = item_in.to_payload()
    if repo.get_item(payload["id"]):
        raise KnowledgeError(409, "An item with this id already exists")
    row = item_row(None, id=payload["id"], current_version=1, status="DRAFT", approved_at=None,
                   expires_at=None, retired_reason=None, created_by=principal.user_id, **item_fields(payload))
    return commit(
        repo, item=row, expected_row_version=None,
        version=version_row(payload["id"], 1, payload, principal.user_id, "created", now),
        audit=audit_row(principal, "create", payload["id"], None, "DRAFT", None, payload, None, now),
    )


def edit_item(repo: KnowledgeRepo, principal: Principal, item_id: str, item_in: ItemIn,
              expected_row_version: int, reason: Optional[str], now: Optional[datetime] = None) -> dict:
    now = now or _now()
    item = _load(repo, item_id)
    payload = item_in.to_payload()
    if payload["id"] != item_id:
        raise KnowledgeError(422, "The item id cannot be changed")
    _check_row_version(item, expected_row_version)
    target = st.require_transition("edit", item["status"])
    cur = _current(repo, item)
    if diff_mod.content_hash(payload) == cur["content_hash"]:
        raise KnowledgeError(422, "No changes to save")
    number = _next_version(repo, item_id)
    row = item_row(item, current_version=number, status=target, approved_at=None, expires_at=None,
                   **item_fields(payload))
    return commit(
        repo, item=row, expected_row_version=expected_row_version,
        version=version_row(item_id, number, payload, principal.user_id, st.clean_reason("edit", reason), now),
        audit=audit_row(principal, "edit", item_id, item["status"], target, cur["payload"], payload,
                        st.clean_reason("edit", reason), now),
    )


def propose_edit(repo: KnowledgeRepo, principal: Principal, item_id: str, item_in: ItemIn,
                 reason: Optional[str], now: Optional[datetime] = None) -> dict:
    """A reviewer's suggested change. The current version is not touched (D5)."""
    now = now or _now()
    item = _load(repo, item_id)
    payload = item_in.to_payload()
    if payload["id"] != item_id:
        raise KnowledgeError(422, "The item id cannot be changed")
    if item["status"] == "RETIRED":
        raise KnowledgeError(409, "A retired item cannot be changed")
    cur = _current(repo, item)
    if diff_mod.content_hash(payload) == cur["content_hash"]:
        raise KnowledgeError(422, "No changes to propose")
    number = _next_version(repo, item_id)
    reason = st.clean_reason("propose", reason)
    commit(
        repo, expected_row_version=None,
        version=version_row(item_id, number, payload, principal.user_id, reason, now, is_proposal=True),
        audit=audit_row(principal, "propose", item_id, item["status"], item["status"], cur["payload"], payload,
                        reason, now),
    )
    return {"item_id": item_id, "proposal_version": number}


def _pending_proposal(repo: KnowledgeRepo, item_id: str, number: int) -> dict:
    ver = repo.get_version(item_id, number)
    if not ver or not ver.get("is_proposal"):
        raise KnowledgeError(404, "Not found")
    if any(a["version"] == number and a["decision"] in _PROPOSAL_DECISIONS for a in repo.list_approvals(item_id)):
        raise KnowledgeError(409, "This proposal was already decided")
    return ver


def _decision_row(principal: Principal, item_id: str, number: int, decision: str, reason: Optional[str],
                  expires_at: Optional[datetime], now: datetime) -> dict:
    return {
        "item_id": item_id, "version": number, "decision": decision,
        "approver_id": principal.user_id, "approver_role": principal.role,
        "approver_name": principal.display_name, "approver_credential": principal.credential,
        "reason": reason, "expires_at": _iso(expires_at) if expires_at else None, "created_at": _iso(now),
    }


def accept_proposal(repo: KnowledgeRepo, principal: Principal, item_id: str, number: int,
                    expected_row_version: int, reason: Optional[str], now: Optional[datetime] = None) -> dict:
    now = now or _now()
    item = _load(repo, item_id)
    _check_row_version(item, expected_row_version)
    target = st.require_transition("accept_proposal", item["status"])
    prop = _pending_proposal(repo, item_id, number)
    cur = _current(repo, item)
    new_number = _next_version(repo, item_id)
    payload = prop["payload"]
    reason = st.clean_reason("accept_proposal", reason)
    row = item_row(item, current_version=new_number, status=target, approved_at=None, expires_at=None,
                   **item_fields(payload))
    # The proposer stays the author of the accepted version (matters for the HIGH approval rule).
    return commit(
        repo, item=row, expected_row_version=expected_row_version,
        version=version_row(item_id, new_number, payload, prop.get("created_by"),
                            f"accepted proposal v{number}", now),
        approval=_decision_row(principal, item_id, number, "proposal_accept", reason, None, now),
        audit=audit_row(principal, "proposal_accept", item_id, item["status"], target, cur["payload"], payload,
                        reason, now),
    )


def decline_proposal(repo: KnowledgeRepo, principal: Principal, item_id: str, number: int,
                     expected_row_version: int, reason: Optional[str], now: Optional[datetime] = None) -> dict:
    now = now or _now()
    item = _load(repo, item_id)
    _check_row_version(item, expected_row_version)
    prop = _pending_proposal(repo, item_id, number)
    reason = st.clean_reason("decline_proposal", reason)
    commit(
        repo, expected_row_version=None,
        approval=_decision_row(principal, item_id, number, "proposal_decline", reason, None, now),
        audit=audit_row(principal, "proposal_decline", item_id, item["status"], item["status"],
                        prop["payload"], None, reason, now),
    )
    return {"item_id": item_id, "declined_version": number}


# -- status actions -------------------------------------------------------------------------

def transition(repo: KnowledgeRepo, principal: Principal, item_id: str, action: str,
               expected_row_version: int, reason: Optional[str], now: Optional[datetime] = None) -> dict:
    """submit, approve, reject, request_changes, retire, restore."""
    if action not in ("submit", "approve", "reject", "request_changes", "retire", "restore"):
        raise KnowledgeError(404, "Not found")
    if principal.role != "admin" and action not in REVIEWER_ACTIONS:
        raise KnowledgeError(403, "Forbidden")
    now = now or _now()
    item = _load(repo, item_id)
    _check_row_version(item, expected_row_version)
    reason = st.clean_reason(action, reason)
    target = st.require_transition(action, item["status"])
    cur = _current(repo, item)

    approved_at, expires_at, retired_reason = None, None, None
    approval = None
    if action == "approve":
        problem = st.approval_problem(item["risk_level"], principal.as_approver(), cur.get("created_by"))
        if problem:
            raise KnowledgeError(403, problem)
        approved_at, expires = now, st.expiry_for(now)
        expires_at = expires
        approval = _decision_row(principal, item_id, item["current_version"], "approve", reason, expires, now)
    elif action in ("reject", "request_changes"):
        approval = _decision_row(principal, item_id, item["current_version"], action, reason, None, now)
    elif action == "retire":
        retired_reason = reason

    row = item_row(
        item, status=target,
        approved_at=_iso(approved_at) if approved_at else None,
        expires_at=_iso(expires_at) if expires_at else None,
        retired_reason=retired_reason,
    )
    after_state = _state(row)
    parts: dict[str, Any] = dict(
        item=row, expected_row_version=expected_row_version,
        audit=audit_row(principal, action, item_id, item["status"], target, _state(item), after_state, reason, now),
    )
    if approval:
        parts["approval"] = approval
    return commit(repo, **parts)


def add_comment(repo: KnowledgeRepo, principal: Principal, item_id: str, body: str,
                version: Optional[int], now: Optional[datetime] = None) -> dict:
    now = now or _now()
    item = _load(repo, item_id)
    if version is not None and not repo.get_version(item_id, version):
        raise KnowledgeError(404, "Not found")
    row = {
        "item_id": item_id, "version": version, "author_id": principal.user_id,
        "author_role": principal.role, "author_name": principal.display_name,
        "body": body, "created_at": _iso(now),
    }
    commit(
        repo, expected_row_version=None, comment=row,
        audit=audit_row(principal, "comment", item_id, item["status"], item["status"], None,
                        {"comment": body[:500]}, None, now),
    )
    return row


def sweep_expired(repo: KnowledgeRepo, now: Optional[datetime] = None) -> list[str]:
    """Move items whose approval lapsed back to IN_REVIEW. Idempotent; audited as 'system'."""
    now = now or _now()
    changed: list[str] = []
    for item in repo.list_expired(_iso(now)):
        target = st.next_status("expire", item["status"])
        if target is None:
            continue
        row = item_row(item, status=target, approved_at=None, expires_at=None)
        try:
            repo.commit_change({
                "item": row, "expected_row_version": item["row_version"],
                "audit": audit_row(None, "approval_expired", item["id"], item["status"], target,
                                   _state(item), _state(row), "approval validity ended", now),
            })
        except ConflictError:
            continue  # someone else changed it first; the next sweep re-checks
        changed.append(item["id"])
    return changed


# -- reads ------------------------------------------------------------------------------------

def dashboard(repo: KnowledgeRepo, now: Optional[datetime] = None) -> dict:
    now = now or _now()
    swept = sweep_expired(repo, now)
    items = repo.all_items()
    by_status = {s: 0 for s in cfg.STATUSES}
    by_risk = {r: 0 for r in cfg.RISK_LEVELS}
    by_topic: dict[str, int] = {}
    by_region = {r: 0 for r in cfg.REGIONS}
    soon, limit = [], now + timedelta(days=cfg.EXPIRING_SOON_DAYS)
    for it in items:
        by_status[it["status"]] = by_status.get(it["status"], 0) + 1
        by_risk[it["risk_level"]] = by_risk.get(it["risk_level"], 0) + 1
        by_topic[it["topic"]] = by_topic.get(it["topic"], 0) + 1
        by_region[it["region"]] = by_region.get(it["region"], 0) + 1
        exp = st.parse_ts(it.get("expires_at"))
        if it["status"] == "APPROVED" and exp and exp <= limit:
            soon.append({"id": it["id"], "expires_at": it["expires_at"]})
    soon.sort(key=lambda x: x["expires_at"])
    return {
        "total": len(items),
        "by_status": by_status,
        "by_risk": by_risk,
        "by_topic": dict(sorted(by_topic.items())),
        "by_region": by_region,
        "high_risk_in_review": sum(1 for i in items if i["status"] == "IN_REVIEW" and i["risk_level"] == "HIGH"),
        "with_conflict": sum(1 for i in items if i.get("has_conflict")),
        "expiring_soon": soon[:20],
        "expired_just_now": swept,
    }


def list_items(repo: KnowledgeRepo, filters: dict, page: int, page_size: int,
               now: Optional[datetime] = None) -> dict:
    sweep_expired(repo, now or _now())
    page_size = max(1, min(int(page_size), cfg.MAX_PAGE_SIZE))
    page = max(1, int(page))
    rows, total = repo.list_items(filters, page_size, (page - 1) * page_size)
    return {"items": rows, "total": total, "page": page, "page_size": page_size}


def get_detail(repo: KnowledgeRepo, principal: Principal, item_id: str) -> dict:
    item = _load(repo, item_id)
    versions = repo.list_versions(item_id)
    approvals = repo.list_approvals(item_id)
    current = next((v for v in versions if v["version"] == item["current_version"] and not v.get("is_proposal")), None)
    actions = [a for a in st.allowed_actions(item["status"]) if a not in ("expire", "accept_proposal")]
    if principal.role != "admin":
        actions = [a for a in actions if a in REVIEWER_ACTIONS]
    approve_blocked = None
    if "approve" in actions:
        approve_blocked = st.approval_problem(item["risk_level"], principal.as_approver(),
                                              (current or {}).get("created_by"))
    audit, audit_total = repo.list_audit(item_id, 200, 0)
    return {
        "item": item,
        "current": current,
        "versions": [{k: v[k] for k in ("version", "is_proposal", "content_hash", "created_by", "created_at",
                                         "change_reason")} for v in versions],
        "pending_proposals": pending_proposals(versions, approvals),
        "approvals": approvals,
        "comments": repo.list_comments(item_id),
        "audit": audit,
        "audit_total": audit_total,
        "allowed_actions": actions,
        "approve_blocked_reason": approve_blocked,
    }


def get_version(repo: KnowledgeRepo, item_id: str, number: int) -> dict:
    ver = repo.get_version(item_id, number)
    if not ver:
        raise KnowledgeError(404, "Not found")
    return ver


def list_audit(repo: KnowledgeRepo, item_id: Optional[str], page: int, page_size: int) -> dict:
    page_size = max(1, min(int(page_size), cfg.MAX_PAGE_SIZE))
    page = max(1, int(page))
    rows, total = repo.list_audit(item_id, page_size, (page - 1) * page_size)
    return {"entries": rows, "total": total, "page": page, "page_size": page_size}


def items_with_payload(repo: KnowledgeRepo, items: list[dict]) -> list[dict]:
    current = repo.get_current_versions(items)
    return [{**it, "payload": (current.get(it["id"]) or {}).get("payload")} for it in items]


def get_published_items(repo: KnowledgeRepo, now: Optional[datetime] = None) -> list[dict]:
    """APPROVED, approval not lapsed, id not permanently blocked."""
    now = now or _now()
    keep = [
        i for i in repo.all_items()
        if i["status"] == "APPROVED"
        and not st.is_expired(i.get("expires_at"), now)
        and i["id"] not in cfg.PERMANENTLY_BLOCKED_CONTENT_IDENTIFIERS
    ]
    return items_with_payload(repo, keep)


def export_items(repo: KnowledgeRepo, now: Optional[datetime] = None) -> list[dict]:
    sweep_expired(repo, now or _now())
    return items_with_payload(repo, repo.all_items())


# -- reviewers --------------------------------------------------------------------------------

def list_reviewers(repo: KnowledgeRepo, now: Optional[datetime] = None) -> dict:
    now = now or _now()
    return {"members": repo.list_admins(), "invites": repo.list_pending_invites(_iso(now))}


def add_reviewer(repo: KnowledgeRepo, principal: Principal, data: ReviewerIn, now: Optional[datetime] = None) -> dict:
    now = now or _now()
    email = data.email.strip().lower()
    known = repo.find_auth_user_by_email(email)
    credential = (data.credential or "").strip() or None
    after = {"email": email, "role": "reviewer", "display_name": data.display_name, "credential": credential}
    if known:
        existing = repo.get_admin(known["id"])
        if existing and existing["role"] == "admin":
            raise KnowledgeError(409, "This person is already an admin")
        commit(
            repo,
            admin_user={"op": "upsert", "row": {
                "user_id": known["id"], "email": email, "role": "reviewer", "display_name": data.display_name,
                "credential": credential, "added_by": principal.user_id,
            }},
            audit=audit_row(principal, "reviewer_update" if existing else "reviewer_add", None, None, None,
                            (existing and {k: existing.get(k) for k in ("email", "role", "display_name", "credential")}) or None,
                            after, None, now),
        )
        return {"result": "updated" if existing else "added", "email": email}
    if any(i["email"].lower() == email for i in repo.list_pending_invites(_iso(now))):
        raise KnowledgeError(409, "This email already has a pending invite")
    commit(
        repo,
        invite={"op": "insert", "email": email, "role": "reviewer", "display_name": data.display_name,
                "credential": credential, "invited_by": principal.user_id,
                "expires_at": _iso(now + timedelta(days=cfg.INVITE_VALIDITY_DAYS))},
        audit=audit_row(principal, "reviewer_invite", None, None, None, None, after, None, now),
    )
    return {"result": "invited", "email": email}


def set_member_active(repo: KnowledgeRepo, principal: Principal, user_id: str, active: bool,
                      now: Optional[datetime] = None) -> dict:
    now = now or _now()
    target = repo.get_admin(user_id)
    if not target:
        raise KnowledgeError(404, "Not found")
    if not active:
        if str(user_id) == str(principal.user_id):
            raise KnowledgeError(409, "You cannot deactivate your own account")
        if target["role"] == "admin" and target.get("active") and repo.count_active_admins() <= 1:
            raise KnowledgeError(409, "The last active admin cannot be deactivated")
    commit(
        repo,
        admin_user={"op": "set_active", "row": {"user_id": user_id, "active": active}},
        audit=audit_row(principal, "member_reactivate" if active else "member_deactivate", None, None, None,
                        {"user_id": user_id, "active": bool(target.get("active"))},
                        {"user_id": user_id, "active": active}, None, now),
    )
    return {"user_id": user_id, "active": active}
