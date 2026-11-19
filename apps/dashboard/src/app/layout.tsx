import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { Shell } from "@/components/Shell";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  display: "swap",
  variable: "--font-inter",
});
import "./console.css";
import "./site.css";
import "./responsive.css";
import "./try.css";

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
      <body className={inter.className}>
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
