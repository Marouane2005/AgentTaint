import type { SessionInfo } from "@/lib/api";

export function SessionBanner({ session }: { session?: SessionInfo | null }) {
  if (!session) return null;
  const isDemo = session.mode === "demo_seed";
  const isEmpty = session.mode === "empty";
  const cls = isDemo ? "banner warn" : isEmpty ? "banner" : "banner ok";
  const title = isDemo
    ? "Simulated demo session"
    : isEmpty
      ? "No active session"
      : "Live session";
  return (
    <div className={cls} role="status">
      <strong>{title}</strong>
      <div style={{ marginTop: "0.35rem" }}>{session.label}</div>
      {session.notes && session.notes.length > 0 ? (
        <ul>
          {session.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
