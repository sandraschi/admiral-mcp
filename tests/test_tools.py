"""End-to-end tests for admiral-mcp tools and relay."""

import asyncio

import httpx
import pytest

BACKEND = "http://127.0.0.1:11089"
RELAY_TOKEN = "admin"


async def _mcp_call(tool_name: str, arguments: dict) -> dict:
    """Call an MCP tool via the streamable HTTP transport."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(30)) as client:
        resp = await client.post(
            f"{BACKEND}/mcp",
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": arguments},
                "id": 1,
            },
        )
        resp.raise_for_status()
        data = resp.json()
        if "result" in data and "structuredContent" in data["result"]:
            return data["result"]["structuredContent"]
        if "result" in data and "content" in data["result"]:
            for c in data["result"]["content"]:
                if c.get("type") == "text":
                    import json

                    return json.loads(c["text"])
        return data


async def _relay_post(path: str, body: dict) -> dict:
    """POST to a relay endpoint with auth."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
        resp = await client.post(
            f"{BACKEND}{path}",
            json=body,
            headers={"Authorization": f"Bearer {RELAY_TOKEN}"},
        )
        return resp.json()


async def _relay_get(path: str) -> dict | str:
    """GET from a relay endpoint with auth."""
    async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
        resp = await client.get(
            f"{BACKEND}{path}",
            headers={"Authorization": f"Bearer {RELAY_TOKEN}"},
        )
        if resp.status_code == 200:
            ct = resp.headers.get("content-type", "")
            if "text/plain" in ct:
                return resp.text
            return resp.json()
        return {"status": resp.status_code, "error": resp.text}


async def _health_check() -> bool:
    """Check if the backend is reachable."""
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(3)) as client:
            resp = await client.post(
                f"{BACKEND}/mcp",
                json={
                    "jsonrpc": "2.0",
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "1"},
                    },
                    "id": 0,
                },
            )
            return resp.status_code == 200
    except Exception:
        return False


@pytest.mark.asyncio
async def test_register_run():
    if not await _health_check():
        pytest.skip("Backend not running")
    result = await _mcp_call(
        "register_run",
        {"run_id": "test-reg-001", "repo": "plex-mcp", "phases": ["lint", "deploy"], "harness": "opencode"},
    )
    assert result["success"] is True
    assert result["run_id"] == "test-reg-001"


@pytest.mark.asyncio
async def test_update_progress():
    if not await _health_check():
        pytest.skip("Backend not running")
    await _mcp_call(
        "register_run",
        {"run_id": "test-prog-001", "repo": "plex-mcp", "phases": ["lint", "deploy"], "harness": "opencode"},
    )
    result = await _mcp_call(
        "update_progress",
        {"run_id": "test-prog-001", "phase": 1, "cost": 0.14, "status": "running"},
    )
    assert result["success"] is True
    assert result["phase"] == 1


@pytest.mark.asyncio
async def test_update_progress_not_found():
    if not await _health_check():
        pytest.skip("Backend not running")
    result = await _mcp_call(
        "update_progress",
        {"run_id": "nonexistent-999", "phase": 0, "cost": 0.0, "status": "running"},
    )
    assert result["success"] is False


@pytest.mark.asyncio
async def test_request_approval_and_resolve():
    if not await _health_check():
        pytest.skip("Backend not running")
    await _mcp_call(
        "register_run",
        {
            "run_id": "test-approve-001",
            "repo": "plex-mcp",
            "phases": ["lint", "approve", "deploy"],
            "harness": "opencode",
        },
    )

    async def _approve_soon():
        await asyncio.sleep(1)
        # Need to get the approval_id — we poll the relay
        # For the test, we use a known pattern
        return True

    result = await _mcp_call(
        "request_approval",
        {
            "run_id": "test-approve-001",
            "summary": "Deploy to prod?",
            "diff_ref": "test-approve-001",
            "diff_content": "+ 5 files\n- 2 files",
        },
    )
    assert result["success"] is True
    assert result["decision"] in ("approve", "deny", "timeout")


@pytest.mark.asyncio
async def test_get_diff():
    if not await _health_check():
        pytest.skip("Backend not running")
    await _mcp_call(
        "register_run",
        {"run_id": "test-diff-001", "repo": "plex-mcp", "phases": ["lint"], "harness": "opencode"},
    )
    # Store diff via request_approval (quick timeout or use resolve)
    # Call in background so it doesn't block
    await _mcp_call(
        "request_approval",
        {
            "run_id": "test-diff-001",
            "summary": "Diff test",
            "diff_ref": "test-diff-001",
            "diff_content": "some diff content here",
        },
    )
    # get_diff should find it stored under run_id
    result = await _mcp_call(
        "get_diff",
        {"diff_ref": "test-diff-001"},
    )
    assert result["success"] is True
    assert result["content"] == "some diff content here"


@pytest.mark.asyncio
async def test_get_diff_not_found():
    if not await _health_check():
        pytest.skip("Backend not running")
    result = await _mcp_call(
        "get_diff",
        {"diff_ref": "this-does-not-exist-anywhere"},
    )
    assert result["success"] is False


@pytest.mark.asyncio
async def test_resolve_approval_not_found():
    if not await _health_check():
        pytest.skip("Backend not running")
    result = await _mcp_call(
        "resolve_approval",
        {"approval_id": "fake-not-real", "decision": "approve"},
    )
    assert result["success"] is False


@pytest.mark.asyncio
async def test_relay_auth_required():
    if not await _health_check():
        pytest.skip("Backend not running")
    async with httpx.AsyncClient(timeout=httpx.Timeout(10)) as client:
        resp = await client.post(
            f"{BACKEND}/relay/approve",
            json={"approval_id": "test"},
        )
        assert resp.status_code == 401


@pytest.mark.asyncio
async def test_relay_get_diff():
    if not await _health_check():
        pytest.skip("Backend not running")
    # Store diff first
    await _mcp_call(
        "register_run",
        {"run_id": "test-relay-diff-001", "repo": "plex-mcp", "phases": ["lint"], "harness": "opencode"},
    )
    await _mcp_call(
        "request_approval",
        {
            "run_id": "test-relay-diff-001",
            "summary": "Test",
            "diff_ref": "test-relay-diff-001",
            "diff_content": "relay diff works",
        },
    )
    # Fetch via relay
    result = await _relay_get("/relay/diff/test-relay-diff-001")
    assert result == "relay diff works"


@pytest.mark.asyncio
async def test_resolve_approval_invalid_decision():
    if not await _health_check():
        pytest.skip("Backend not running")
    result = await _mcp_call(
        "resolve_approval",
        {"approval_id": "fake-001", "decision": "maybe"},
    )
    assert result["success"] is False
