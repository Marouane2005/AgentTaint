export type SessionInfo = {
  mode: string;
  label: string;
  seeded_at?: string | null;
  notes?: string[];
};

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: { Accept: "application/json", ...(init?.headers || {}) },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status} ${path}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export function fetchOverview() {
  return getJson<{
    session: SessionInfo;
    decisions: Record<string, number>;
    graph: Record<string, number>;
    system: Record<string, unknown>;
  }>("/api/v1/metrics/overview");
}

export function fetchDecisions() {
  return getJson<{
    session: SessionInfo;
    items: Array<Record<string, unknown>>;
  }>("/api/v1/decisions");
}

export function fetchGraph() {
  return getJson<{
    session: SessionInfo;
    nodes: Array<Record<string, unknown>>;
    edges: Array<Record<string, unknown>>;
    status_legend: Record<string, string>;
    relationship_legend: Record<string, string>;
  }>("/api/v1/graph/export");
}

export function fetchReconstruction() {
  return getJson<{
    session: SessionInfo;
    disclaimer: string;
    source: string;
    evidence: Array<Record<string, unknown>>;
    empty: boolean;
    message: string | null;
  }>("/api/v1/reconstruction");
}

export function fetchBenchmarks() {
  return getJson<{
    available: boolean;
    disclaimer: string;
    reports: Array<Record<string, unknown>>;
    message: string | null;
  }>("/api/v1/benchmarks");
}

export function seedDemo() {
  return getJson<Record<string, unknown>>("/api/v1/demo/seed", { method: "POST" });
}

export function clearSession() {
  return getJson<Record<string, unknown>>("/api/v1/session/clear", { method: "POST" });
}

export function fetchHealth() {
  return getJson<{ status: string; session_mode: string }>("/api/v1/health");
}
