import type { ReactNode } from "react";

type Props = {
  kind: "loading" | "empty" | "error";
  title?: string;
  children?: ReactNode;
  onRetry?: () => void;
};

/** One consistent loading / empty / error block for every data panel. */
export function StatePanel({ kind, title, children, onRetry }: Props) {
  if (kind === "loading") {
    return (
      <div className="loading" role="status">
        {title ?? "Loading…"}
      </div>
    );
  }
  const cls = kind === "error" ? "banner danger" : "empty";
  return (
    <div className={cls} role={kind === "error" ? "alert" : "status"}>
      {title ? <strong>{title}</strong> : null}
      {children ? <div>{children}</div> : null}
      {kind === "error" && onRetry ? (
        <button className="btn secondary" type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </div>
  );
}
