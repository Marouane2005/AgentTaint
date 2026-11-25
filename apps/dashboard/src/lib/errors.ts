/** Turn a thrown fetch/API error into a message a first-time visitor can act on. */
export function friendlyError(err: unknown): string {
  const raw = err instanceof Error ? err.message : String(err);
  const status = /^(\d{3}) /.exec(raw)?.[1];
  if (status === "401" || status === "403") {
    return `${status}: the token was rejected. Check it matches the one in your .env and try again.`;
  }
  if (status === "404") {
    return `404: this API route does not exist. The dashboard and API may be different versions.`;
  }
  if (status && status.startsWith("5")) {
    return `${status}: the AgentTaint API hit an error. Check its logs, then retry.`;
  }
  if (/failed to fetch|networkerror|load failed|fetch failed/i.test(raw)) {
    return "Cannot reach the AgentTaint API. Start it with `agenttaint dashboard` (or `make api`) and retry.";
  }
  return raw;
}
