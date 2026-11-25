"use client";

import { useEffect, useRef, useState } from "react";

/** Copies a single shell command. The label resets after a short confirmation. */
export function CopyCommand({ text }: { text: string }) {
  const [label, setLabel] = useState("Copy");
  const timer = useRef<number | null>(null);

  useEffect(() => {
    return () => {
      if (timer.current !== null) window.clearTimeout(timer.current);
    };
  }, []);

  async function onCopy() {
    try {
      await navigator.clipboard.writeText(text);
      setLabel("Copied");
    } catch {
      setLabel("Copy failed");
    }
    if (timer.current !== null) window.clearTimeout(timer.current);
    timer.current = window.setTimeout(() => setLabel("Copy"), 2000);
  }

  return (
    <button
      type="button"
      className="btn secondary copy-btn"
      onClick={() => void onCopy()}
      aria-live="polite"
    >
      {label}
    </button>
  );
}
