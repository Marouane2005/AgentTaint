"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const LINKS = [
  { href: "/", label: "Overview" },
  { href: "/provenance", label: "Provenance Explorer" },
  { href: "/reconstruction", label: "Reconstruction" },
  { href: "/gateway", label: "Security Gateway" },
  { href: "/benchmarks", label: "Benchmark Lab" },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <strong>AgentTaint</strong>
          <span>Information-flow security for AI agents &amp; MCP</span>
        </div>
        <nav className="nav" aria-label="Primary">
          {LINKS.map((link) => {
            const active =
              link.href === "/"
                ? pathname === "/"
                : pathname.startsWith(link.href);
            return (
              <Link
                key={link.href}
                href={link.href}
                className={active ? "active" : undefined}
              >
                {link.label}
              </Link>
            );
          })}
        </nav>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
