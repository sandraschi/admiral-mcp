"""Starlette relay REST endpoints for the iOS Admiral Pager app."""

import json
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse

from admiral_mcp.auth import require_auth
from admiral_mcp.db import get_db
from admiral_mcp.events import get_approval_events
from admiral_mcp.models import ApprovalDecision

logger = logging.getLogger(__name__)


def _unauthorized() -> JSONResponse:
    return JSONResponse({"error": "unauthorized"}, status_code=401)


def _not_found(msg: str = "not found") -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=404)


def _bad_request(msg: str) -> JSONResponse:
    return JSONResponse({"error": msg}, status_code=400)


async def relay_approve(request: Request) -> JSONResponse:
    if not require_auth(request):
        return _unauthorized()

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return _bad_request("invalid JSON body")

    approval_id = body.get("approval_id", "").strip()
    if not approval_id:
        return _bad_request("missing approval_id")

    db = get_db()
    events = get_approval_events()

    resolved = await db.resolve_approval(approval_id, ApprovalDecision.APPROVE)
    if not resolved:
        return _not_found(f"no pending approval: {approval_id}")

    await events.signal(approval_id, ApprovalDecision.APPROVE)

    return JSONResponse(
        {
            "status": "ok",
            "approval_id": approval_id,
            "decision": "approve",
        }
    )


async def relay_deny(request: Request) -> JSONResponse:
    if not require_auth(request):
        return _unauthorized()

    try:
        body = await request.json()
    except (json.JSONDecodeError, ValueError):
        return _bad_request("invalid JSON body")

    approval_id = body.get("approval_id", "").strip()
    if not approval_id:
        return _bad_request("missing approval_id")

    db = get_db()
    events = get_approval_events()

    resolved = await db.resolve_approval(approval_id, ApprovalDecision.DENY)
    if not resolved:
        return _not_found(f"no pending approval: {approval_id}")

    await events.signal(approval_id, ApprovalDecision.DENY)

    return JSONResponse(
        {
            "status": "ok",
            "approval_id": approval_id,
            "decision": "deny",
        }
    )


async def relay_get_diff(request: Request) -> JSONResponse:
    if not require_auth(request):
        return _unauthorized()

    diff_ref = request.path_params.get("diff_ref", "")
    if not diff_ref:
        return _bad_request("missing diff_ref")

    db = get_db()
    content = await db.get_diff(diff_ref)

    if content is None:
        return _not_found(f"no diff content for: {diff_ref}")

    return PlainTextResponse(content, media_type="text/plain")
