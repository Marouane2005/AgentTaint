import type { SessionInfo } from "@/lib/api";

export function SessionBanner({ session }: { session?: SessionInfo | null }) {
  if (!session) return null;
  const isDemo = session.mode === "demo_seed";
  const isEmpty = session.mode === "empty";
  return (
    <div className={`banner ${isDemo ? "warn" : ""} ${isEmpty ? "" : ""}`}>
      <strong>{isDemo ? "Simulated demo session" : "Session"}:</strong>{" "}
      {session.label}
      {session.notes && session.notes.length > 0 ? (
        <ul style={{ margin: "0.5rem 0 0", paddingLeft: "1.1rem" }}>
          {session.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}
