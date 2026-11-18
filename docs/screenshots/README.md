# Dashboard screenshots

Captured with `npm run screenshots` (Playwright, `apps/dashboard/scripts/screenshots.mjs`)
against a running API and dashboard after **Seed demo session**. All data is real
output of the SecurityGateway, provenance registry and audit store on synthetic
scenarios (demo email exfiltration plus held-out and challenge benchmark scenarios).

| File | Page |
| --- | --- |
| `01-overview.png` | Console overview: KPIs, decision timeline, risk gauges, destination map, risk tiers, top policies, recent decisions |
| `02-provenance-trace.png` | Provenance trace explorer: sessions/traces sidebar, layered DAG, flows-by-source popover, legend, zoom, timeline |
| `03-provenance-selected-action.png` | Same, with a gateway decision node selected (inspector) |
| `04-provenance-all-traces.png` | All seeded traces in one DAG |
| `05-audit.png` | Decision and audit table with filters and detail panel |
| `06-confirmations-locked.png` | Human approval screen before the approver token is entered |
| `07-confirmations-queue.png` | Pending CONFIRM queue (approver unlocked) |
| `08-confirmations-approved.png` | After approving one confirmation |
| `09-reconstruction.png` | Reconstruction evidence |
| `10-gateway.png` | Gateway decisions |
| `11-benchmarks.png` | Benchmark lab |

![Overview](01-overview.png)
![Provenance trace](02-provenance-trace.png)
![Confirmations](07-confirmations-queue.png)
