"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";
import { TokenGate } from "@/components/TokenGate";
import { useDemoMode } from "@/lib/useDemoMode";

const TABS = [
  { href: "/overview", label: "Overview" },
  { href: "/demo", label: "Run a scenario" },
  { href: "/provenance", label: "Provenance" },
  { href: "/audit", label: "Audit" },
  { href: "/confirmations", label: "Confirmations" },
  { href: "/reconstruction", label: "Reconstruction" },
  { href: "/gateway", label: "Gateway" },
  { href: "/benchmarks", label: "Benchmarks" },
];

// Product site pages render without the console frame.
const SITE_PREFIXES = ["/product", "/limitations", "/admin", "/terms", "/privacy", "/refunds"];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  const demo = useDemoMode();
  if (SITE_PREFIXES.some((p) => pathname.startsWith(p))) {
    return <>{children}</>;
  }
  return (
    <div className="app-frame">
      <header className="topnav">
        <Link href={demo ? "/product" : "/overview"} className="topnav-brand">
          <span className="brand-glyph" aria-hidden>
            AT
          </span>
          <strong>AgentTaint</strong>
        </Link>
        <nav aria-label="Main">
          {TABS.map((t) => {
            const active = pathname.startsWith(t.href);
            return (
              <Link
                key={t.href}
                href={t.href}
                className={active ? "active" : undefined}
                aria-current={active ? "page" : undefined}
              >
                {t.label}
              </Link>
            );
          })}
        </nav>
        {demo ? (
          <span className="research-chip" title="Mock tools and synthetic scenarios only">
            Public demo · synthetic data · approvals locked
          </span>
        ) : (
          <span className="research-chip" title="Synthetic + adversarial evidence only">
            AgentTaint 1.0
          </span>
        )}
      </header>
      <main className={pathname.startsWith("/provenance") ? "frame-main full" : "frame-main"}>
        <TokenGate />
        {children}
      </main>
    </div>
  );
}
