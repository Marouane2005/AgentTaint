import Link from "next/link";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";

export const metadata = { title: "AgentTaint · Limitations" };

const SECTIONS: { title: string; items: string[] }[] = [
  {
    title: "What the enforcement can and cannot see",
    items: [
      "AgentTaint filters tool calls. A model can still say harmful or false things in its reply; injection goals that need no tool call are out of scope.",
      "There is no perfect causal attribution inside a language model. Reconstruction estimates influence; it does not prove it, and its support levels are not calibrated probabilities. Links it adds are always marked INFERRED.",
      "Lineage depends on instrumentation. Uninstrumented steps yield PARTIAL or UNKNOWN lineage, which the policy treats with suspicion (more confirmations), not as safe.",
      "Declared lineage is asserted by the agent. An agent can declare the wrong parent; missing lineage is treated as UNKNOWN.",
      "Adaptive evasion works sometimes: heavy paraphrase, identifiers split across messages and novel encodings can produce false negatives.",
      "Cross-agent provenance is preserved only between AgentTaint-aware agents that pass authenticated envelopes.",
    ],
  },
  {
    title: "Deployment assumptions",
    items: [
      "The proxy, its databases and the policy files are trusted. If they are compromised, the guarantees are void.",
      "Run one proxy per agent identity: agents sharing one proxy process are indistinguishable in decisions.",
      "Only stdio MCP servers are proxied today. Remote (HTTP) servers, MCP resources and prompts are not.",
      "Cancellation is cooperative: a tool call already forwarded to the server may still complete.",
      "An approval binds the exact argument bytes. It does not prove the person understood the risk.",
      "Fail-closed defaults trade utility for safety: expect more CONFIRM prompts after an agent reads untrusted content.",
    ],
  },
  {
    title: "What the evaluation shows (and does not)",
    items: [
      "Most results come from a synthetic benchmark written for this project. Low attack success there does not transfer to production agents.",
      "The external benchmark run (AgentDojo) is a sampled subset with free-tier models. The model itself resisted most injections, so it says more about cost and compatibility than about protection. InjecAgent has not been evaluated.",
      "There is no fair head-to-head comparison with related systems (CaMeL, FIDES and others); we make no comparative claim.",
      "The semantic channel in CI uses a fixture embedder, not a calibrated production model.",
    ],
  },
  {
    title: "This public demo",
    items: [
      "Scenarios are synthetic and every tool is a mock: nothing is sent, executed or fetched.",
      "Approvals are locked and the session is shared between visitors and reset periodically.",
      "Requests are rate-limited. The demo runs on a free hosting tier and may take a minute to wake up.",
    ],
  },
];

export default function LimitationsPage() {
  return (
    <div className="site">
      <SiteHeader />
      <main className="doc">
        <p className="eyebrow">Read this before relying on AgentTaint</p>
        <h1>Limitations</h1>
        <p className="lead">
          AgentTaint reduces some risks of agents misusing tools. It is not a guarantee. This page
          summarizes the limitations list that ships with the product (docs/limitations.md).
        </p>
        {SECTIONS.map((s) => (
          <section key={s.title}>
            <h2>{s.title}</h2>
            <ul className="honest">
              {s.items.map((i) => (
                <li key={i}>{i}</li>
              ))}
            </ul>
          </section>
        ))}
        <p>
          <Link href="/product">← Back to the product page</Link>
        </p>
      </main>
      <SiteFooter />
    </div>
  );
}
