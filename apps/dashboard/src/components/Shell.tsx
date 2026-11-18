"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const TABS = [
  { href: "/", label: "Overview" },
  { href: "/provenance", label: "Provenance" },
  { href: "/audit", label: "Audit" },
  { href: "/confirmations", label: "Confirmations" },
  { href: "/reconstruction", label: "Reconstruction" },
  { href: "/gateway", label: "Gateway" },
  { href: "/benchmarks", label: "Benchmarks" },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-frame">
      <header className="topnav">
        <Link href="/" className="topnav-brand">
          <span className="brand-glyph" aria-hidden>
            AT
          </span>
          <strong>AgentTaint</strong>
        </Link>
        <nav aria-label="Main">
          {TABS.map((t) => {
            const active = t.href === "/" ? pathname === "/" : pathname.startsWith(t.href);
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
        <span className="research-chip" title="Synthetic + adversarial evidence only">
          Research demo · not production ASR
        </span>
      </header>
      <main className={pathname.startsWith("/provenance") ? "frame-main full" : "frame-main"}>
        {children}
      </main>
    </div>
  );
}
