"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

const GROUPS = [
  {
    label: "Operations",
    links: [
      { href: "/", label: "Overview" },
      { href: "/provenance", label: "Provenance Explorer" },
      { href: "/reconstruction", label: "Reconstruction" },
      { href: "/gateway", label: "Security Gateway" },
    ],
  },
  {
    label: "Research",
    links: [{ href: "/benchmarks", label: "Benchmark Lab" }],
  },
];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">
            <span className="brand-glyph" aria-hidden>
              AT
            </span>
            <strong>AgentTaint</strong>
          </div>
          <span>Evidence-based information-flow security for AI agents &amp; MCP</span>
        </div>
        {GROUPS.map((group) => (
          <div className="nav-group" key={group.label}>
            <div className="nav-label">{group.label}</div>
            <nav className="nav" aria-label={group.label}>
              {group.links.map((link) => {
                const active =
                  link.href === "/"
                    ? pathname === "/"
                    : pathname.startsWith(link.href);
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={active ? "active" : undefined}
                    aria-current={active ? "page" : undefined}
                  >
                    {link.label}
                  </Link>
                );
              })}
            </nav>
          </div>
        ))}
        <div className="sidebar-foot">
          <div className="k">Local control plane</div>
          <div className="v">Read-only inspection · gateway not bypassed</div>
        </div>
      </aside>
      <main className="main">{children}</main>
    </div>
  );
}
