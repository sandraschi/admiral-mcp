import { useCallback, useEffect, useState } from "react";
import { fetchHealth } from "../../lib/api";

export default function Topbar() {
  const [backendOk, setBackendOk] = useState<boolean | null>(null);

  const refresh = useCallback(async () => {
    try {
      const h = await fetchHealth();
      setBackendOk(h.status === "ok");
    } catch {
      setBackendOk(false);
    }
  }, []);

  useEffect(() => {
    refresh();
    const interval = setInterval(refresh, 10_000);
    return () => clearInterval(interval);
  }, [refresh]);

  return (
    <header className="flex items-center justify-between border-b border-zinc-800 bg-zinc-900/50 backdrop-blur px-6 py-3">
      <h1 className="text-sm font-medium text-zinc-300">Dashboard</h1>
      <div className="flex items-center gap-2">
        <div
          data-testid="backend-dot"
          className={clsxDot(backendOk)}
        />
        <span className="text-xs text-zinc-500">
          {backendOk === null
            ? "Connecting..."
            : backendOk
              ? "Connected"
              : "Offline"}
        </span>
      </div>
    </header>
  );
}

function clsxDot(ok: boolean | null): string {
  const base = "h-2 w-2 rounded-full animate-pulse";
  if (ok === null) return `${base} bg-zinc-500`;
  if (ok) return `${base} bg-green-500`;
  return `${base} bg-red-500`;
}
