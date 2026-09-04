# Three-minute demo runbook

## Before recording

- Use a clean browser and the deployed Cloud Run URL.
- Wait until the status says **Operational** and the live signal shows a recent update.
- Open the top-right **demo access settings** button (`⌘`), paste the operator key, and select
  **Save locally**. The key stays in session storage and must never appear in the recording.
- Confirm the queue shows **0 awaiting review**. Resolved verification incidents may remain visible;
  do not describe the complete history as an empty queue.
- Do not show cloud consoles, secret values, browser bookmarks, or unrelated brands.
- Perform one unrecorded rehearsal. A cold ClickHouse/Cloud Run start and four sequential Gemini
  stages can add latency, so begin recording only after the dashboard is warm.

## Script

**0:00–0:20 — Problem**

“Streaming operators lose viewer-hours and revenue while raw dashboards wait for someone to notice.
WatchTower continuously turns delivery telemetry into an evidence-led incident and a safe next step.”

**0:20–0:40 — Normal operation**

Show live views, starts, buffer rate, audience chart, and **0 awaiting review**. Resolved history is
acceptable. Point out the four-agent rail and that Gemini is event-gated rather than called on every
polling cycle.

**0:40–1:00 — Controlled failure**

Choose **Aurora Drift → MENA → Buffer spike** and click **Arm simulation**. State that the title,
cover, telemetry, and anomaly are intentionally fictional and self-generated. The dashboard submits
three controlled telemetry ticks; while the agents run, narrate the evidence pipeline instead of
waiting silently.

**1:00–1:45 — Agent investigation**

Open the new incident. Show:

- the observed signal and rolling-baseline deviation;
- root-cause attribution to the affected CDN node;
- lost viewer-hours, sessions, and USD impact; and
- the Detector → Root-Cause → Impact → Action trace.

Say: “Both analytics steps use the official mcp-clickhouse server with a database-enforced
read-only identity. Gemini never invents the dollar amount.”

**1:45–2:25 — Human gate**

Read the reversible recommendation. Click **Approve recommendation**. Emphasize: “Approval records
the operator's decision. WatchTower intentionally has no tool capable of executing a CDN change.”

Do not trigger a second anomaly in the primary take. If the first run completes unusually early,
use the remaining time to show the methodology and security guardrails rather than risking another
model round trip.

**2:25–3:00 — Technical close**

Show the live URL and repository briefly. Close with: “Google ADK coordinates four Gemini agents;
ClickHouse supplies live operational truth through its official MCP server; and deterministic
guardrails keep the system explainable, affordable, and human-governed.”

## Accuracy notes

- **Approve recommendation** records a decision only; it does not execute a CDN or platform change.
- The estimated USD value comes from deterministic application math. Gemini explains it but cannot
  alter it.
- Detector and root-cause evidence is read through official `mcp-clickhouse` using the database's
  `SELECT`-only identity.
- If the UI says **Telemetry unavailable**, stop the take. Do not present a cold or failed backend as
  operational.
