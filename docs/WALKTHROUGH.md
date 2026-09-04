# WatchTower walkthrough — every control, and what it means

This explains the dashboard element by element: what each thing is, what the numbers mean, what
happens when you click, and why it is designed that way. Nothing here needs an account.

**Live app:** <https://watchtower-283557821298.us-central1.run.app>

The service scales to zero, so the first request after an idle period takes roughly 30 seconds while
readiness reports `503`. That is the designed startup contract, not a fault.

---

## 1. The top bar

| Control | What it is |
|---|---|
| **● Operational** | Live health. Green means the app reached ClickHouse and the last refresh succeeded. If it reads **Telemetry unavailable**, the datastore is waking or unreachable — wait and it recovers. |
| **⌘** | The key panel. State-changing controls need a key; reading never does. |
| **＋ Simulate incident** | Arms a synthetic fault so you can watch the whole loop end to end. |

### The key panel (⌘)

Two different credentials exist, on purpose.

- **Operator key** — held only by the deployment owner, stored in Google Secret Manager, never in the
  repository. Unlimited.
- **Review key** — published so anyone evaluating the project can run the full loop:
  `watchtower-judge-demo`. Open *Reviewing this project? Get the review key* and press **Fill it in**.

The key is stored in `sessionStorage` — your browser tab only. It is sent to this deployment and
nowhere else, and it disappears when you close the tab.

The review key reaches exactly four endpoints (arm, advance, approve, dismiss). It cannot read or
delete anything: the database identity behind it holds `SELECT, INSERT` only. Starting an
investigation is protected by short-window and per-instance 24-hour limits to reduce model-cost
exposure; **recording a decision is never limited**, because finishing the loop is the point.

---

## 2. The hero and the agent pipeline

The right-hand rail is the four-stage workflow, and it is **live** — not a diagram.

| Stage | What it does |
|---|---|
| **01 Detector** | Confirms the signal is real by comparing a five-minute live window against the preceding sixty-minute baseline. Deterministic Python, not a model. |
| **02 Root-Cause** | Queries CDN-node and regional evidence through the official read-only ClickHouse MCP server, then ranks the likely cause. |
| **03 Impact Estimator** | Converts the fault into affected sessions, lost viewer-hours, and dollars. The arithmetic is auditable code; the model only explains it. |
| **04 Action Drafter** | Writes one specific, reversible action. **It holds no execution tool** — there is no function anywhere in the codebase that could act on it. |
| **◆ Human approval required** | The pipeline stops here, always. |

**Reading the rail while it runs.** The label changes from `Event-gated` to a pulsing
`● Investigating`, and a line names what is happening — for example
*Violet Engine · Latin America — Querying CDN and regional evidence through MCP…*. Completed stages
show **DONE** in cyan; the current one shows **RUNNING** in amber. A full run takes roughly 20–30
seconds because four real Gemini calls happen.

**Event-gated matters.** Gemini is not called on every tick. Deterministic rules decide whether a
material anomaly exists; only then do the agents run. That keeps reasoning cheap, auditable, and
honest — the model never invents an incident.

---

## 3. The metric strip

| Metric | Meaning |
|---|---|
| **LIVE VIEWS · 5M** | Views in the last five minutes across all twelve titles and five regions. Underneath: how many telemetry rows are retained. |
| **PLAYBACK STARTS** | Play presses in the same window. Starts always exceed views — some starts never become a watched view, which is exactly the failure WatchTower looks for. |
| **BUFFER RATE** | Buffering events divided by starts. Healthy sits near 2%. Detection fires above 8% *and* at least 2.5× baseline. |
| **AD IMPRESSIONS** | Ads delivered against the fictional catalog. |

---

## 4. Live signal and guardrails

**Audience activity** plots views per minute for the last thirty minutes, with *Updated Ns ago*
proving the feed is live. Timestamps are marked UTC by the API, so the reading is correct in every
timezone.

**Guardrails** is the trust panel, and every row is a real constraint:

| Row | Meaning |
|---|---|
| Data plane · **ClickHouse** | All analytics run in ClickHouse Cloud. Nothing is computed from memory. |
| Agent access · **Read-only MCP** | Agents reach data only through the official `mcp-clickhouse` server, over stdio, never exposed to the network. |
| AI provider · **Vertex AI** | Gemini 2.5 Flash through Vertex AI. No non-Google AI SDK exists in the runtime; a passing test enforces it. |
| Action policy · **Human only** | No autonomous execution exists. |

---

## 5. The incident queue — "Decisions, not alerts"

The counter on the right shows how many incidents await review.

Each card reads: **signal type · region**, the **title**, the **CDN node** and how long ago it was
detected, then **estimated impact** and **viewer-hours**, and a status pill:

- **PENDING APPROVAL** (amber) — waiting for a human.
- **APPROVED** (green) — a person accepted the recommendation. *The decision was recorded; nothing
  was executed.*
- **DISMISSED** — a person rejected it.

Press **Review →** to open the full incident:

- **Viewer-hours, affected sessions, estimated revenue** — the audited numbers.
- **Executive brief** — written by Gemini from the evidence, including the observed rate, the
  baseline, the deviation percentage and the confidence.
- **Agent trace** — all four stages with real durations, so you can see where the time went.
- **Pending human decision** — the drafted action, and the two buttons.

---

## 6. Simulating an incident

Press **＋ Simulate incident**.

| Field | What to choose |
|---|---|
| **Fictional title** | Any of the twelve original titles. All are invented; none are real media. |
| **Region** | North America, Europe, MENA, South Asia, Latin America. Each has its own CDN nodes and its own time-of-day traffic curve. |
| **Signal** | **Buffer spike** — degraded CDN delivery. **View drop** — regional playback collapse. **Ad failure** — delivery error surge. |

Press **Arm simulation**. The anomaly is written across the live detection window, so the next pass
detects it immediately rather than averaging it away, and all three signal types behave the same.
Watch the rail; roughly 20–30 seconds later a new incident appears in the queue.

Everything is synthetic. No real platform, CDN, or media catalog is touched at any point.

---

## 7. Approving or dismissing

Open an incident and choose. **Approve** records that a human accepted the recommendation.
**Dismiss** records that a human rejected it. Both are versioned and persisted in ClickHouse with a
note.

This is the part worth being precise about: **approval is a record, not an execution.** WatchTower
never calls a CDN, an ad platform, or a playback system. The Action Drafter has no tool with which
to do so, and a test asserts that no such function exists anywhere in the runtime. The job ends at
giving a person everything they need to decide quickly.

---

## 8. The monitored catalog

Twelve original titles with code-native gradient covers. There is no third-party media data, poster
art, studio asset, or external image request anywhere in the product — every cover is generated from
two colours in code.

---

## 9. If something looks wrong

| Symptom | What it means |
|---|---|
| Page is slow on the first load | Cold start from zero instances. Roughly 30 seconds, once. |
| **Telemetry unavailable** | ClickHouse Cloud is waking. It recovers on its own; refresh after a moment. |
| A control says a key is required | Open **⌘** and paste the review key. |
| `429` when arming | The shared key reached a short-window or per-instance 24-hour limit. Recording a decision still works. Run locally with `docker compose` for unrestricted local testing. |
| Arming produced no incident | Rare. Arm once more; detection needs the window to clear its threshold. |

See [TESTING.md](TESTING.md) to verify any of this yourself, including from the command line.
