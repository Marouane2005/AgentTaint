import type { Metadata } from "next";
import { Shell } from "@/components/Shell";
import "./globals.css";
import "./console.css";

export const metadata: Metadata = {
  title: "AgentTaint Security Dashboard",
  description:
    "Interactive security console for AgentTaint provenance, gateway decisions, and synthetic benchmarks.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
