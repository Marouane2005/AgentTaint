"use client";

import { useEffect, useState } from "react";
import { FileInput, GitBranch, Gavel, Send, ShieldCheck } from "lucide-react";
import type { DemoRunResult } from "@/lib/api";

const STEPS = [
  { id: "input", label: "Input received", icon: FileInput },
  { id: "provenance", label: "Provenance tracked", icon: GitBranch },
  { id: "call", label: "Call proposed", icon: Send },
  { id: "policy", label: "Policy evaluated", icon: Gavel },
  { id: "verdict", label: "Verdict", icon: ShieldCheck },
] as const;

const STEP_MS = 380;

function motionReduced(): boolean {
  if (typeof window === "undefined" || typeof window.matchMedia !== "function") return true;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** Advances only after a gateway response exists. Reduced motion jumps to the verdict. */
export function useDecisionStep(result: DemoRunResult | null): number {
  const [step, setStep] = useState(-1);
  useEffect(() => {
    if (!result) {
      setStep(-1);
      return;
    }
    if (motionReduced()) {
      setStep(STEPS.length - 1);
      return;
    }
    setStep(0);
    const timers = STEPS.map((_, index) => window.setTimeout(() => setStep(index), index * STEP_MS));
    return () => {
      for (const timer of timers) window.clearTimeout(timer);
    };
  }, [result]);
  return step;
}

export function DecisionSequence({
  result,
  step,
}: {
  result: DemoRunResult;
  step: number;
}) {
  const verdict = result.with_agenttaint.decision;
  return (
    <ol className="decision-seq" aria-label="Decision sequence">
      {STEPS.map((item, index) => {
        const Icon = item.icon;
        const on = index <= step;
        return (
          <li key={item.id} className={on ? "on" : undefined} aria-current={index === step ? "step" : undefined}>
            <Icon size={15} aria-hidden />
            <span>{item.label}</span>
            {item.id === "verdict" && on ? (
              <b className={`dec ${verdict}`}>{verdict}</b>
            ) : null}
          </li>
        );
      })}
    </ol>
  );
}

export function verdictVisible(step: number): boolean {
  return step >= STEPS.length - 1;
}

export function graphVisible(step: number): boolean {
  return step >= 1;
}
