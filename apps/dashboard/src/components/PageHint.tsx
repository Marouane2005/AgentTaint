"use client";

import { useEffect, useState, type ReactNode } from "react";

/** Short "how to read this page" note. Visitors can hide it; the choice is remembered. */
export function PageHint({
  id,
  title,
  children,
}: {
  id: string;
  title: string;
  children: ReactNode;
}) {
  const key = `agenttaint.hint.${id}`;
  const [hidden, setHidden] = useState(false);
  useEffect(() => {
    try {
      setHidden(window.localStorage.getItem(key) === "hidden");
    } catch {
      /* storage unavailable: always show */
    }
  }, [key]);
  if (hidden) {
    return (
      <button
        type="button"
        className="hint-reopen"
        onClick={() => {
          setHidden(false);
          try {
            window.localStorage.removeItem(key);
          } catch {
            /* ignore */
          }
        }}
      >
        ? How to read this page
      </button>
    );
  }
  return (
    <aside className="page-hint" aria-label={`About this page: ${title}`}>
      <div className="page-hint-head">
        <strong>{title}</strong>
        <button
          type="button"
          aria-label="Hide this tip"
          onClick={() => {
            setHidden(true);
            try {
              window.localStorage.setItem(key, "hidden");
            } catch {
              /* ignore */
            }
          }}
        >
          Hide tip
        </button>
      </div>
      <div className="page-hint-body">{children}</div>
    </aside>
  );
}
