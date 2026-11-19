"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import {
  Activity,
  FlaskConical,
  LayoutDashboard,
  Radio,
  ScrollText,
  Search,
  Share2,
  ShieldCheck,
  Waypoints,
} from "lucide-react";
import { TokenGate } from "@/components/TokenGate";
import { useDemoMode } from "@/lib/useDemoMode";

const TABS = [
  { href: "/overview", label: "Overview", icon: LayoutDashboard },
  { href: "/activity", label: "Live activity", icon: Activity },
  { href: "/demo", label: "Run a scenario", icon: Waypoints },
  { href: "/provenance", label: "Provenance", icon: Share2 },
  { href: "/audit", label: "Audit", icon: ScrollText },
  { href: "/confirmations", label: "Confirmations", icon: ShieldCheck },
  { href: "/reconstruction", label: "Reconstruction", icon: Search },
  { href: "/gateway", label: "Gateway", icon: Radio },
  { href: "/benchmarks", label: "Benchmarks", icon: FlaskConical },
];

// Product site pages render without the console frame.
const SITE_PREFIXES = ["/product", "/limitations", "/admin", "/terms", "/privacy", "/refunds"];

export function Shell({ children }: { children: ReactNode }) {
  const pathname = usePathname() || "/";
  const demo = useDemoMode();
  const [menuOpen, setMenuOpen] = useState(false);
  useEffect(() => setMenuOpen(false), [pathname]);
  if (SITE_PREFIXES.some((p) => pathname.startsWith(p))) {
    return <>{children}</>;
  }
  return (
    <div className="app-frame">
      <header className={menuOpen ? "topnav menu-open" : "topnav"}>
        <Link href={demo ? "/product" : "/overview"} className="topnav-brand">
          <span className="brand-glyph" aria-hidden>
            AT
          </span>
          <strong>AgentTaint</strong>
        </Link>
        <button
          type="button"
          className="menu-toggle"
          aria-expanded={menuOpen}
          aria-controls="main-nav"
          onClick={() => setMenuOpen((v) => !v)}
        >
          <span aria-hidden>{menuOpen ? "✕" : "☰"}</span> Menu
        </button>
        <nav id="main-nav" aria-label="Main" className={menuOpen ? "open" : undefined}>
          {TABS.map((t) => {
            const active = pathname.startsWith(t.href);
            const Icon = t.icon;
            return (
              <Link
                key={t.href}
                href={t.href}
                className={active ? "active" : undefined}
                aria-current={active ? "page" : undefined}
              >
                <Icon size={15} aria-hidden /> {t.label}
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
