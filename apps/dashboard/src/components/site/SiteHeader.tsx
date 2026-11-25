import Link from "next/link";
import { SELLER, SUPPORT_EMAIL } from "@/lib/site";

export function SiteHeader() {
  return (
    <header className="site-header">
      <Link href="/product" className="site-brand">
        <span className="brand-glyph" aria-hidden>
          AT
        </span>
        <strong>AgentTaint</strong>
      </Link>
      <nav aria-label="Site">
        <Link href="/product#how">How it works</Link>
        <Link href="/product#pricing">Open source &amp; support</Link>
        <Link href="/limitations">Limitations</Link>
        <Link href="/demo" className="site-cta">
          Live demo
        </Link>
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="site-footer">
      <span>
        © 2026 AgentTaint · {SELLER} · Contact:{" "}
        <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
      </span>
      <span>
        <Link href="/product#pricing">Open source &amp; support</Link> · <Link href="/limitations">Limitations</Link>{" "}
        · <Link href="/terms">Terms of Service</Link> · <Link href="/privacy">Privacy Policy</Link>{" "}
        · <Link href="/refunds">Refund Policy</Link>
      </span>
    </footer>
  );
}
