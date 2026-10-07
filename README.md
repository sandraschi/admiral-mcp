# admiral-mcp

Agent-harness-to-iPhone pager bridge. Lets AI agent harnesses (OpenCode, Claude Code, Cursor) page your iPhone for approval and stream job progress via Live Activities.

## What it does

When an AI agent needs human approval (e.g., "deploy to production?"), it calls `request_approval`. The server pushes an actionable notification to your iPhone with Approve/Deny buttons. The agent blocks until you respond. Job progress is streamed via Live Activity updates.

## Two-Repo Architecture

This project has two codebases on two machines:

| Machine | Repo | Role |
|---------|------|------|
| **Windows (Goliath)** | `sandraschi/admiral-mcp` | FastMCP server, APNs relay, dashboard (this repo) |
| **Mac (needs a name)** | `sandraschi/admiral-pager` | SwiftUI iOS app, APNs receiver, AltStore PAL dist |

The server runs on Windows. The iOS app is built on Mac. They talk over Tailscale.

## Quick Start (Windows — this repo)

```powershell
# Install
uv sync

# Start full stack (backend + dashboard)
.\start.ps1
```

Server on `http://127.0.0.1:11089`, dashboard on `http://127.0.0.1:11090`:
- MCP transport: `/mcp`
- Relay REST: `/relay/*`
- Health API: `/api/v1/health`

## Tools

| Tool | Description |
|------|-------------|
| `register_run` | Announce a new agent job |
| `update_progress` | Advance phase, push Live Activity update |
| `request_approval` | Request human approval (blocks until response) |
| `resolve_approval` | Resolve pending approval (phone callback) |
| `get_diff` | Serve diff content to iOS app |

## Relay Endpoints

All require `Authorization: Bearer <token>` header.

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/relay/approve` | Approve a pending request |
| POST | `/relay/deny` | Deny a pending request |
| GET | `/relay/diff/{ref}` | Fetch diff content |

## Configuration

Copy `.env.example` to `.env` and fill in values. See `llms-full.txt` for the complete reference.

APNs is optional — the server works without it (no pushes sent, tools still function).

## Security

- Binds to localhost only by default. Use Tailscale IP for phone access.
- Bearer token auth on all relay endpoints
- .p8 APNs key lives outside the repo (env var path)
- Approval IDs are single-use (replay protected)

## Fleet Info

- Port: 11089/11090 (10700-11500 fleet band)
- FastMCP 3.4+ with Starlette relay
- SQLite persistence
- React + Vite + TailwindCSS dashboard
- uv + ruff + justfile
- MCPB packaging ready

---

## iOS Client: Admiral Pager (Mac — separate repo)

The iOS app is a SwiftUI app distributed via AltStore PAL. It receives
APNs pushes, displays actionable notifications with Approve/Deny buttons,
shows Live Activities with run progress, and fetches diff content from
the relay.

### Zero-to-App: Cursor Build Prompt

**Paste the entire block below into Cursor's AI chat on your Mac.**
It will scaffold the complete Xcode project, all Swift files, WidgetKit
extension, notification service, entitlements, and build settings.

---

```text
You are building an iOS app called "Admiral Pager". Follow these
instructions exactly. Generate every file with complete code. No stubs.

## Product
An iOS app that receives APNs push notifications from an MCP server
running on a Windows machine. It shows actionable alerts (Approve/Deny),
serves a Live Activity for job progress, and fetches diff content.

## Prerequisites (must already be done)
- macOS Sequoia 15.6+ with Xcode 27 beta installed
- Apple Developer account ($99/year, enrolled)
- Tailscale installed and connected to the same tailnet as the Windows
  server (the server runs at a Tailscale IP like 100.x.x.x:11089)
- Xcode 27 beta selected: `sudo xcode-select --switch /Applications/Xcode-27.0b.app`

## Xcode Project Setup
Create a new Xcode project with these exact settings:
- Template: iOS → App
- Product Name: Admiral Pager
- Team: (your Apple Developer team)
- Organization Identifier: ai.fleet
- Bundle Identifier: ai.fleet.admiral-pager
- Interface: SwiftUI
- Language: Swift
- Minimum Deployment: iOS 19.0
- Include Tests: none

After creating the base project, add two additional targets:
1. Widget Extension (for Live Activity):
   File → New → Target → Widget Extension
   Product Name: AdmiralPagerWidget
   Check "Include Live Activity" if available

2. Notification Service Extension (for rich push notifications):
   File → New → Target → Notification Service Extension
   Product Name: NotificationService

## Project File Structure
Create these directories and files under the Admiral Pager/ group:

```
Admiral Pager/
├── AdmiralPagerApp.swift           (replace the generated App file)
├── ContentView.swift                (replace the generated ContentView)
├── Info.plist                       (already exists, don't modify)
├── Admiral Pager.entitlements       (create this file)
├── Models/
│   ├── Run.swift
│   └── Approval.swift
├── Services/
│   ├── RelayClient.swift
│   └── NotificationManager.swift
├── Views/
│   ├── DashboardView.swift
│   ├── DiffView.swift
│   └── ApprovalRow.swift
└── Assets.xcassets/                 (already exists, leave as-is)
```

## Complete File Contents

### Admiral Pager.entitlements
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>aps-environment</key>
    <string>development</string>
</dict>
</plist>
```

### Models/Run.swift
```swift
import Foundation

struct Run: Identifiable, Codable {
    let runId: String
    let repo: String
    let status: String
    let phase: Int
    let phases: [String]

    var id: String { runId }

    var statusDisplay: String {
        status.replacingOccurrences(of: "_", with: " ").capitalized
    }

    var phaseDisplay: String {
        guard phase < phases.count else { return "\(phase)/\(phases.count)" }
        return "\(phase)/\(phases.count): \(phases[phase])"
    }
}
```

### Models/Approval.swift
```swift
import Foundation

struct Approval: Identifiable, Codable {
    let approvalId: String
    let runId: String
    let summary: String

    var id: String { approvalId }
}
```

### Services/RelayClient.swift
```swift
import Foundation

actor RelayClient {
    // CHANGE THIS to your Windows machine's Tailscale IP
    static let baseURL = "http://100.118.171.110:11089"
    // Must match ADMIRAL_RELAY_TOKEN in .env on Windows
    static let token = "admin"

    static func approve(approvalId: String) async throws {
        let url = URL(string: "\(baseURL)/relay/approve")!
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["approval_id": approvalId])
        let _ = try await URLSession.shared.data(for: req)
    }

    static func deny(approvalId: String) async throws {
        let url = URL(string: "\(baseURL)/relay/deny")!
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["approval_id": approvalId])
        let _ = try await URLSession.shared.data(for: req)
    }

    static func getDiff(ref: String) async throws -> String {
        let url = URL(string: "\(baseURL)/relay/diff/\(ref)")!
        var req = URLRequest(url: url)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, _) = try await URLSession.shared.data(for: req)
        return String(decoding: data, as: UTF8.self)
    }

    static func fetchDiagnostics() async throws -> DiagnosticsResponse {
        let url = URL(string: "\(baseURL)/api/v1/diagnostics")!
        let (data, _) = try await URLSession.shared.data(for: URLRequest(url: url))
        return try JSONDecoder().decode(DiagnosticsResponse.self, from: data)
    }
}

struct DiagnosticsResponse: Codable {
    let status: String
    let runsCount: Int
    let pendingApprovals: Int
    let recentRuns: [DiagnosticsRun]
    let pendingApprovalItems: [DiagnosticsApproval]

    enum CodingKeys: String, CodingKey {
        case status
        case runsCount = "runs_count"
        case pendingApprovals = "pending_approvals"
        case recentRuns = "recent_runs"
        case pendingApprovalItems = "pending_approval_items"
    }
}

struct DiagnosticsRun: Codable {
    let runId: String
    let repo: String
    let status: String
    let phase: Int
    let phases: [String]

    enum CodingKeys: String, CodingKey {
        case runId = "run_id"
        case repo, status, phase, phases
    }
}

struct DiagnosticsApproval: Codable {
    let approvalId: String
    let runId: String
    let summary: String

    enum CodingKeys: String, CodingKey {
        case approvalId = "approval_id"
        case runId = "run_id"
        case summary
    }
}
```

### Services/NotificationManager.swift
```swift
import UserNotifications
import UIKit

final class NotificationManager: NSObject, ObservableObject {
    static let shared = NotificationManager()

    @Published var deviceToken: String?
    @Published var isAuthorized = false

    private override init() {
        super.init()
    }

    func requestAuthorization() {
        let center = UNUserNotificationCenter.current()
        center.delegate = self
        center.requestAuthorization(options: [.alert, .sound, .badge]) { granted, _ in
            DispatchQueue.main.async {
                self.isAuthorized = granted
                if granted {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
        }

        let approve = UNNotificationAction(
            identifier: "APPROVE_ACTION",
            title: "Approve",
            options: [.authenticationRequired, .foreground]
        )
        let deny = UNNotificationAction(
            identifier: "DENY_ACTION",
            title: "Deny",
            options: [.authenticationRequired, .foreground]
        )
        let showDiff = UNNotificationAction(
            identifier: "SHOW_DIFF_ACTION",
            title: "Show Diff",
            options: [.foreground]
        )

        let category = UNNotificationCategory(
            identifier: "FLEET_APPROVAL",
            actions: [approve, deny, showDiff],
            intentIdentifiers: [],
            options: [.customDismissAction]
        )
        center.setNotificationCategories([category])
    }

    func didRegister(token: Data) {
        let tokenString = token.map { String(format: "%02x", $0) }.joined()
        DispatchQueue.main.async {
            self.deviceToken = tokenString
        }
        print("APNs device token: \(tokenString)")
    }
}

// MARK: - UNUserNotificationCenterDelegate
extension NotificationManager: UNUserNotificationCenterDelegate {
    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        willPresent notification: UNNotification,
        withCompletionHandler completionHandler: @escaping (UNNotificationPresentationOptions) -> Void
    ) {
        completionHandler([.banner, .sound, .badge])
    }

    func userNotificationCenter(
        _ center: UNUserNotificationCenter,
        didReceive response: UNNotificationResponse,
        withCompletionHandler completionHandler: @escaping () -> Void
    ) {
        let userInfo = response.notification.request.content.userInfo
        let approvalId = userInfo["approval_id"] as? String ?? ""

        switch response.actionIdentifier {
        case "APPROVE_ACTION":
            Task { try? await RelayClient.approve(approvalId: approvalId) }
        case "DENY_ACTION":
            Task { try? await RelayClient.deny(approvalId: approvalId) }
        case "SHOW_DIFF_ACTION":
            let diffRef = userInfo["diff_ref"] as? String ?? ""
            // Post notification to navigate to diff view
            NotificationCenter.default.post(
                name: .showDiff,
                object: nil,
                userInfo: ["diffRef": diffRef]
            )
        default:
            NotificationCenter.default.post(
                name: .approvalTapped,
                object: nil,
                userInfo: ["approvalId": approvalId]
            )
        }
        completionHandler()
    }
}

extension Notification.Name {
    static let showDiff = Notification.Name("showDiff")
    static let approvalTapped = Notification.Name("approvalTapped")
}
```

### AdmiralPagerApp.swift
```swift
import SwiftUI
import UIKit

@main
struct AdmiralPagerApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate
    @StateObject private var nav = NavigationState()

    var body: some Scene {
        WindowGroup {
            ContentView()
                .environmentObject(nav)
                .onOpenURL { _ in }
        }
    }
}

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        NotificationManager.shared.requestAuthorization()
        return true
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        NotificationManager.shared.didRegister(token: deviceToken)
    }

    func application(
        _ application: UIApplication,
        didFailToRegisterForRemoteNotificationsWithError error: Error
    ) {
        print("Failed to register for remote notifications: \(error)")
    }
}

final class NavigationState: ObservableObject {
    @Published var selectedDiffRef: String?
    @Published var selectedApprovalId: String?
}
```

### ContentView.swift
```swift
import SwiftUI

struct ContentView: View {
    @EnvironmentObject var nav: NavigationState

    var body: some View {
        NavigationStack {
            DashboardView()
                .navigationTitle("Admiral")
                .navigationDestination(item: $nav.selectedDiffRef) { ref in
                    DiffView(diffRef: ref)
                }
        }
        .onReceive(NotificationCenter.default.publisher(for: .showDiff)) { notif in
            nav.selectedDiffRef = notif.userInfo?["diffRef"] as? String
        }
        .onReceive(NotificationCenter.default.publisher(for: .approvalTapped)) { _ in
            // Refresh dashboard when an approval action occurs
        }
    }
}

extension String: @retroactive Identifiable {
    public var id: String { self }
}
```

### Views/DashboardView.swift
```swift
import SwiftUI

struct DashboardView: View {
    @State private var runs: [DiagnosticsRun] = []
    @State private var approvals: [DiagnosticsApproval] = []
    @State private var isRefreshing = false
    @State private var errorMessage: String?
    @State private var deviceToken: String?

    private let timer = Timer.publish(every: 10, on: .main, in: .common).autoconnect()

    var body: some View {
        List {
            // Status Section
            Section("Status") {
                HStack {
                    Circle()
                        .fill(errorMessage == nil ? Color.green : Color.red)
                        .frame(width: 8, height: 8)
                    Text(errorMessage == nil ? "Connected" : "Offline")
                        .font(.subheadline)
                        .foregroundStyle(.secondary)
                }

                if let token = deviceToken {
                    VStack(alignment: .leading, spacing: 4) {
                        Text("Device Token")
                            .font(.caption)
                            .foregroundStyle(.secondary)
                        Text(token)
                            .font(.caption2)
                            .monospaced()
                            .foregroundStyle(.tertiary)
                    }
                }
            }

            // Pending Approvals Section
            Section("Pending Approvals (\(approvals.count))") {
                if approvals.isEmpty {
                    Text("No pending approvals")
                        .font(.subheadline)
                        .foregroundStyle(.tertiary)
                } else {
                    ForEach(approvals, id: \.approvalId) { approval in
                        ApprovalRow(approval: approval)
                    }
                }
            }

            // Active Runs Section
            Section("Recent Runs (\(runs.count))") {
                if runs.isEmpty {
                    Text("No runs yet")
                        .font(.subheadline)
                        .foregroundStyle(.tertiary)
                } else {
                    ForEach(runs, id: \.runId) { run in
                        RunRow(run: run)
                    }
                }
            }
        }
        .refreshable { await refresh() }
        .onReceive(timer) { _ in Task { await refresh() } }
        .task { await refresh() }
    }

    private func refresh() async {
        isRefreshing = true
        defer { isRefreshing = false }

        do {
            let diag = try await RelayClient.fetchDiagnostics()
            runs = diag.recentRuns
            approvals = diag.pendingApprovalItems
            errorMessage = nil
        } catch {
            errorMessage = error.localizedDescription
        }
    }
}

struct RunRow: View {
    let run: DiagnosticsRun

    var body: some View {
        VStack(alignment: .leading, spacing: 4) {
            HStack {
                Text(run.runId)
                    .font(.headline)
                Spacer()
                StatusBadge(status: run.status)
            }
            Text("\(run.repo) · Phase \(run.phase)/\(run.phases.count)")
                .font(.caption)
                .foregroundStyle(.secondary)
        }
        .padding(.vertical, 2)
    }
}

struct StatusBadge: View {
    let status: String

    private var color: Color {
        switch status {
        case "running": return .blue
        case "complete": return .green
        case "failed": return .red
        case "awaiting_approval": return .orange
        case "cancelled": return .gray
        default: return .secondary
        }
    }

    var body: some View {
        Text(status.replacingOccurrences(of: "_", with: " ").capitalized)
            .font(.caption2)
            .fontWeight(.medium)
            .padding(.horizontal, 8)
            .padding(.vertical, 2)
            .background(color.opacity(0.15))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}
```

### Views/ApprovalRow.swift
```swift
import SwiftUI

struct ApprovalRow: View {
    let approval: DiagnosticsApproval

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text(approval.summary)
                .font(.subheadline)
            Text("Run: \(approval.runId)")
                .font(.caption)
                .foregroundStyle(.secondary)

            HStack(spacing: 12) {
                Button {
                    Task { try? await RelayClient.approve(approvalId: approval.approvalId) }
                } label: {
                    Label("Approve", systemImage: "checkmark.circle.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(.green)

                Button {
                    Task { try? await RelayClient.deny(approvalId: approval.approvalId) }
                } label: {
                    Label("Deny", systemImage: "xmark.circle.fill")
                        .frame(maxWidth: .infinity)
                }
                .buttonStyle(.borderedProminent)
                .tint(.red)
            }
        }
        .padding(.vertical, 4)
    }
}
```

### Views/DiffView.swift
```swift
import SwiftUI

struct DiffView: View {
    let diffRef: String
    @State private var content: String = ""
    @State private var isLoading = true

    var body: some View {
        Group {
            if isLoading {
                ProgressView("Loading diff...")
            } else if content.isEmpty {
                ContentUnavailableView(
                    "No Diff Content",
                    systemImage: "doc.text.magnifyingglass",
                    description: Text("No diff found for \"\(diffRef)\"")
                )
            } else {
                ScrollView {
                    Text(content)
                        .font(.system(.caption, design: .monospaced))
                        .padding()
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
            }
        }
        .navigationTitle(diffRef)
        .task { await load() }
    }

    private func load() async {
        isLoading = true
        defer { isLoading = false }
        do {
            content = try await RelayClient.getDiff(ref: diffRef)
        } catch {
            content = "Error loading diff: \(error.localizedDescription)"
        }
    }
}
```

### AdmiralPagerWidget/AdmiralPagerWidget.swift
Replace the generated Widget file with:

```swift
import WidgetKit
import SwiftUI

struct RunProgressEntry: TimelineEntry {
    let date: Date
    let runId: String
    let phase: Int
    let phaseName: String
    let status: String
    let cost: String
    let totalPhases: Int
}

struct RunProgressWidget: Widget {
    let kind = "RunProgressWidget"

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: RunProgressEntry.self) { context in
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(context.state.runId)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("Phase \(context.state.phase + 1)/\(context.state.totalPhases): \(context.state.phaseName)")
                        .font(.headline)
                }
                Spacer()
                StatusTag(status: context.state.status)
                Text(context.state.cost)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding()
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Text(context.state.runId).font(.caption)
                }
                DynamicIslandExpandedRegion(.center) {
                    Text("\(context.state.phaseName) — \(context.state.status)")
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(context.state.cost)
                }
            } compactLeading: {
                Text("P\(context.state.phase + 1)")
            } compactTrailing: {
                Text(context.state.status.prefix(4))
            } minimal: {
                Text("\(context.state.phase + 1)")
            }
        }
    }
}

struct StatusTag: View {
    let status: String
    var color: Color {
        switch status {
        case "running": return .blue
        case "complete": return .green
        case "failed": return .red
        default: return .secondary
        }
    }
    var body: some View {
        Text(status.capitalized)
            .font(.caption2)
            .padding(.horizontal, 6)
            .padding(.vertical, 2)
            .background(color.opacity(0.2))
            .foregroundStyle(color)
            .clipShape(Capsule())
    }
}
```

### NotificationService/NotificationService.swift
Replace the generated file with:

```swift
import UserNotifications

class NotificationService: UNNotificationServiceExtension {
    var contentHandler: ((UNNotificationContent) -> Void)?
    var bestAttemptContent: UNMutableNotificationContent?

    override func didReceive(
        _ request: UNNotificationRequest,
        withContentHandler contentHandler: @escaping (UNNotificationContent) -> Void
    ) {
        self.contentHandler = contentHandler
        bestAttemptContent = (request.content.mutableCopy() as? UNMutableNotificationContent)

        guard let bestAttemptContent = bestAttemptContent else {
            contentHandler(request.content)
            return
        }

        // Forward all custom payload keys so the main app can read them
        // (approval_id, run_id, diff_ref are already in userInfo from APNs)
        contentHandler(bestAttemptContent)
    }

    override func serviceExtensionTimeWillExpire() {
        if let contentHandler = contentHandler, let bestAttemptContent = bestAttemptContent {
            contentHandler(bestAttemptContent)
        }
    }
}
```

## Xcode Capabilities
After creating files, enable these in the main target's Signing & Capabilities:
- Push Notifications
- Background Modes (check "Remote notifications")

In the Widget Extension target:
- No extra capabilities needed (Live Activity inherits from main app)

## Build Settings to Verify
- Main target: Enable Modules (YES), Swift Language Version (Swift 6)
- Widget target: Same, plus "Supports Live Activities" (YES) in Info.plist
- Notification Service target: Deployment target matches main app

## Build & Run on Simulator
```bash
# Select a simulator
xcrun simctl list devices | grep iPhone

# Build
xcodebuild -project "Admiral Pager.xcodeproj" \
  -scheme "Admiral Pager" \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  build

# Or open in Xcode and press Cmd+R
```

## After Building
1. Run the app on a simulator. Look in Xcode console for:
   "APNs device token: <hex string>"
2. Copy that token to ADMIRAL_APNS_DEVICE_TOKEN in .env on the Windows
   server. This is how the server knows which device to push to.

## Testing Without APNs
You can test the relay callbacks without push notifications:

From Mac Terminal:
```bash
# Fetch diagnostics to see pending approvals
curl http://100.118.171.110:11089/api/v1/diagnostics | python3 -m json.tool

# Approve a pending approval
curl -X POST http://100.118.171.110:11089/relay/approve \
  -H "Authorization: Bearer admin" \
  -H "Content-Type: application/json" \
  -d '{"approval_id":"<approval-id-from-diagnostics>"}'
```
```

---

### Manual Setup (if not using Cursor)

If you prefer to set up manually instead of using the Cursor prompt above,
follow the step-by-step guide below.

### Prerequisites

- **Apple Developer account** ($99/year, https://developer.apple.com)
  - Without this: no APNs, no app signing, no device deployment
  - Sign up at developer.apple.com → Account → Enroll
  - Takes 1-2 business days to activate

- **Mac** running macOS Sequoia 15.6+ (or latest Sonoma)
  - Minimum 16 GB RAM, 50 GB free disk
  - Apple Silicon (M1+) strongly recommended

- **Tailscale** installed on both Mac and Windows
  - Free tier is sufficient — one tailnet, both machines

### Step 1: Install Xcode 27 Beta

Xcode 27 is the 2026 release (iOS 20 SDK). You need the beta for the
latest SwiftUI APIs and Live Activity improvements.

```bash
# Download from Apple Developer:
# https://developer.apple.com/download/

# Or via xcodes (recommended — manages multiple Xcode versions):
brew install xcodesorg/made/xcodes
xcodes install 27.0b   # current beta at time of writing

# Select it as the active Xcode:
sudo xcode-select --switch /Applications/Xcode-27.0b.app

# Launch once to accept license and install additional components:
open /Applications/Xcode-27.0b.app
```

Verify:

```bash
xcodebuild -version        # Xcode 27.0
xcrun simctl list devices  # Should show iOS 20 simulators
```

### Step 2: Set Up Your IDE

Pick one — both work for SwiftUI:

**Cursor (recommended — AI-native):**

```bash
brew install --cask cursor
# Then install the Swift extension from Cursor's extension marketplace
```

Cursor is the same app on Mac as on Windows. Your license transfers.

**Zen (free, open-source):**

```bash
brew install --cask zen-browser
# Zen is the browser; you still need Xcode for building
# For Zed editor (better Swift support, also free):
brew install --cask zed
```

**Terminal-only (no IDE):**

```bash
# All you really need is Xcode + git + your editor of choice
# Build from command line with xcodebuild
```

### Step 3: Scaffold the iOS Project

```bash
# Create the project directory
mkdir ~/Dev/admiral-pager
cd ~/Dev/admiral-pager

# Create a new SwiftUI app with Xcode project file
# (Do this in Xcode GUI once, then edit in Cursor/Zed)
open -a Xcode-27.0b

# In Xcode:
# File → New → Project → iOS → App
# Product Name: Admiral Pager
# Team: your Apple ID
# Organization Identifier: ai.fleet
# Interface: SwiftUI
# Language: Swift
# Include: none (add Notification Service Extension later for rich notifications)

# After creating, close Xcode and work from Cursor/Zed
```

### Step 4: Project Structure

Your SwiftUI project should have:

```
admiral-pager/
├── Admiral Pager.xcodeproj/
├── Admiral Pager/
│   ├── AdmiralPagerApp.swift      # @main App struct
│   ├── ContentView.swift           # Main UI (runs list, approvals)
│   ├── Models/
│   │   ├── Run.swift               # Run model
│   │   └── Approval.swift          # Approval model
│   ├── Services/
│   │   ├── RelayClient.swift       # HTTP client for relay REST
│   │   └── PushDelegate.swift      # APNs registration + handling
│   ├── Views/
│   │   ├── DashboardView.swift     # Active runs + pending approvals
│   │   ├── DiffView.swift          # Diff content viewer
│   │   └── ApprovalRow.swift
│   ├── LiveActivity/
│   │   └── RunProgressWidget.swift # Live Activity UI (WidgetKit)
│   └── Assets.xcassets/
├── AdmiralPagerWidget/             # WidgetKit extension
│   └── AdmiralPagerWidget.swift    # Live Activity widget
└── NotificationService/            # Rich notification extension
    └── NotificationService.swift
```

### Step 5: Core SwiftUI App

**AdmiralPagerApp.swift** — entry point:

```swift
import SwiftUI
import UserNotifications

@main
struct AdmiralPagerApp: App {
    @UIApplicationDelegateAdaptor(AppDelegate.self) var appDelegate

    var body: some Scene {
        WindowGroup {
            ContentView()
        }
    }
}

class AppDelegate: NSObject, UIApplicationDelegate {
    func application(
        _ application: UIApplication,
        didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
    ) -> Bool {
        // Request notification permission
        UNUserNotificationCenter.current().requestAuthorization(options: [.alert, .sound, .badge]) { granted, error in
            if granted {
                DispatchQueue.main.async {
                    UIApplication.shared.registerForRemoteNotifications()
                }
            }
        }
        return true
    }

    func application(
        _ application: UIApplication,
        didRegisterForRemoteNotificationsWithDeviceToken deviceToken: Data
    ) {
        let token = deviceToken.map { String(format: "%02x", $0) }.joined()
        print("APNs device token: \(token)")
        // Copy this token to ADMIRAL_APNS_DEVICE_TOKEN in .env on Windows
    }
}
```

**RelayClient.swift** — HTTP calls to the server:

```swift
import Foundation

actor RelayClient {
    // Change this to your Windows machine's Tailscale IP
    static let baseURL = "http://100.118.171.110:11089"
    static let token = "admin"  // Must match ADMIRAL_RELAY_TOKEN

    static func approve(approvalId: String) async throws {
        let url = URL(string: "\(baseURL)/relay/approve")!
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["approval_id": approvalId])
        let _ = try await URLSession.shared.data(for: req)
    }

    static func deny(approvalId: String) async throws {
        let url = URL(string: "\(baseURL)/relay/deny")!
        var req = URLRequest(url: url)
        req.httpMethod = "POST"
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        req.setValue("application/json", forHTTPHeaderField: "Content-Type")
        req.httpBody = try JSONEncoder().encode(["approval_id": approvalId])
        let _ = try await URLSession.shared.data(for: req)
    }

    static func getDiff(ref: String) async throws -> String {
        let url = URL(string: "\(baseURL)/relay/diff/\(ref)")!
        var req = URLRequest(url: url)
        req.setValue("Bearer \(token)", forHTTPHeaderField: "Authorization")
        let (data, _) = try await URLSession.shared.data(for: req)
        return String(decoding: data, as: UTF8.self)
    }
}
```

### Step 6: Handle Actionable Notifications

Register the `FLEET_APPROVAL` notification category so Approve/Deny
buttons appear:

```swift
func registerNotificationCategories() {
    let approve = UNNotificationAction(
        identifier: "APPROVE_ACTION",
        title: "Approve",
        options: [.authenticationRequired, .foreground]
    )
    let deny = UNNotificationAction(
        identifier: "DENY_ACTION",
        title: "Deny",
        options: [.authenticationRequired, .foreground]
    )
    let showDiff = UNNotificationAction(
        identifier: "SHOW_DIFF_ACTION",
        title: "Show Diff",
        options: [.foreground]
    )

    let category = UNNotificationCategory(
        identifier: "FLEET_APPROVAL",
        actions: [approve, deny, showDiff],
        intentIdentifiers: [],
        options: [.customDismissAction]
    )

    UNUserNotificationCenter.current().setNotificationCategories([category])
}
```

In your `AppDelegate` or a `UNUserNotificationCenterDelegate`:

```swift
func userNotificationCenter(
    _ center: UNUserNotificationCenter,
    didReceive response: UNNotificationResponse,
    withCompletionHandler completionHandler: @escaping () -> Void
) {
    let userInfo = response.notification.request.content.userInfo
    let approvalId = userInfo["approval_id"] as? String ?? ""

    switch response.actionIdentifier {
    case "APPROVE_ACTION":
        Task { try? await RelayClient.approve(approvalId: approvalId) }
    case "DENY_ACTION":
        Task { try? await RelayClient.deny(approvalId: approvalId) }
    case "SHOW_DIFF_ACTION":
        let diffRef = userInfo["diff_ref"] as? String ?? ""
        // Navigate to diff view with diffRef
    default:
        break
    }
    completionHandler()
}
```

### Step 7: Live Activity (WidgetKit Extension)

Add a Widget Extension target in Xcode:

```
File → New → Target → Widget Extension
```

**RunProgressWidget.swift**:

```swift
import WidgetKit
import SwiftUI

struct RunProgressEntry: TimelineEntry {
    let date: Date
    let runId: String
    let phase: Int
    let phaseName: String
    let status: String
    let cost: String
    let totalPhases: Int
}

struct RunProgressWidget: Widget {
    let kind = "RunProgressWidget"

    var body: some WidgetConfiguration {
        ActivityConfiguration(for: RunProgressEntry.self) { context in
            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text(context.state.runId)
                        .font(.caption)
                        .foregroundStyle(.secondary)
                    Text("Phase \(context.state.phase + 1)/\(context.state.totalPhases): \(context.state.phaseName)")
                        .font(.headline)
                }
                Spacer()
                Text(context.state.cost)
                    .font(.caption)
                    .foregroundStyle(.secondary)
            }
            .padding()
        } dynamicIsland: { context in
            DynamicIsland {
                DynamicIslandExpandedRegion(.leading) {
                    Text(context.state.runId)
                }
                DynamicIslandExpandedRegion(.center) {
                    Text("\(context.state.phaseName) — \(context.state.status)")
                }
                DynamicIslandExpandedRegion(.trailing) {
                    Text(context.state.cost)
                }
            } compactLeading: {
                Text("P\(context.state.phase + 1)")
            } compactTrailing: {
                Text(context.state.status.prefix(4))
            } minimal: {
                Text("\(context.state.phase + 1)")
            }
        }
    }
}
```

### Step 8: Add Push Capabilities

In `Admiral Pager.entitlements`:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>aps-environment</key>
    <string>development</string>
</dict>
</plist>
```

In Xcode project settings → Signing & Capabilities:
- Add "Push Notifications" capability
- Add "Live Activities" capability (if available in Xcode 27)

### Step 9: Build & Test on Simulator

```bash
# List available simulators
xcrun simctl list devices | grep iPhone

# Build for simulator
xcodebuild -project "Admiral Pager.xcodeproj" \
  -scheme "Admiral Pager" \
  -destination 'platform=iOS Simulator,name=iPhone 17 Pro' \
  build

# Or open in Xcode and press Cmd+R
```

Simulator limitations:
- No real APNs pushes (use `xcrun simctl push` to send test pushes)
- No AltStore sideloading (need real device)
- Live Activities render but don't appear on Lock Screen in simulator

Test the relay manually from Terminal on Mac:

```bash
# Mac → Windows over Tailscale
curl -X POST http://100.118.171.110:11089/relay/approve \
  -H "Authorization: Bearer admin" \
  -H "Content-Type: application/json" \
  -d '{"approval_id":"test-123"}'
```

### Step 10: Export for AltStore PAL / AltMarket

AltStore PAL is EU-only (DMA-mandated alternative app marketplace).
If you're in the EU, this is the primary distribution path. If not,
you can still sideload via AltStore (classic, requires AltServer on Mac).

**EU users — AltStore PAL:**

1. Install AltStore PAL on iPhone: https://altstore.io (EU link)
2. In Xcode, archive the app: Product → Archive
3. Export as `.ipa`: Distribute App → Custom → Export
4. Upload the `.ipa` to your AltStore PAL source

**Non-EU users — AltStore Classic:**

1. Install AltServer on Mac: `brew install --cask altstore`
2. Connect iPhone via USB, enable Wi-Fi sync in Finder
3. In Xcode, archive and export as `.ipa`
4. Drag `.ipa` onto AltServer → "Install to [your iPhone]"
5. Re-sign every 7 days (free account) or yearly (paid account)

**Source JSON for AltStore PAL (host alongside your .ipa):**

```json
{
  "name": "Admiral Pager",
  "identifier": "ai.fleet.admiral-pager",
  "apps": [
    {
      "bundleIdentifier": "ai.fleet.admiral-pager",
      "name": "Admiral Pager",
      "version": "0.1.0",
      "versionDate": "2026-07-12",
      "downloadURL": "https://your-server.com/admiral-pager.ipa",
      "size": 5242880,
      "iconURL": "https://your-server.com/icon.png",
      "screenshotURLs": []
    }
  ]
}
```

### Step 11: Production Checklist

- [ ] Replace `admin` relay token with a strong random string
- [ ] Set `ADMIRAL_APNS_SANDBOX=0` in `.env` on Windows
- [ ] Change `aps-environment` to `production` in entitlements
- [ ] Ship production APNs key to the Windows server (never commit it)
- [ ] Set `ADMIRAL_HOST` to your Tailscale IP (not `0.0.0.0`)
- [ ] Add fallback UI for when Windows machine is unreachable
- [ ] Add notification to re-open app after device reboot
- [ ] Test end-to-end: agent calls `request_approval` → phone buzzes → tap Approve → agent unblocks

### iOS Build Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| "No provisioning profile" | No paid dev account | Enroll at developer.apple.com |
| "Signing requires a team" | Team not set in Xcode | Xcode → Target → Signing → Team |
| APNs pushes not arriving | Sandbox/prod mismatch | Match `aps-environment` to ADMIRAL_APNS_SANDBOX |
| "This app cannot be installed" | AltStore PAL source URL wrong | Verify source JSON is publicly accessible |
| Live Activity doesn't update | Wrong push type | Set `push_type: liveactivity` in APNs payload |
| Connection refused from iPhone | Firewall or wrong IP | Use Tailscale IP, verify Tailscale connected on both |
