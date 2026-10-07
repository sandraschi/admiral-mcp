import { useCallback, useEffect, useState } from "react";
import { Activity, Clock, Hammer, Hourglass } from "lucide-react";
import { fetchDiagnostics, fetchHealth } from "../lib/api";
import { useZoom } from "../lib/use-zoom";

interface HealthData {
  status: string;
  server: string;
  version: string;
  uptime_seconds: number;
  tool_count: number;
  runs_count: number;
  pending_approvals: number;
}

interface DiagnosticsData {
  status: string;
  server: string;
  version: string;
  uptime_seconds: number;
  tool_count: number;
  runs_count: number;
  pending_approvals: number;
  recent_runs: RunItem[];
  pending_approval_items: ApprovalItem[];
  errors: string[];
}

interface RunItem {
  run_id: string;
  repo: string;
  status: string;
  phase: number;
  phases: string[];
}

interface ApprovalItem {
  approval_id: string;
  run_id: string;
  summary: string;
}

function fmtUptime(seconds: number): string {
  if (seconds < 60) return `${seconds}s`;
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m`;
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  return `${h}h ${m}m`;
}

export default function Dashboard() {
  useZoom();

  const [health, setHealth] = useState<HealthData | null>(null);
  const [diag, setDiag] = useState<DiagnosticsData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [retryDelay, setRetryDelay] = useState(1);
  const [retryTimer, setRetryTimer] = useState<ReturnType<typeof setTimeout> | null>(null);

  const load = useCallback(async () => {
    try {
      const [h, d] = await Promise.all([fetchHealth(), fetchDiagnostics()]);
      setHealth(h);
      setDiag(d);
      setError(null);
      setRetryDelay(1);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Connection failed");
      const timer = setTimeout(() => {
        setRetryDelay((prev) => Math.min(prev * 2, 16));
        load();
      }, retryDelay * 1000);
      setRetryTimer(timer);
    }
  }, [retryDelay]);

  useEffect(() => {
    load();
    const interval = setInterval(load, 10_000);
    return () => {
      clearInterval(interval);
      if (retryTimer) clearTimeout(retryTimer);
    };
  }, [load, retryTimer]);

  if (error && !health) {
    return (
      <div className="flex flex-col items-center justify-center py-24 gap-4">
        <div className="text-red-400 text-sm">Backend unreachable: {error}</div>
        <div className="text-zinc-500 text-xs">
          Retrying in {retryDelay}s...
        </div>
      </div>
    );
  }

  return (
    <div data-testid="dashboard" className="space-y-6">
      {/* KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          testid="kpi-server"
          icon={<Activity className="h-5 w-5" />}
          label="Server"
          value={health?.server ?? "—"}
        />
        <KpiCard
          testid="kpi-tools"
          icon={<Hammer className="h-5 w-5" />}
          label="MCP Tools"
          value={health?.tool_count?.toString() ?? "—"}
        />
        <KpiCard
          testid="kpi-runs"
          icon={<Clock className="h-5 w-5" />}
          label="Total Runs"
          value={health?.runs_count?.toString() ?? "—"}
        />
        <KpiCard
          testid="kpi-pending"
          icon={<Hourglass className="h-5 w-5" />}
          label="Pending Approvals"
          value={health?.pending_approvals?.toString() ?? "—"}
        />
      </div>

      {/* Uptime + Version */}
      <div className="flex items-center gap-4 text-xs text-zinc-500">
        <span>Uptime: {health ? fmtUptime(health.uptime_seconds) : "—"}</span>
        <span>Version: {health?.version ?? "—"}</span>
        {error && <span className="text-red-400">Health poll: {error}</span>}
      </div>

      {/* Recent Runs Table */}
      <section>
        <h2 className="text-sm font-medium text-zinc-300 mb-3">Recent Runs</h2>
        {diag?.recent_runs && diag.recent_runs.length > 0 ? (
          <div className="overflow-x-auto rounded-lg border border-zinc-800">
            <table className="w-full text-xs text-zinc-400">
              <thead className="bg-zinc-900 text-zinc-500 uppercase">
                <tr>
                  <th className="px-4 py-2 text-left">Run ID</th>
                  <th className="px-4 py-2 text-left">Repo</th>
                  <th className="px-4 py-2 text-left">Status</th>
                  <th className="px-4 py-2 text-left">Phase</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-zinc-800">
                {diag.recent_runs.map((r) => (
                  <tr key={r.run_id} className="hover:bg-zinc-900/50">
                    <td className="px-4 py-2 font-mono text-zinc-300">
                      {r.run_id}
                    </td>
                    <td className="px-4 py-2">{r.repo}</td>
                    <td className="px-4 py-2">
                      <StatusBadge status={r.status} />
                    </td>
                    <td className="px-4 py-2">
                      {r.phase}/{r.phases.length}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="text-xs text-zinc-600 py-8 text-center border border-dashed border-zinc-800 rounded-lg">
            No runs yet. Use register_run to create one.
          </div>
        )}
      </section>

      {/* Pending Approvals */}
      <section>
        <h2 className="text-sm font-medium text-zinc-300 mb-3">
          Pending Approvals
        </h2>
        {diag?.pending_approval_items &&
        diag.pending_approval_items.length > 0 ? (
          <div className="space-y-2">
            {diag.pending_approval_items.map((a) => (
              <div
                key={a.approval_id}
                className="flex items-center gap-4 rounded-lg border border-amber-500/20 bg-amber-500/5 px-4 py-3"
              >
                <Hourglass className="h-4 w-4 text-amber-500 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="text-xs text-zinc-300 truncate">
                    {a.summary}
                  </div>
                  <div className="text-xs text-zinc-600 mt-0.5">
                    run: {a.run_id} · id: {a.approval_id}
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-xs text-zinc-600 py-6 text-center border border-dashed border-zinc-800 rounded-lg">
            No pending approvals.
          </div>
        )}
      </section>
    </div>
  );
}

function KpiCard({
  testid,
  icon,
  label,
  value,
}: {
  testid: string;
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div
      data-testid={testid}
      className="rounded-lg border border-zinc-800 bg-zinc-900/50 p-4"
    >
      <div className="flex items-center gap-2 text-zinc-500 mb-2">
        {icon}
        <span className="text-xs uppercase tracking-wider">{label}</span>
      </div>
      <div className="text-2xl font-semibold text-zinc-100">{value}</div>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  const color: Record<string, string> = {
    queued: "bg-zinc-700 text-zinc-300",
    running: "bg-blue-500/10 text-blue-400",
    awaiting_approval: "bg-amber-500/10 text-amber-400",
    complete: "bg-green-500/10 text-green-400",
    failed: "bg-red-500/10 text-red-400",
    cancelled: "bg-zinc-700 text-zinc-500",
  };
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-medium ${color[status] ?? "bg-zinc-800 text-zinc-500"}`}
    >
      {status}
    </span>
  );
}
