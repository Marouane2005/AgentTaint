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

The Pro card uses Paddle.js overlay checkout for price
`pri_01m7r7zmmk1g29rp2y6t6px3mq` (AgentTaint Pro, $15.00 USD/month). The
Paddle client-side token is read at build time from `PADDLE_CLIENT_TOKEN`
(Render: Environment, then redeploy so the static build picks it up). While it
is unset the card shows the waitlist instead. Client-side tokens are public by
design; never put a Paddle API key in this variable.

Delivering the release bundle to new subscribers is manual for now (send the
`agenttaint-1.0.0.tar.gz` download link after Paddle's purchase notification).

## Free-plan caveats

* The web service sleeps after inactivity; the first request can take ~1 minute.
* Render's free Postgres expires 30 days after creation. Export the waitlist
  (`/admin/waitlist` → Export CSV) before then, and move to a paid or Neon
  database by setting `AGENTTAINT_SITE_DB_URL`.
