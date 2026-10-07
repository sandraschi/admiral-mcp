"""admiral-mcp: Agent-harness-to-iPhone pager bridge.

FastMCP 3.2+ server with 5 tools, SQLite persistence, Starlette relay
for iOS callback, APNs push relay, and health/diagnostics REST API.
"""

import logging

from fastmcp import FastMCP
from starlette.routing import Route

from admiral_mcp.apns import APNsRelay
from admiral_mcp.config import get_config
from admiral_mcp.db import get_db
from admiral_mcp.events import get_approval_events
from admiral_mcp.health import api_diagnostics, api_health
from admiral_mcp.models import (
    ApprovalDecision,
    GetDiffResult,
    RegisterRunResult,
    RequestApprovalResult,
    ResolveApprovalResult,
    RunPhase,
    UpdateProgressResult,
)
from admiral_mcp.relay import relay_approve, relay_deny, relay_get_diff

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger("admiral_mcp")

mcp = FastMCP("admiral-mcp")

_apns_relay = APNsRelay()

_MUTATING: dict = {}
_READ_ONLY = {"readonly": True}

# ---------------------------------------------------------------------------
# Tool 1: register_run
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_MUTATING)
async def register_run(
    run_id: str,
    repo: str,
    phases: list[str],
    harness: str,
) -> RegisterRunResult:
    """Announce a new agent job to the pager.

    The harness (Claude Code, OpenCode, etc.) calls this before starting
    a multi-phase run. The backend creates a run record and is ready to
    accept progress updates.

    Args:
        run_id: Unique identifier for this run.
        repo: Repository name the job operates on.
        phases: Ordered list of phase names (e.g. ["lint", "test", "deploy"]).
        harness: Name of the agent harness (e.g. "claude-code", "opencode").

    ## Return Format
    {"success": true, "message": "Run registered", "run_id": "backup-db-001"}

    ## Examples
    register_run(
        run_id="deploy-v2",
        repo="plex-mcp",
        phases=["lint","test","build","deploy"],
        harness="opencode",
    )
    """
    db = get_db()
    record = await db.register_run(run_id, repo, phases, harness)
    logger.info("Run registered: %s (repo=%s, harness=%s)", run_id, repo, harness)
    return RegisterRunResult(
        success=True,
        message=f"Run '{run_id}' registered with {len(phases)} phases",
        run_id=record.run_id,
    )


# ---------------------------------------------------------------------------
# Tool 2: update_progress
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_MUTATING)
async def update_progress(
    run_id: str,
    phase: int,
    cost: float,
    status: str,
) -> UpdateProgressResult:
    """Advance a run to the next phase and push a Live Activity update.

    The harness calls this after each phase completes. If APNs is
    configured, a Live Activity push is sent to the iOS device.

    Args:
        run_id: Run identifier from register_run.
        phase: 0-based phase index.
        cost: Cumulative cost in USD so far.
        status: One of queued, running, awaiting_approval, complete,
            failed, cancelled.

    ## Return Format
    {"success": true, "message": "Phase 1/4: lint (running)",
     "run_id": "deploy-v2", "phase": 1}

    ## Examples
    update_progress(run_id="deploy-v2", phase=1, cost=0.14, status="running")
    """
    try:
        run_status = RunPhase(status)
    except ValueError:
        valid = [s.value for s in RunPhase]
        return UpdateProgressResult(
            success=False,
            message=f"Invalid status '{status}'. Must be one of: {valid}",
            run_id=run_id,
            phase=phase,
        )

    db = get_db()
    record = await db.update_run_phase(run_id, phase, cost, run_status)
    if record is None:
        return UpdateProgressResult(
            success=False,
            message=f"Run '{run_id}' not found. Call register_run first.",
            run_id=run_id,
            phase=phase,
        )

    phase_names = record.phases
    phase_name = phase_names[phase] if phase < len(phase_names) else f"phase_{phase}"

    await _apns_relay.send_live_activity_update(
        run_id=run_id,
        phase=phase,
        phase_name=phase_name,
        status=status,
        cost=cost,
        total_phases=len(phase_names),
    )

    logger.info(
        "Progress updated: %s phase %d/%d (%s)",
        run_id,
        phase,
        len(phase_names),
        status,
    )
    return UpdateProgressResult(
        success=True,
        message=f"Phase {phase}/{len(phase_names)}: {phase_name} ({status})",
        run_id=run_id,
        phase=phase,
    )


# ---------------------------------------------------------------------------
# Tool 3: request_approval
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_MUTATING)
async def request_approval(
    run_id: str,
    summary: str,
    diff_ref: str | None = None,
    diff_content: str | None = None,
) -> RequestApprovalResult:
    """Request human approval and block until a decision arrives or timeout.

    Sends an actionable APNs push to the iOS device with Approve/Deny
    buttons. Blocks for up to ADMIRAL_APPROVAL_TIMEOUT seconds (default
    300). If no decision arrives before timeout, returns "timeout".

    The iOS app calls back via POST /relay/approve or POST /relay/deny,
    which calls resolve_approval internally to unblock this tool.

    Args:
        run_id: Run identifier from register_run.
        summary: One-line description of what needs approval.
        diff_ref: Opaque reference the iOS app uses to fetch diff content.
        diff_content: Optional diff content stored for get_diff retrieval.

    ## Return Format
    {"success": true, "message": "Approved: deploy to production",
     "approval_id": "a1b2c3d4", "decision": "approve"}

    ## Examples
    request_approval(
        run_id="deploy-v2",
        summary="Deploy to production?",
        diff_ref="deploy-v2",
        diff_content="+ 5 files changed...",
    )
    """
    config = get_config()
    db = get_db()
    events = get_approval_events()

    record = await db.get_run(run_id)
    if record is None:
        return RequestApprovalResult(
            success=False,
            message=f"Run '{run_id}' not found",
            approval_id="",
            decision=ApprovalDecision.TIMEOUT,
        )

    if diff_content:
        await db.store_diff(run_id, diff_content)
        actual_diff_ref = run_id
    else:
        actual_diff_ref = diff_ref

    approval = await db.create_approval(run_id, summary, actual_diff_ref)
    await events.create(approval.approval_id)

    logger.info(
        "Approval requested: approval_id=%s run_id=%s summary=%s",
        approval.approval_id,
        run_id,
        summary[:80],
    )

    await _apns_relay.send_approval_alert(
        approval_id=approval.approval_id,
        run_id=run_id,
        summary=summary,
        diff_ref=actual_diff_ref,
    )

    await db.update_run_phase(run_id, record.current_phase, record.cost, RunPhase.AWAITING_APPROVAL)

    await events.wait(approval.approval_id, config.approval_timeout)
    resolved = await db.get_approval(approval.approval_id)
    decision = resolved.decision if resolved else ApprovalDecision.TIMEOUT

    return RequestApprovalResult(
        success=True,
        message=f"Approval result: {decision.value}",
        approval_id=approval.approval_id,
        decision=decision,
    )


# ---------------------------------------------------------------------------
# Tool 4: resolve_approval
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_MUTATING)
async def resolve_approval(
    approval_id: str,
    decision: str,
) -> ResolveApprovalResult:
    """Resolve a pending approval (called by the relay when the phone answers).

    One-shot: the approval_id is consumed and cannot be replayed.
    This unblocks the waiting request_approval call.

    Args:
        approval_id: The approval ID from request_approval.
        decision: "approve" or "deny".

    ## Return Format
    {"success": true, "message": "Approval resolved: approve",
     "approval_id": "a1b2c3d4", "decision": "approve"}

    ## Examples
    resolve_approval(approval_id="a1b2c3d4", decision="approve")
    """
    try:
        dec = ApprovalDecision(decision)
    except ValueError:
        return ResolveApprovalResult(
            success=False,
            message=f"Invalid decision '{decision}'. Must be 'approve' or 'deny'.",
            approval_id=approval_id,
            decision=ApprovalDecision.TIMEOUT,
        )

    db = get_db()
    events = get_approval_events()

    resolved = await db.resolve_approval(approval_id, dec)
    if not resolved:
        return ResolveApprovalResult(
            success=False,
            message=f"No pending approval found for: {approval_id}",
            approval_id=approval_id,
            decision=ApprovalDecision.TIMEOUT,
        )

    await events.signal(approval_id, dec)

    logger.info("Approval resolved: approval_id=%s decision=%s", approval_id, decision)
    return ResolveApprovalResult(
        success=True,
        message=f"Approval resolved: {decision}",
        approval_id=approval_id,
        decision=dec,
    )


# ---------------------------------------------------------------------------
# Tool 5: get_diff
# ---------------------------------------------------------------------------


@mcp.tool(annotations=_READ_ONLY)
async def get_diff(
    diff_ref: str,
) -> GetDiffResult:
    """Serve diff content to the iOS app by reference.

    The diff content is stored by request_approval when diff_content is
    provided. The iOS app fetches it via GET /relay/diff/{diff_ref}.

    Args:
        diff_ref: Opaque reference for diff retrieval (typically the run_id).

    ## Return Format
    {"success": true, "message": "Diff retrieved (1234 bytes)",
     "diff_ref": "deploy-v2", "content": "+ 5 files changed..."}

    ## Examples
    get_diff(diff_ref="deploy-v2")
    """
    db = get_db()
    content = await db.get_diff(diff_ref)
    if content is None:
        return GetDiffResult(
            success=False,
            message=f"No diff content for: {diff_ref}",
            diff_ref=diff_ref,
            content=None,
        )

    return GetDiffResult(
        success=True,
        message=f"Diff retrieved ({len(content)} bytes)",
        diff_ref=diff_ref,
        content=content,
    )


# ---------------------------------------------------------------------------
# App assembly: FastMCP + health/diagnostics API + relay routes
# ---------------------------------------------------------------------------

mcp_app = mcp.http_app()

mcp_app.routes.append(Route("/relay/approve", relay_approve, methods=["POST"]))
mcp_app.routes.append(Route("/relay/deny", relay_deny, methods=["POST"]))
mcp_app.routes.append(Route("/relay/diff/{diff_ref:path}", relay_get_diff, methods=["GET"]))
mcp_app.routes.append(Route("/api/v1/health", api_health, methods=["GET"]))
mcp_app.routes.append(Route("/api/v1/diagnostics", api_diagnostics, methods=["GET"]))

starlette_app = mcp_app


def main() -> None:
    import uvicorn

    config = get_config()
    logger.info("admiral-mcp v%s starting on %s:%d", config.version, config.host, config.port)
    uvicorn.run(
        starlette_app,
        host=config.host,
        port=config.port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
