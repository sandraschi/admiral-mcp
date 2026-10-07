"""Health check and diagnostics REST endpoints for the dashboard.

Provides GET /api/v1/health (KPIs) and GET /api/v1/diagnostics
(comprehensive system info) consumed by the React dashboard.
"""

import time

from starlette.requests import Request
from starlette.responses import JSONResponse

from admiral_mcp.db import get_db

_start_time = time.time()


async def api_health(request: Request) -> JSONResponse:
    db = get_db()
    runs_count = await db.count_runs()
    pending = await db.count_pending_approvals()
    uptime = int(time.time() - _start_time)

    return JSONResponse(
        {
            "status": "ok",
            "server": "admiral-mcp",
            "version": "0.1.0",
            "uptime_seconds": uptime,
            "tool_count": 5,
            "runs_count": runs_count,
            "pending_approvals": pending,
            "providers": {},
        }
    )


async def api_diagnostics(request: Request) -> JSONResponse:
    db = get_db()
    runs_count = await db.count_runs()
    pending = await db.count_pending_approvals()
    uptime = int(time.time() - _start_time)
    runs = await db.list_runs(limit=10)
    pending_approvals = await db.list_pending_approvals()

    return JSONResponse(
        {
            "status": "ok",
            "server": "admiral-mcp",
            "version": "0.1.0",
            "uptime_seconds": uptime,
            "tool_count": 5,
            "runs_count": runs_count,
            "pending_approvals": pending,
            "tools": [
                {"name": "register_run"},
                {"name": "update_progress"},
                {"name": "request_approval"},
                {"name": "resolve_approval"},
                {"name": "get_diff"},
            ],
            "system": {
                "windows": True,
                "python": True,
            },
            "recent_runs": [
                {
                    "run_id": r.run_id,
                    "repo": r.repo,
                    "status": r.status.value,
                    "phase": r.current_phase,
                    "phases": r.phases,
                }
                for r in runs
            ],
            "pending_approval_items": [
                {
                    "approval_id": a.approval_id,
                    "run_id": a.run_id,
                    "summary": a.summary,
                }
                for a in pending_approvals
            ],
            "errors": [],
        }
    )
