export type SessionInfo = {
  mode: string;
  label: string;
  seeded_at?: string | null;
  notes?: string[];
};

const TOKEN_KEY = "agenttaint.dashboardToken";

/** Dashboard read token typed by the operator; kept for this browser tab only. */
export function getSessionToken(): string {
  try {
    return typeof window === "undefined" ? "" : window.sessionStorage.getItem(TOKEN_KEY) || "";
  } catch {
    return "";
  }
}

export function setSessionToken(value: string) {
  try {
    if (value) window.sessionStorage.setItem(TOKEN_KEY, value);
    else window.sessionStorage.removeItem(TOKEN_KEY);
  } catch {
    /* storage unavailable: token stays unset */
  }
}

export class UnauthorizedError extends Error {}

function authHeaders(): HeadersInit {
  // Self-hosted deployments run with AGENTTAINT_API_AUTH=required: the operator
  // types the dashboard token once per tab (never bundled into the build).
  const typed = getSessionToken();
  if (typed) return { "X-AgentTaint-Token": typed };
  // Legacy local-dev option for a build-time token.
  if (typeof process !== "undefined" && process.env.NEXT_PUBLIC_AGENTTAINT_TOKEN) {
    return { "X-AgentTaint-Token": process.env.NEXT_PUBLIC_AGENTTAINT_TOKEN };
  }
  return {};
}

async function getJson<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    ...init,
    headers: {
      Accept: "application/json",
      ...authHeaders(),
      ...(init?.headers || {}),
    },
    cache: "no-store",
  });
  if (!res.ok) {
    const text = await res.text();
    if (res.status === 401) throw new UnauthorizedError(`401 ${path}: ${text}`);
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

export type DecisionQuery = {
  limit?: number;
  offset?: number;
  decision?: string;
  risk_tier?: string;
  tool?: string;
  q?: string;
  sort?: "created_at" | "tool" | "decision" | "risk_tier";
  order?: "asc" | "desc";
};

export function fetchDecisions(query: DecisionQuery = {}) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const qs = params.toString();
  return getJson<{
    session: SessionInfo;
    items: Array<Record<string, unknown>>;
    total?: number;
    offset?: number;
    limit?: number;
  }>(qs ? `/api/v1/decisions?${qs}` : "/api/v1/decisions");
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

export type BenchmarkScenario = {
  scenario_id: string;
  kind: string;
  family: string;
  split: string;
  description: string;
  difficulty: string;
};

export function fetchBenchmarks() {
  return getJson<{
    available: boolean;
    disclaimer: string;
    reports: Array<Record<string, unknown>>;
    message: string | null;
    scenarios?: {
      available: boolean;
      counts: Record<string, number>;
      catalog: BenchmarkScenario[];
      catalog_count: number;
      message?: string | null;
      note?: string;
    };
  }>("/api/v1/benchmarks");
}

export function seedDemo() {
  return getJson<Record<string, unknown>>("/api/v1/demo/seed", { method: "POST" });
}

export function clearSession() {
  return getJson<Record<string, unknown>>("/api/v1/session/clear", { method: "POST" });
}

export function fetchHealth() {
  return getJson<{
    status: string;
    session_mode: string;
    registry_ok?: boolean;
    audit_ok?: boolean;
    policy_ok?: boolean;
    demo_mode?: boolean;
    auth_mode?: string;
  }>("/api/v1/health");
}

export function fetchAncestors(spanId: string) {
  return getJson<{
    span_id: string;
    ancestors: Array<Record<string, unknown>>;
  }>(`/api/v1/spans/${encodeURIComponent(spanId)}/ancestors`);
}

export type Decision = {
  call_id: string;
  agent_id?: string | null;
  tool: string;
  risk_tier: string;
  arguments_redacted?: Record<string, unknown>;
  arguments_hash?: string;
  evidence?: Array<Record<string, unknown>>;
  provenance_status?: string;
  decision: "ALLOW" | "BLOCK" | "CONFIRM" | string;
  policy_id?: string | null;
  confirmation_id?: string | null;
  created_at: string;
  latency_ms?: number | null;
  explanation?: string;
};

export type TraceCall = { call_ids: string[]; span_ids: string[] };

export type Trace = {
  trace_id: string;
  label: string;
  kind: string;
  family: string;
  source: string;
  decision?: string;
  span_ids: string[];
  call_ids: string[];
  calls?: TraceCall[];
};

export function fetchTraces() {
  return getJson<{ session: SessionInfo; traces: Trace[] }>("/api/v1/traces");
}

export function fetchAllDecisions() {
  return getJson<{ session: SessionInfo; items: Decision[] }>(
    "/api/v1/decisions?limit=500",
  );
}

export type PendingConfirmation = {
  confirmation_id: string;
  tool: string;
  agent_id: string;
  risk_tier: string;
  policy_id?: string | null;
  arguments_redacted?: Record<string, unknown>;
  arguments_hash: string;
  explanation: string;
  status: string;
  expires_at: string;
  /** Present only in the response to an approve call; shown to the approver once. */
  approval_token?: string;
};

/**
 * Human approval channel. The approver token is typed by a person into the
 * approval screen and kept in component memory only: it is never read from
 * NEXT_PUBLIC_* env vars, stored, or bundled.
 */
function approverHeaders(approverToken: string): HeadersInit {
  return { "X-AgentTaint-Approver": approverToken };
}

export function fetchConfirmations(approverToken: string) {
  return getJson<{ pending: PendingConfirmation[] }>("/api/v1/confirmations", {
    headers: approverHeaders(approverToken),
  });
}

export function decideConfirmation(
  approverToken: string,
  confirmationId: string,
  action: "approve" | "deny",
) {
  return getJson<PendingConfirmation>(
    `/api/v1/confirmations/${encodeURIComponent(confirmationId)}/${action}`,
    { method: "POST", headers: approverHeaders(approverToken) },
  );
}

// --- Public demo and product site ------------------------------------------------

export type DemoScenario = {
  scenario_id: string;
  kind: "attack" | "benign";
  family: string;
  split: string;
  description: string;
  difficulty: string;
  send_to?: string | null;
};

export type DemoRunResult = {
  scenario: Omit<DemoScenario, "kind"> & { kind: string };
  trace_id: string;
  call_ids: string[];
  span_ids?: string[];
  agent_call?: { tool: string; arguments: Record<string, string> } | null;
  agent_reason?: string;
  graph?: {
    nodes: Array<Record<string, unknown>>;
    edges: Array<Record<string, unknown>>;
    decisions: Decision[];
  };
  without_agenttaint: {
    decision: string;
    attack_success?: boolean | null;
    benign_completed?: boolean | null;
  };
  with_agenttaint: {
    decision: string;
    policy_id?: string | null;
    attack_success?: boolean | null;
    benign_completed?: boolean | null;
    evidence_statuses: string[];
    latency_ms: number;
    explanation?: string;
  };
};

export function fetchDemoScenarios() {
  return getJson<{ demo_mode: boolean; scenarios: DemoScenario[] }>("/api/v1/demo/scenarios");
}

export function runDemoScenario(scenarioId: string) {
  return getJson<DemoRunResult>("/api/v1/demo/run", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ scenario_id: scenarioId }),
  });
}

export function runDemoCustom(instruction: string, content: string) {
  return getJson<DemoRunResult>("/api/v1/demo/custom", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ instruction, content }),
  });
}

export async function joinWaitlist(email: string, website: string, source = "landing") {
  const res = await fetch("/api/v1/waitlist", {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "application/json" },
    body: JSON.stringify({ email, website, source }),
  });
  const data = (await res.json().catch(() => ({}))) as { message?: string; detail?: unknown };
  if (!res.ok) {
    const detail = typeof data.detail === "string" ? data.detail : "Please enter a valid email.";
    // FastAPI validation errors arrive as a list; keep the message human.
    throw new Error(res.status === 429 ? "Too many attempts. Try again later." : detail);
  }
  return data.message || "Thanks, you're on the list.";
}

export type WaitlistEntry = { email: string; plan: string; source: string; created_at: string };

/** Admin token is typed by the operator and kept in component memory only. */
export function fetchWaitlist(adminToken: string) {
  return getJson<{ count: number; entries: WaitlistEntry[] }>("/api/v1/admin/waitlist", {
    headers: { "X-AgentTaint-Admin": adminToken },
  });
}

export async function downloadWaitlistCsv(adminToken: string) {
  const res = await fetch("/api/v1/admin/waitlist?format=csv", {
    headers: { "X-AgentTaint-Admin": adminToken },
  });
  if (!res.ok) throw new Error(`${res.status}: could not export`);
  return res.text();
}
