/* eslint-disable @next/next/no-img-element -- static export serves plain images */
import Link from "next/link";
import { SiteFooter, SiteHeader } from "@/components/site/SiteHeader";
import { WaitlistForm } from "@/components/site/WaitlistForm";
import { PaddleCheckout } from "@/components/site/PaddleCheckout";
import { CHECKOUT_URL, PADDLE_CLIENT_TOKEN, PRO_PRICE, SUPPORT_EMAIL } from "@/lib/site";

const FEATURES = [
  {
    title: "Tracks where arguments come from",
    body: "Every tool result becomes a labeled span (user, internal, untrusted tool output). Links between spans carry evidence: KNOWN, INFERRED, UNKNOWN or PARTIAL. Inferred links are never upgraded to known.",
  },
  {
    title: "Decides on every tool call",
    body: "A Cedar policy returns ALLOW, CONFIRM or BLOCK for each call from the tool's risk tier and the provenance of its arguments. If the provenance store is unreachable, high-risk calls fail closed.",
  },
  {
    title: "Asks a person, out of band",
    body: "CONFIRM holds the call. Approval happens in the dashboard or a terminal, never through the agent: it is bound to the exact arguments, works once and expires. The agent has no approve tool.",
  },
  {
    title: "Flags broken lineage",
    body: "When an uninstrumented step hides where a value came from, lexical, structural and optional semantic matching flag likely untrusted influence. It is a scrutiny signal, not proof, and it is labeled that way.",
  },
];

const STEPS = [
  ["Point your MCP client at the proxy", "Replace the server entry with `agenttaint proxy --config agenttaint.yaml`."],
  ["The proxy starts your MCP server", "It forwards tools/list, and labels every tool result with its origin."],
  ["Each call is evaluated", "ALLOW is forwarded. CONFIRM waits for a person. BLOCK is refused with the reason."],
  ["Review in the dashboard", "Provenance graph, audit log with policy ids and argument hashes, approval queue."],
];

const SCREENS = [
  ["/screens/01-overview.png", "Console overview: decisions over time, risk gauges, destinations."],
  ["/screens/03-provenance-selected-action.png", "Provenance graph for one trace, with the blocked send selected."],
  ["/screens/05-audit.png", "Audit log: every decision with its policy and explanation."],
  ["/screens/07-confirmations-queue.png", "Approval queue: held calls wait for a person (self-hosted Pro)."],
];

export const metadata = {
  title: "AgentTaint · Provenance firewall for MCP tool calls",
  description:
    "AgentTaint sits between your agent and its MCP servers and blocks or holds high-risk tool calls whose arguments trace back to untrusted content.",
};

export default function ProductPage() {
  return (
    <div className="site">
      <SiteHeader />
      <main>
        <section className="hero">
          <p className="eyebrow">Self-hosted · MCP stdio proxy · Cedar policies</p>
          <h1>
            A provenance firewall for <span className="accent">MCP tool calls</span>
          </h1>
          <p className="lead">
            AgentTaint sits between your agent and its MCP servers. It records where every tool
            argument came from, and blocks, or holds for a person, high-risk calls whose arguments
            trace back to untrusted content, such as a recipient address lifted from an inbound
            email.
          </p>
          <div className="hero-cta">
            <Link className="btn big" href="/demo">
              Try the live demo
            </Link>
            <Link className="btn big secondary" href="#pricing">
              Pricing
            </Link>
          </div>
          <p className="fine">
            The demo runs synthetic scenarios against mock tools. Nothing you do there sends
            anything anywhere.
          </p>
          <div className="hero-shot">
            <img src="/screens/03-provenance-selected-action.png" alt="AgentTaint provenance graph" />
          </div>
        </section>

        <section className="band">
          <h2>What it does</h2>
          <div className="feature-grid">
            {FEATURES.map((f) => (
              <article key={f.title} className="feature">
                <h3>{f.title}</h3>
                <p>{f.body}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="band" id="how">
          <h2>How it works</h2>
          <ol className="steps">
            {STEPS.map(([title, body], i) => (
              <li key={title}>
                <span className="step-n">{i + 1}</span>
                <div>
                  <h3>{title}</h3>
                  <p>{body}</p>
                </div>
              </li>
            ))}
          </ol>
          <pre className="code">{`{
  "mcpServers": {
    "files-protected": {
      "command": "agenttaint",
      "args": ["proxy", "--config", "/home/you/agenttaint/agenttaint.yaml"]
    }
  }
}`}</pre>
          <p className="fine">
            Works with MCP clients that launch stdio servers (desktop apps and IDE clients). The
            protected server keeps running unchanged behind the proxy.
          </p>
        </section>

        <section className="band">
          <h2>Screenshots</h2>
          <div className="shots">
            {SCREENS.map(([src, caption]) => (
              <figure key={src}>
                <img src={src} alt={caption} loading="lazy" />
                <figcaption>{caption}</figcaption>
              </figure>
            ))}
          </div>
        </section>

        <section className="band">
          <h2>What it does not do</h2>
          <ul className="honest">
            <li>
              It filters tool calls. It does not stop a model from <em>saying</em> something wrong
              in its reply.
            </li>
            <li>
              Reconstruction signals are heuristics. Heavy paraphrase or values split across
              messages can evade them.
            </li>
            <li>
              Results so far come from our synthetic benchmark and a sampled external benchmark run
              with one real model. They are not production attack-prevention rates.
            </li>
            <li>Remote (HTTP) MCP servers, MCP resources and prompts are not proxied yet.</li>
          </ul>
          <p>
            <Link href="/limitations">Read the full limitations →</Link>
          </p>
        </section>

        <section className="band" id="pricing">
          <h2>Pricing</h2>
          <div className="pricing">
            <article className="plan">
              <h3>Demo</h3>
              <p className="price">Free</p>
              <ul>
                <li>This hosted demo, open to everyone</li>
                <li>Synthetic attack and benign scenarios</li>
                <li>Real gateway and Cedar policy, mock tools only</li>
                <li>Provenance graph and audit log</li>
                <li>Approvals locked</li>
              </ul>
              <Link className="btn secondary" href="/demo">
                Open the demo
              </Link>
            </article>
            <article className="plan featured">
              <h3>Pro</h3>
              <p className="price">
                {PRO_PRICE}
                <span> USD/month</span>
              </p>
              <ul>
                <li>Self-hosted full version on your machines</li>
                <li>
                  <span className="mono">agenttaint</span> CLI: proxy, approvals, dashboard
                </li>
                <li>Docker Compose stack with Postgres</li>
                <li>Out-of-band approvals with a separate approver token</li>
                <li>Updates while subscribed</li>
                <li>Email support</li>
              </ul>
              {PADDLE_CLIENT_TOKEN ? (
                <PaddleCheckout />
              ) : CHECKOUT_URL ? (
                <a className="btn" href={CHECKOUT_URL} rel="noopener">
                  Subscribe · {PRO_PRICE} USD/month
                </a>
              ) : (
                <>
                  <p className="fine">Checkout is not open yet. Join the waitlist and we&apos;ll email you.</p>
                  <WaitlistForm source="pricing" />
                </>
              )}
              <p className="fine">
                Questions: <a href={`mailto:${SUPPORT_EMAIL}`}>{SUPPORT_EMAIL}</a>
              </p>
            </article>
          </div>
        </section>
      </main>
      <SiteFooter />
    </div>
  );
}
