# admiral-mcp — Install

## Prerequisites

- Python 3.12+ (uv auto-fetches)
- [uv](https://docs.astral.sh/uv/)
- [just](https://github.com/casey/just)
- [Bun](https://bun.sh) (for the dashboard)

## Install

```powershell
git clone https://github.com/sandraschi/admiral-mcp.git
cd admiral-mcp
uv sync
bun --cwd webapp install
```

## Configure

```powershell
Copy-Item .env.example .env
# Edit .env with your values
```

## Run

```powershell
# Full stack (backend + dashboard):
.\start.ps1

# Backend only:
just serve
```

## MCP Client Registration

Add to your MCP client config (opencode.json, claude_desktop_config.json, .cursor/mcp.json):

```json
{
  "mcpServers": {
    "admiral-mcp": {
      "url": "http://127.0.0.1:11089/mcp"
    }
  }
}
```

## APNs Setup

1. Create an APNs key in Apple Developer → Keys → APNs Authentication Key
2. Download the .p8 file, store it outside the repo (e.g., `C:\secrets\apns\`)
3. Set `ADMIRAL_APNS_KEY_PATH`, `ADMIRAL_APNS_KEY_ID`, `ADMIRAL_APNS_TEAM_ID` in `.env`
4. Set `ADMIRAL_APNS_TOPIC` to your iOS app's bundle ID (`ai.fleet.admiral-pager`)
5. Get the device push token from the iOS app (printed at launch) and set `ADMIRAL_APNS_DEVICE_TOKEN`

## Remote Access (iPhone via Tailscale)

1. Install Tailscale on both machines
2. Find your Windows Tailscale IP: `tailscale ip -4`
3. Set `ADMIRAL_HOST=<tailscale-ip>` in `.env`
4. The iOS app connects to `http://<tailscale-ip>:11089`

Never bind to `0.0.0.0` — MCP endpoints are attack surface.

## iOS App (Mac — separate repo)

The iOS client "Admiral Pager" is a SwiftUI app built on Mac and distributed
via AltStore PAL. Full build instructions are in [README.md](README.md#ios-client-admiral-pager-mac--separate-repo).

Quick summary:
1. Apple Developer account ($99/year)
2. Install Xcode 27 beta
3. Scaffold SwiftUI project with APNs + Live Activity
4. Build in Xcode, test on simulator
5. Export `.ipa`, distribute via AltStore PAL (EU) or AltServer sideload

## Test with curl (no APNs needed)

```powershell
# FastMCP 3.4 streamable HTTP requires Accept header + session tracking.
$headers = @{
    "Content-Type" = "application/json"
    "Accept" = "application/json, text/event-stream"
}

# Step 1: Initialize and capture session ID
$init = Invoke-RestMethod -Uri "http://127.0.0.1:11089/mcp" -Method Post -Headers $headers -Body '{"jsonrpc":"2.0","method":"initialize","params":{"protocolVersion":"2025-11-25","capabilities":{},"clientInfo":{"name":"curl","version":"1"}},"id":0}'
$sid = $init.'mcp-session-id'
$headers['mcp-session-id'] = $sid

# Step 2: Register a run
Invoke-RestMethod -Uri "http://127.0.0.1:11089/mcp" -Method Post -Headers $headers -Body '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"register_run","arguments":{"run_id":"test-001","repo":"plex-mcp","phases":["lint","deploy"],"harness":"opencode"}},"id":1}'

# Step 3: Request approval (via curl since it blocks)
curl -X POST http://127.0.0.1:11089/mcp -H "Content-Type: application/json" -H "Accept: application/json, text/event-stream" -H "mcp-session-id: $sid" -d '{"jsonrpc":"2.0","method":"tools/call","params":{"name":"request_approval","arguments":{"run_id":"test-001","summary":"Deploy to prod?","diff_ref":"test-001","diff_content":"+ 5 files changed"}},"id":2}'

# Step 4: In another terminal, resolve the approval (phone callback)
curl -X POST http://127.0.0.1:11089/relay/approve -H "Authorization: Bearer admin" -H "Content-Type: application/json" -d '{"approval_id":"<approval_id>"}'
```
