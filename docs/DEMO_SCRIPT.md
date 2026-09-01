# Three-minute demo runbook

## Before recording

- Use a clean browser and the deployed Cloud Run URL.
- Confirm the status says operational and ClickHouse has a live timestamp.
- Save the operator key through the `⌘` control.
- Keep one pending-free incident queue and normal telemetry on screen.
- Do not show cloud consoles, secret values, browser bookmarks, or unrelated brands.

## Script

**0:00–0:20 — Problem**

“Streaming operators lose viewer-hours and revenue while raw dashboards wait for someone to notice.
WatchTower continuously turns delivery telemetry into an evidence-led incident and a safe next step.”

**0:20–0:40 — Normal operation**

Show live views, starts, buffer rate, audience chart, and the empty incident queue. Point out the
four-agent rail and that Gemini is event-gated rather than called on every polling cycle.

**0:40–1:00 — Controlled failure**

Choose **Aurora Drift → MENA → Buffer spike** and click **Arm simulation**. State that the title,
cover, telemetry, and anomaly are intentionally fictional and self-generated.

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

Trigger a second anomaly if time permits and dismiss it to show both decision paths.

**2:25–3:00 — Technical close**

Show the live URL and repository briefly. Close with: “Google ADK coordinates four Gemini agents;
ClickHouse supplies live operational truth through its official MCP server; and deterministic
guardrails keep the system explainable, affordable, and human-governed.”
