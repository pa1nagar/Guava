"""
knowledge_admin.py - /api/admin/knowledge: curate, review and audit the guava knowledge base.

Every route needs a signed-in admin or reviewer (401 anonymous, 403 anyone else).
Admin-only routes: create, edit, accept/decline proposals, retire, restore,
import-seed, sweep-expired, exports, reviewer management.
Only GET, POST and PUT are used (CORS allows nothing else). Nothing here deletes
data: items are retired, history is append-only (see the migration).

Responses are never cached and carry generic error bodies (no stack traces, no
echo of what the caller sent).
"""
import logging
from datetime import datetime, timezone
from typing import Literal, Optional

from fastapi import APIRouter, Depends, Path, Query, Request, Response
from fastapi.exceptions import HTTPException, RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from services.knowledge import config as cfg
from services.knowledge import export as export_mod
from services.knowledge import seed_import
from services.knowledge import service as svc
from services.knowledge.access import Principal, require_admin, require_reviewer_or_admin
from services.knowledge.models import (
    ActionIn, CommentIn, ImportIn, ItemCreateIn, ItemEditIn, ProposalIn, ReviewerIn,
)
from services.knowledge.repo import ConflictError, KnowledgeRepo, RepoError, get_repo
from services.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)

NO_STORE = "no-store"


class _KnowledgeRoute(APIRoute):
    """Adds Cache-Control: no-store and turns expected errors into generic JSON bodies."""

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request) -> Response:
            try:
                response = await original(request)
            except cfg.KnowledgeError as exc:
                response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code)
            except ConflictError:
                response = JSONResponse(
                    {"detail": "The record was changed by someone else. Reload and try again"}, status_code=409)
            except RepoError:
                response = JSONResponse({"detail": "Service unavailable"}, status_code=503)
            except RequestValidationError as exc:
                errors = [{"loc": list(e.get("loc", ())), "msg": str(e.get("msg", "Invalid"))[:200]}
                          for e in exc.errors()[:20]]
                response = JSONResponse({"detail": errors}, status_code=422)
            except HTTPException as exc:
                response = JSONResponse({"detail": exc.detail}, status_code=exc.status_code,
                                        headers=dict(exc.headers or {}))
            response.headers["Cache-Control"] = NO_STORE
            return response

        return handler


router = APIRouter(prefix="/admin/knowledge", route_class=_KnowledgeRoute)

_read = Depends(RateLimiter("knowledge_read"))
_write = Depends(RateLimiter("knowledge_write"))
_export = Depends(RateLimiter("knowledge_export"))
_import = Depends(RateLimiter("knowledge_import"))

ItemId = Path(..., pattern=cfg.ID_PATTERN, max_length=20)
UserIdPath = Path(..., pattern=cfg.UUID_PATTERN, max_length=36)
VersionNo = Path(..., ge=1, le=100000)

Status = Literal[*cfg.STATUSES]  # type: ignore[valid-type]
Topic = Literal[*cfg.TOPICS]  # type: ignore[valid-type]
Region = Literal[*cfg.REGIONS]  # type: ignore[valid-type]
Risk = Literal[*cfg.RISK_LEVELS]  # type: ignore[valid-type]


def _now() -> datetime:
    return datetime.now(timezone.utc)


# -- who am I / overview ---------------------------------------------------------------

@router.get("/me", dependencies=[_read])
def me(principal: Principal = Depends(require_reviewer_or_admin)):
    return {
        "user_id": principal.user_id, "role": principal.role, "email": principal.email,
        "display_name": principal.display_name, "credential": principal.credential,
    }


@router.get("/dashboard", dependencies=[_read])
def dashboard(_: Principal = Depends(require_reviewer_or_admin), repo: KnowledgeRepo = Depends(get_repo)):
    return svc.dashboard(repo)


# -- items -----------------------------------------------------------------------------------

@router.get("/items", dependencies=[_read])
def items_list(
    q: Optional[str] = Query(default=None, max_length=cfg.MAX_QUERY_LEN),
    status: Optional[Status] = Query(default=None),
    topic: Optional[Topic] = Query(default=None),
    region: Optional[Region] = Query(default=None),
    risk_level: Optional[Risk] = Query(default=None),
    has_conflict: Optional[bool] = Query(default=None),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=cfg.DEFAULT_PAGE_SIZE, ge=1, le=cfg.MAX_PAGE_SIZE),
    _: Principal = Depends(require_reviewer_or_admin),
    repo: KnowledgeRepo = Depends(get_repo),
):
    filters = {"q": q, "status": status, "topic": topic, "region": region,
               "risk_level": risk_level, "has_conflict": has_conflict}
    return svc.list_items(repo, filters, page, page_size)


@router.post("/items", status_code=201, dependencies=[_write])
def item_create(body: ItemCreateIn, principal: Principal = Depends(require_admin),
                repo: KnowledgeRepo = Depends(get_repo)):
    return {"item": svc.create_item(repo, principal, body.item)}


@router.get("/items/{item_id}", dependencies=[_read])
def item_detail(item_id: str = ItemId, principal: Principal = Depends(require_reviewer_or_admin),
                repo: KnowledgeRepo = Depends(get_repo)):
    return svc.get_detail(repo, principal, item_id)


@router.put("/items/{item_id}", dependencies=[_write])
def item_edit(body: ItemEditIn, item_id: str = ItemId, principal: Principal = Depends(require_admin),
              repo: KnowledgeRepo = Depends(get_repo)):
    return {"item": svc.edit_item(repo, principal, item_id, body.item, body.expected_row_version, body.reason)}


@router.get("/items/{item_id}/versions/{number}", dependencies=[_read])
def item_version(item_id: str = ItemId, number: int = VersionNo,
                 _: Principal = Depends(require_reviewer_or_admin), repo: KnowledgeRepo = Depends(get_repo)):
    return svc.get_version(repo, item_id, number)


@router.post("/items/{item_id}/proposals", status_code=201, dependencies=[_write])
def proposal_create(body: ProposalIn, item_id: str = ItemId,
                    principal: Principal = Depends(require_reviewer_or_admin),
                    repo: KnowledgeRepo = Depends(get_repo)):
    return svc.propose_edit(repo, principal, item_id, body.item, body.reason)


@router.post("/items/{item_id}/proposals/{number}/accept", dependencies=[_write])
def proposal_accept(body: ActionIn, item_id: str = ItemId, number: int = VersionNo,
                    principal: Principal = Depends(require_admin), repo: KnowledgeRepo = Depends(get_repo)):
    return {"item": svc.accept_proposal(repo, principal, item_id, number, body.expected_row_version, body.reason)}


@router.post("/items/{item_id}/proposals/{number}/decline", dependencies=[_write])
def proposal_decline(body: ActionIn, item_id: str = ItemId, number: int = VersionNo,
                     principal: Principal = Depends(require_admin), repo: KnowledgeRepo = Depends(get_repo)):
    return svc.decline_proposal(repo, principal, item_id, number, body.expected_row_version, body.reason)


def _add_action(path: str, action: str, guard) -> None:
    def endpoint(body: ActionIn, item_id: str = ItemId, principal: Principal = Depends(guard),
                 repo: KnowledgeRepo = Depends(get_repo)):
        return {"item": svc.transition(repo, principal, item_id, action, body.expected_row_version, body.reason)}

    endpoint.__name__ = f"item_{action}"
    router.add_api_route(f"/items/{{item_id}}/{path}", endpoint, methods=["POST"], dependencies=[_write])


_add_action("submit", "submit", require_reviewer_or_admin)
_add_action("approve", "approve", require_reviewer_or_admin)
_add_action("reject", "reject", require_reviewer_or_admin)
_add_action("request-changes", "request_changes", require_reviewer_or_admin)
_add_action("retire", "retire", require_admin)
_add_action("restore", "restore", require_admin)


@router.post("/items/{item_id}/comments", status_code=201, dependencies=[_write])
def comment_create(body: CommentIn, item_id: str = ItemId,
                   principal: Principal = Depends(require_reviewer_or_admin),
                   repo: KnowledgeRepo = Depends(get_repo)):
    return svc.add_comment(repo, principal, item_id, body.body, body.version)


# -- audit, import, sweep, export, published -------------------------------------------

@router.get("/audit", dependencies=[_read])
def audit_list(
    item_id: Optional[str] = Query(default=None, pattern=cfg.ID_PATTERN, max_length=20),
    page: int = Query(default=1, ge=1, le=10000),
    page_size: int = Query(default=cfg.DEFAULT_PAGE_SIZE, ge=1, le=cfg.MAX_PAGE_SIZE),
    _: Principal = Depends(require_reviewer_or_admin),
    repo: KnowledgeRepo = Depends(get_repo),
):
    return svc.list_audit(repo, item_id, page, page_size)


@router.post("/import-seed", dependencies=[_import])
def import_seed(body: ImportIn, principal: Principal = Depends(require_admin),
                repo: KnowledgeRepo = Depends(get_repo)):
    return seed_import.run(repo, principal, dry_run=body.dry_run)


@router.post("/sweep-expired", dependencies=[_write])
def sweep_expired(_: Principal = Depends(require_admin), repo: KnowledgeRepo = Depends(get_repo)):
    return {"expired": svc.sweep_expired(repo)}


def _export_audit(repo: KnowledgeRepo, principal: Principal, kind: str, count: int) -> None:
    svc.commit(repo, expected_row_version=None, audit=svc.audit_row(
        principal, "export", None, None, None, None, {"format": kind, "items": count}, None, _now()))


@router.get("/export.csv", dependencies=[_export])
def export_csv(principal: Principal = Depends(require_admin), repo: KnowledgeRepo = Depends(get_repo)):
    items = svc.export_items(repo)
    _export_audit(repo, principal, "csv", len(items))
    return Response(
        content=export_mod.items_to_csv(items),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="guava-knowledge.csv"'},
    )


@router.get("/export.json", dependencies=[_export])
def export_json(principal: Principal = Depends(require_admin), repo: KnowledgeRepo = Depends(get_repo)):
    items = svc.export_items(repo)
    _export_audit(repo, principal, "json", len(items))
    return {"items": items}


@router.get("/published", dependencies=[_read])
def published(_: Principal = Depends(require_reviewer_or_admin), repo: KnowledgeRepo = Depends(get_repo)):
    return {"items": svc.get_published_items(repo)}


# -- reviewers -----------------------------------------------------------------------------------

@router.get("/reviewers", dependencies=[_read])
def reviewers_list(_: Principal = Depends(require_admin), repo: KnowledgeRepo = Depends(get_repo)):
    return svc.list_reviewers(repo)


@router.post("/reviewers", status_code=201, dependencies=[_write])
def reviewer_add(body: ReviewerIn, principal: Principal = Depends(require_admin),
                 repo: KnowledgeRepo = Depends(get_repo)):
    return svc.add_reviewer(repo, principal, body)


@router.post("/reviewers/{user_id}/deactivate", dependencies=[_write])
def reviewer_deactivate(user_id: str = UserIdPath, principal: Principal = Depends(require_admin),
                        repo: KnowledgeRepo = Depends(get_repo)):
    return svc.set_member_active(repo, principal, user_id, False)


@router.post("/reviewers/{user_id}/reactivate", dependencies=[_write])
def reviewer_reactivate(user_id: str = UserIdPath, principal: Principal = Depends(require_admin),
                        repo: KnowledgeRepo = Depends(get_repo)):
    return svc.set_member_active(repo, principal, user_id, True)
