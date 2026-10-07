# Admiral MCP — User Tutorial

## Quick Start

Admiral MCP lets your AI agent harness page your iPhone for approvals and
stream job progress to a Live Activity. Here's how to set it up and use it.

## 1. Installation

```powershell
git clone https://github.com/sandraschi/admiral-mcp.git
cd admiral-mcp
uv sync
```

## 2. Configuration

Copy the example env file and edit it:

```powershell
Copy-Item .env.example .env
```

Minimum required settings:
```
ADMIRAL_HOST=127.0.0.1
ADMIRAL_PORT=11089
ADMIRAL_RELAY_TOKEN=your-secret-token
```

For iPhone notifications, also set the APNs variables (see below).

## 3. Starting the Server

```powershell
# Backend only:
just serve

# Full stack (backend + dashboard):
.\start.ps1
```

The dashboard opens at http://127.0.0.1:11090. The MCP transport is at
http://127.0.0.1:11089/mcp.

## 4. Registering with Your Agent Harness

Add to your MCP client config:

**OpenCode** (`~/.config/opencode/opencode.json`):
```json
{
  "mcpServers": {
    "admiral-mcp": {
      "url": "http://127.0.0.1:11089/mcp"
    }
  }
}
```

**Claude Desktop** (`%APPDATA%\Claude\claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "admiral-mcp": {
      "command": "uv",
      "args": ["run", "python", "-m", "admiral_mcp.server"],
      "cwd": "D:\\Dev\\repos\\admiral-mcp"
    }
  }
}
```

## 5. Using the Tools

### Basic Run Lifecycle

```
1. Agent calls register_run("deploy-v2", "plex-mcp", ["lint","test","deploy"], "opencode")
   → Run record created. Dashboard shows it.

2. Agent calls update_progress("deploy-v2", phase=0, cost=0.00, status="running")
   → Live Activity updates on iPhone: "Phase 1/3: lint (running)"

3. Agent calls update_progress("deploy-v2", phase=1, cost=0.07, status="running")
   → Live Activity: "Phase 2/3: test (running)"

4. Agent needs approval before production deploy:
   request_approval("deploy-v2", "Deploy to production?",
                    diff_ref="deploy-v2",
                    diff_content="+ 5 files changed\n- 2 files removed")
   → iPhone buzzes: "Approval Needed: Deploy to production?"
   → Agent blocks waiting...

5. User taps "Approve" on iPhone
   → POST /relay/approve arrives
   → Agent unblocks, returns "approve"

6. Agent calls update_progress("deploy-v2", phase=2, cost=0.14, status="complete")
   → Live Activity: "Phase 3/3: deploy (complete)"
```

### What Happens on Timeout

If the user doesn't respond within 5 minutes (configurable):
- `request_approval` returns `decision: "timeout"`
- The agent should decide: abort, retry, or proceed cautiously
- Never silently continue a destructive operation after timeout

## 6. The Dashboard

The React dashboard at http://127.0.0.1:11090 shows:

- **KPI Cards**: Server name, tool count, total runs, pending approvals
- **Backend Connection**: Green dot = connected, Red = offline
- **Recent Runs Table**: All recent runs with status and phase progress
- **Pending Approvals**: Cards showing what's waiting for human response

The dashboard auto-refreshes every 10 seconds and uses exponential backoff
retry when the backend is unreachable.

## 7. iPhone Setup (APNs)

To enable push notifications to your iPhone:

1. **Create an APNs Key** at https://developer.apple.com/account/
   - Keys → Create a Key → APNs Authentication Key
   - Download the `.p8` file

2. **Store the key outside the repo**:
   ```powershell
   mkdir C:\secrets\apns
   move AuthKey_XXXXXXXX.p8 C:\secrets\apns\
   ```

3. **Configure the env vars** in `.env`:
   ```
   ADMIRAL_APNS_KEY_PATH=C:\secrets\apns\AuthKey_XXXXXXXX.p8
   ADMIRAL_APNS_KEY_ID=XXXXXXXX
   ADMIRAL_APNS_TEAM_ID=XXXXXXXX
   ADMIRAL_APNS_TOPIC=ai.fleet.admiral-pager
   ADMIRAL_APNS_SANDBOX=1
   ADMIRAL_APNS_DEVICE_TOKEN=<your-device-push-token>
   ```

4. **Restart the server**. APNs is auto-detected on startup.

Without APNs configured, the server works fine — tools function normally,
they just don't send push notifications. The dashboard still updates.

## 8. Remote Access via Tailscale

To let your iPhone reach the server when away from your desk:

1. Install Tailscale on both devices
2. Find your Windows machine's Tailscale IP (e.g., `100.87.44.12`)
3. Set `ADMIRAL_HOST=100.87.44.12` in `.env`
4. The iOS app connects to `http://100.87.44.12:11089`

Never bind to `0.0.0.0` — MCP endpoints are attack surface. Tailscale
provides encrypted, authenticated networking.

## 9. Testing Without a Phone

You can simulate the approval flow with curl:

```powershell
# Terminal 1: Start server
just serve

# Terminal 2: Simulate approver (phone)
# This polls for pending approvals and resolves them
while ($true) {
    $pending = Invoke-RestMethod "http://127.0.0.1:11089/api/v1/diagnostics"
    foreach ($a in $pending.pending_approval_items) {
        Write-Host "Approving: $($a.summary)"
        Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:11089/relay/approve" -Headers @{Authorization="Bearer admin"} -ContentType "application/json" -Body "{`"approval_id`": `"$($a.approval_id)`"}"
    }
    Start-Sleep 2
}
```

## 10. Troubleshooting

| Symptom | Likely Cause | Fix |
|---------|-------------|-----|
| "Run not found" | register_run wasn't called | Always register before updating progress |
| Approval timeout | User away from phone | Increase ADMIRAL_APPROVAL_TIMEOUT |
| 406 Not Acceptable on /mcp | Missing Accept header | Add `Accept: application/json, text/event-stream` |
| 401 on /relay/* | Wrong or missing Bearer token | Check ADMIRAL_RELAY_TOKEN in .env |
| No push notifications | APNs not configured | Verify all APNS_* env vars are set |
| Dashboard shows "Offline" | Backend not running | Start with `just serve` or `.\start.ps1` |

## 11. Next Steps

- The iOS app ("Admiral Pager") is built separately in SwiftUI
- Future: chat interface on the dashboard for interacting with the agent
- Future: Prefab UI cards for in-conversation run status
- Future: Tauri NSIS installer for one-click desktop setup
