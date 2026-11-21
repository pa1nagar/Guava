"""
status.py - pure status machine and approval rules. No I/O.

Transitions (D6):
  submit           DRAFT -> IN_REVIEW
  approve          IN_REVIEW -> APPROVED
  reject           IN_REVIEW -> REJECTED
  request_changes  IN_REVIEW -> CHANGES_REQUESTED
  retire           any status except RETIRED -> RETIRED
  restore          RETIRED -> DRAFT
  expire           APPROVED -> IN_REVIEW (system, approval lapsed)
  edit             DRAFT->DRAFT, IN_REVIEW->IN_REVIEW, CHANGES_REQUESTED->IN_REVIEW,
                   REJECTED->DRAFT, APPROVED->IN_REVIEW (new version voids approval)
  accept_proposal  any status except RETIRED -> IN_REVIEW
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from services.knowledge import config as cfg

_NON_RETIRED = tuple(s for s in cfg.STATUSES if s != "RETIRED")

TRANSITIONS: dict[str, dict[str, str]] = {
    "submit": {"DRAFT": "IN_REVIEW"},
    "approve": {"IN_REVIEW": "APPROVED"},
    "reject": {"IN_REVIEW": "REJECTED"},
    "request_changes": {"IN_REVIEW": "CHANGES_REQUESTED"},
    "retire": {s: "RETIRED" for s in _NON_RETIRED},
    "restore": {"RETIRED": "DRAFT"},
    "expire": {"APPROVED": "IN_REVIEW"},
    "edit": {
        "DRAFT": "DRAFT",
        "IN_REVIEW": "IN_REVIEW",
        "CHANGES_REQUESTED": "IN_REVIEW",
        "REJECTED": "DRAFT",
        "APPROVED": "IN_REVIEW",
    },
    "accept_proposal": {s: "IN_REVIEW" for s in _NON_RETIRED},
}

# Actions that must carry a written reason.
REASON_REQUIRED = frozenset({"reject", "request_changes", "retire", "restore", "decline_proposal"})


def next_status(action: str, current: str) -> Optional[str]:
    """Return the status after ``action`` from ``current``, or None when not allowed."""
    return TRANSITIONS.get(action, {}).get(current)


def can_transition(action: str, current: str) -> bool:
    return next_status(action, current) is not None


def require_transition(action: str, current: str) -> str:
    target = next_status(action, current)
    if target is None:
        raise cfg.KnowledgeError(409, "This action is not allowed in the item's current status")
    return target


def allowed_actions(current: str) -> list[str]:
    return sorted(a for a in TRANSITIONS if can_transition(a, current))


def clean_reason(action: str, reason: Optional[str]) -> Optional[str]:
    """Strip the reason; raise 422 when the action requires one and it is too short."""
    text = (reason or "").strip() or None
    if action in REASON_REQUIRED and (text is None or len(text) < cfg.MIN_REASON_CHARS):
        raise cfg.KnowledgeError(422, "A reason is required")
    return text


def approval_problem(risk_level: str, approver: dict, author_id: Optional[str]) -> Optional[str]:
    """Return why ``approver`` may not approve an item, or None when allowed.

    approver: {"user_id", "role", "display_name", "credential"}.
    LOW/MEDIUM: admin or reviewer. HIGH: a reviewer with a name and a credential
    on file who did not author the version being approved.
    """
    role = approver.get("role")
    if role not in cfg.ROLES:
        return "Only an admin or reviewer can approve"
    if risk_level != "HIGH":
        return None
    if role != "reviewer":
        return "A HIGH risk item must be approved by a reviewer, not an admin"
    if not (approver.get("display_name") or "").strip():
        return "The reviewer's name must be on file to approve a HIGH risk item"
    if not (approver.get("credential") or "").strip():
        return "The reviewer's credential must be on file to approve a HIGH risk item"
    if author_id is not None and str(approver.get("user_id")) == str(author_id):
        return "The author cannot approve their own HIGH risk item"
    return None


def expiry_for(approved_at: datetime) -> datetime:
    return approved_at + timedelta(days=cfg.APPROVAL_VALIDITY_DAYS)


def parse_ts(value) -> Optional[datetime]:
    """Parse an ISO timestamp (str or datetime) into an aware UTC datetime."""
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        dt = value
    else:
        text = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(text)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def is_expired(expires_at, now: datetime) -> bool:
    exp = parse_ts(expires_at)
    return exp is None or exp <= now
