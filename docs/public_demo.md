# Public demo and product site

The hosted demo is one Render web service (free plan, native Python runtime):
the FastAPI control plane runs with `AGENTTAINT_DEMO_MODE=1` and serves the
static dashboard build, which also contains the product site (`/product`,
`/limitations`, `/terms`, `/privacy`, `/refunds`) and the waitlist admin view
(`/admin/waitlist`). Blueprint for reference: `render.yaml`.

## What demo mode changes

| Area | Behaviour |
|------|-----------|
| Tools | Mock email only. No shell, filesystem, HTTP or Docker backends are wired. |
| Data | Synthetic scenarios replayed through the real gateway and Cedar policy; seeded at startup, reset when 200 traces accumulate. Shared between visitors. |
| `/api/v1/demo/run` | Runs one catalogued scenario twice: undefended (throwaway stores) and with AgentTaint (shared session). |
| Approvals | Every `/api/v1/confirmations*` request returns 403, whatever token is sent. `session/clear` returns 403. |
| Tokens | No operator token is configured or bundled. API auth is off for public reads. |
| Rate limits | Per client and global sliding windows: reads 240/min, scenario runs 12/min, seeding 2/min, waitlist 5/hour, admin 10/min. 429 with `Retry-After`. |
| `/` | Redirects to `/product/` (self-hosted installs redirect to `/overview/`). |

## Waitlist

In demo mode signups are refused (503) until `AGENTTAINT_SITE_DB_URL` is set,
because the free host's disk is ephemeral. `POST /api/v1/waitlist` stores the email (lower-cased, unique), source and
time in `AGENTTAINT_SITE_DB_URL`. Duplicates and honeypot hits get the same
answer as a new signup. `GET /api/v1/admin/waitlist[?format=csv]` needs
`X-AgentTaint-Admin: $AGENTTAINT_ADMIN_TOKEN` (24+ characters; the route
returns 503 without one). The `/admin/waitlist` page asks for that token and
keeps it in memory only.

## Payments (Paddle)

AgentTaint itself is free, open-source software under the Apache License 2.0.
The optional Hosted Support card uses Paddle.js overlay checkout for price
`pri_01m7r7zmmk1g29rp2y6t6px3mq` (optional hosted support, $15.00 USD/month). The
Paddle client-side token is read at build time from `PADDLE_CLIENT_TOKEN`
(Render: Environment, then redeploy so the static build picks it up). Overlay
checkout also requires `NEXT_PUBLIC_PADDLE_CHECKOUT_ENABLED=true` at build
time. While that flag is not exactly `true` — the default, including when it
is unset — the card does not open Paddle. The button is "Request hosted
support" and emails the support address with the subject "AgentTaint hosted
support". If Paddle.js fails to load, fails to initialise, or reports
`checkout.error`, the overlay is closed and that same email path is shown.
While the token itself is unset, the card shows the waitlist instead.
Client-side tokens are public by design; never put a Paddle API key in this
variable. The Render blueprint leaves the checkout flag unset.

## Free-plan caveats

* The web service sleeps after inactivity; the first request can take ~1 minute.
* Render's free Postgres expires 30 days after creation. Export the waitlist
  (`/admin/waitlist` → Export CSV) before then, and move to a paid or Neon
  database by setting `AGENTTAINT_SITE_DB_URL`.

## Free-text runs

`POST /api/v1/demo/custom` takes `{"instruction": "...", "content": "..."}`
(instruction up to 500 characters, content up to 2,000; rate limited to 8 runs per
minute per visitor). A deliberately obedient mock agent turns the text into at most
one mocked `email.send` call: it follows a send instruction wherever it reads one,
including inside the untrusted content. That proposed call then goes through the real
gateway, provenance registry and Cedar policy, and the response includes the
plain-English reason, the policy id and the span and call ids for the provenance graph.
Nothing is sent: every tool is a mock.

`DELETE /api/v1/admin/waitlist/{email}` (admin token) removes one signup.
