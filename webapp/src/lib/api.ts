const API_BASE = "http://127.0.0.1:11089";

export async function fetchHealth() {
  const r = await fetch(`${API_BASE}/api/v1/health`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

export async function fetchDiagnostics() {
  const r = await fetch(`${API_BASE}/api/v1/diagnostics`);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}
