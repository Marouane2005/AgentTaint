import Link from "next/link";
import type { ReactNode } from "react";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";

export function LegalPage({
  title,
  updated,
  children,
}: {
  title: string;
  updated: string;
  children: ReactNode;
}) {
  return (
    <div className="site">
      <SiteHeader />
      <main className="doc legal">
        <h1>{title}</h1>
        <p className="fine">Last updated: {updated}</p>
        {children}
        <p>
          <Link href="/product">← Back to the product page</Link>
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}
