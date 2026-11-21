"""
access.py - who may use the knowledge admin routes.

Identity comes from the verified JWT (services.auth.get_user_id). Role comes from
a per-request lookup in admin_users through the service-role repo, with no
cache, so deactivation takes effect on the next request.

  anonymous / bad token      -> 401
  signed in, not a member    -> 403 {"detail": "Forbidden"} (same body for every
                                non-member and for deactivated members)
  reviewer on admin route    -> 403 {"detail": "Forbidden"}

Bootstrap: env ADMIN_BOOTSTRAP_EMAILS (comma list). Only while no active admin
exists, a signed-in user whose confirmed email is on the list becomes admin.
Invite: an unexpired admin_invites row for the caller's confirmed email is
consumed on first use.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from fastapi import Depends, Header, HTTPException

from services.auth import get_user_id
from services.knowledge import config as cfg
from services.knowledge.repo import ConflictError, KnowledgeRepo, RepoError, get_repo

logger = logging.getLogger(__name__)

FORBIDDEN = {"detail": "Forbidden"}


@dataclass(frozen=True)
class Principal:
    user_id: str
    role: str
    email: Optional[str] = None
    display_name: Optional[str] = None
    credential: Optional[str] = None

    @property
    def actor_name(self) -> str:
        return self.display_name or self.email or self.user_id

    def as_approver(self) -> dict:
        return {
            "user_id": self.user_id,
            "role": self.role,
            "display_name": self.display_name,
            "credential": self.credential,
        }


def _forbidden() -> HTTPException:
    return HTTPException(status_code=403, detail="Forbidden")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def bootstrap_emails() -> set[str]:
    raw = os.environ.get("ADMIN_BOOTSTRAP_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def _audit(user_id: str, role: str, name: str, action: str, after: dict, reason: str) -> dict:
    return {
        "actor_id": user_id, "actor_role": role, "actor_name": name, "action": action,
        "item_id": None, "from_status": None, "to_status": None,
        "before": None, "after": after, "diff": None, "reason": reason,
        "created_at": _now().isoformat(),
    }


def _join(repo: KnowledgeRepo, user_id: str) -> Optional[dict]:
    """First sign-in of a non-member: bootstrap or invite. Returns the new admin row."""
    emails = bootstrap_emails()
    auth_user = repo.get_auth_user(user_id)
    if not auth_user or not auth_user.get("email_confirmed") or not auth_user.get("email"):
        return None
    email = str(auth_user["email"]).strip().lower()

    if emails and email in emails and repo.count_active_admins() == 0:
        repo.commit_change({
            "admin_user": {"op": "insert", "row": {
                "user_id": user_id, "email": email, "role": "admin",
                "display_name": None, "credential": None, "added_by": user_id,
            }},
            "audit": _audit(user_id, "admin", email, "admin_bootstrap",
                            {"user_id": user_id, "role": "admin"}, "bootstrap by ADMIN_BOOTSTRAP_EMAILS"),
        })
        return repo.get_admin(user_id)

    invite = repo.get_invite_for_email(email, _now().isoformat())
    if invite:
        repo.commit_change({
            "admin_user": {"op": "insert", "row": {
                "user_id": user_id, "email": email, "role": invite["role"],
                "display_name": invite.get("display_name"), "credential": invite.get("credential"),
                "added_by": invite.get("invited_by"),
            }},
            "invite": {"op": "consume", "id": invite["id"], "user_id": user_id},
            "audit": _audit(user_id, invite["role"], invite.get("display_name") or email,
                            "invite_consumed", {"user_id": user_id, "role": invite["role"]}, "invite accepted"),
        })
        return repo.get_admin(user_id)
    return None


def resolve_principal(user_id: str, repo: KnowledgeRepo) -> Principal:
    """Look the caller up; 403 for anyone who is not an active member."""
    try:
        row = repo.get_admin(user_id)
        if row is None:
            try:
                row = _join(repo, user_id)
            except ConflictError:  # a parallel first request already created the row
                row = repo.get_admin(user_id)
    except RepoError:
        raise HTTPException(status_code=503, detail="Service unavailable")
    if not row or not row.get("active") or row.get("role") not in cfg.ROLES:
        raise _forbidden()
    return Principal(
        user_id=str(row["user_id"]),
        role=row["role"],
        email=row.get("email"),
        display_name=row.get("display_name"),
        credential=row.get("credential"),
    )


def bearer_required(authorization: Optional[str] = Header(default=None)) -> None:
    """Anonymous callers get 401 (not the 422 a missing required header would give)."""
    if not authorization or not authorization.strip():
        raise HTTPException(status_code=401, detail="Invalid token")


def require_reviewer_or_admin(
    _: None = Depends(bearer_required),
    user_id: str = Depends(get_user_id),
    repo: KnowledgeRepo = Depends(get_repo),
) -> Principal:
    return resolve_principal(user_id, repo)


def require_admin(
    _: None = Depends(bearer_required),
    user_id: str = Depends(get_user_id),
    repo: KnowledgeRepo = Depends(get_repo),
) -> Principal:
    principal = resolve_principal(user_id, repo)
    if principal.role != "admin":
        raise _forbidden()
    return principal
