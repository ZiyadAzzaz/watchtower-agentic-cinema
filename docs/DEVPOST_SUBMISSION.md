# WatchTower — paste-ready Devpost submission

The live application and source URLs are final. Replace only the demo-video URL. Everything else is ready to
paste.

## Project name

WatchTower

## Tagline / one-line description

Release-night intelligence for the people who ship a title: four Gemini agents watch delivery
telemetry in ClickHouse, find out who cannot watch your premiere and why, price the damage in lost
viewer-hours, and stop for a human to decide.

## Links

- Live application: <https://watchtower-283557821298.us-central1.run.app>
- Source code: <https://github.com/ZiyadAzzaz/watchtower-agentic-cinema>
- Demo video: `[PUBLIC_VIDEO_URL]`

## Testing instructions for judges

The dashboard is open to everyone — no sign-up, no account. To run the full decision loop yourself:

1. Open the live application. It scales to zero, so the first load takes about 30 seconds.
2. Click the **⌘** button in the top bar, expand *Reviewing this project?*, and press **Fill it in**.
   The shared review key is `watchtower-judge-demo`.
3. Press **＋ Simulate incident**, choose any fictional title, region and failure type, then
   **Arm simulation**.
4. Watch the agent rail: four Gemini agents investigate in real time, roughly 20–30 seconds.
5. Open the resulting incident and **approve** or **dismiss** it.

The review key is separate from the deployment's operator credential, which stays in Google Secret
Manager. It reaches four endpoints, the database identity behind it can only read and insert, and no
execution tool exists anywhere in the system — approving records a human decision and calls nothing
downstream. Starting an investigation is rate limited; recording a decision never is.

`docs/WALKTHROUGH.md` in the repository explains every control on the dashboard.

## Who it is for

The distribution and release-operations crew at a studio or streamer — the people on the launch
bridge the night a title goes live. They are the last link in the entertainment value chain, and the
only one measured in whether the audience actually got to watch. When a premiere lands badly in one
region, they are the team that has to know within minutes, not at the next-day post-mortem.

Their stakeholder is the fan. A buffering premiere is a fan who leaves.

## Inspiration

A film or series can be years in the making and still fail in its final ten minutes — the ten minutes
between a viewer pressing play and giving up. On release night the people responsible for that
moment are watching dashboards that go red without saying why, how many fans are affected, or what
it costs. A graph changing color is not yet a decision.

Everything upstream in this industry is deliberate: a director approves a cut, a colorist approves a
grade, a producer approves a budget. We wanted the last link in the chain to work the same way —
evidence assembled fast by machines, the decision still made by a person who is accountable for it.

Our design principle is **evidence first, agents second, human decision always**. Deterministic code
decides whether a material anomaly exists and calculates its impact. Gemini receives bounded,
read-only evidence and turns it into a concise investigation and reversible recommendation. The
workflow then stops for a person to approve or dismiss.

## What it does — features and functionality

WatchTower continuously generates original synthetic streaming telemetry for 12 fictional titles
across five regions and stores it in ClickHouse. The product:

- compares short live windows with rolling baselines;
- detects regional view collapses, buffering spikes, and ad-delivery failures;
- uses the official `mcp-clickhouse` server to retrieve bounded operational evidence;
- identifies the most likely affected CDN node and explains the evidence;
- calculates affected sessions, lost viewer-hours, estimated revenue impact, and severity;
- runs four specialized Google ADK agents: Detector, Root-Cause, Impact Estimator, and Action
  Drafter;
- displays a trace of all four agent stages in a responsive operations dashboard;
- creates every incident in `pending_approval` state; and
- lets a human approve or dismiss the recommendation without executing any downstream change.

The demo includes a controlled simulation panel. An operator can arm a fictional failure, watch the
same ClickHouse/MCP/agent path investigate it, inspect the quantified impact, and record a human
decision. No CDN, advertising platform, playback service, or external production system can be
changed by WatchTower.

## How we built it — technologies used

- **ClickHouse Cloud** stores live telemetry, the fictional catalog, and versioned incident state.
- **Official `mcp-clickhouse`** runs over container-local stdio for agent evidence queries.
- **Google Agent Development Kit 2.8** provides a real four-stage `SequentialAgent` workflow.
- **Gemini 2.5 Flash on Vertex AI** is the only runtime AI/model provider.
- **FastAPI and Uvicorn** serve the API, dashboard, health endpoints, and guarded controls.
- **Vanilla HTML, CSS, and JavaScript** provide the responsive dashboard without a frontend runtime
  dependency.
- **Google Cloud Run** hosts the cost-constrained service with zero minimum and one maximum
  instance.
- **Google Secret Manager** supplies the two database passwords and operator token.
- **Artifact Registry and Cloud Build** create and store the private container image.
- **Docker Compose** provides a reproducible local ClickHouse and application environment.
- **Pytest and Ruff** enforce behavior, policy, formatting, and integration quality.

Security is layered. The ingestion identity has only `SELECT` and `INSERT`; the separate MCP
identity has `SELECT` only. MCP write flags are disabled, and application middleware rejects
mutations, comments, multiple statements, unknown tables, and unbounded output. Production startup
is locked to the WatchTower Google Cloud project, verified ClickHouse TLS, Vertex AI, scoped
credentials, and a required operator token.

## Other data sources

WatchTower uses **no third-party movie database, media catalog, poster, studio asset, customer data,
or private streaming-platform data**. All 12 titles, names, descriptions, genres, cover gradients,
regional telemetry patterns, CDN labels, and injected anomaly signals were created specifically for
this project during the contest period.

The only operational data source is the application's own synthetic event stream stored in
ClickHouse. Demo business-impact constants—41 minutes per average session, $0.11 retention value per
viewer-hour, 3.2 ads per affected session, and an $18 CPM—are clearly disclosed assumptions used to
make the calculation auditable rather than claims about a real streaming company.

## Challenges we ran into

The hardest problem was making agentic analysis useful without allowing a model to invent evidence,
write arbitrary SQL, or silently take action. We separated responsibility:

1. deterministic thresholds establish that an anomaly is real;
2. fixed, validated queries retrieve only the evidence needed;
3. deterministic formulas calculate impact;
4. Gemini explains evidence and drafts a response; and
5. a human owns the final decision.

We also handled practical integration issues: different MCP result-envelope formats, ClickHouse
aggregate alias behavior, persistent stdio session management, database password policy, transient
cloud wake-up latency, strict cloud-project isolation, and Cloud Run startup behavior when a remote
datastore is still waking. Production now listens immediately but keeps readiness and operational
endpoints closed until initialization succeeds.

## Accomplishments that we're proud of

- A real end-to-end event → ClickHouse → official MCP → four-agent → human approval workflow.
- Four genuine Google ADK/Gemini stages rather than a simulated agent animation.
- An original, visually coherent streaming catalog with no third-party media or IP.
- Quantified impact with the complete calculation methodology visible on every incident.
- A database-enforced read-only MCP identity plus application-level query defenses.
- A human gate with no hidden action-execution capability.
- Real ClickHouse Cloud, MCP, Vertex AI, Docker, API, policy, and regression verification.
- Cost controls: event-gated Gemini, scale-to-zero Cloud Run, one maximum instance, and project
  budget checkpoints.

## What we learned — findings

Agent reliability improves when models receive bounded evidence and immutable calculations instead
of a blank SQL surface. The model is best used to synthesize and communicate a decision context,
while code and database permissions establish the facts it is allowed to use.

ClickHouse works especially well for this pattern. Short-window operational queries and longer
rolling baselines can share one real-time store, and the official MCP server lets agents consume
that evidence without adding a second analytics pipeline. A separate read-only database identity is
more credible than relying on prompt instructions to prevent writes.

We also learned that human governance should be visible in the product, not hidden in documentation.
Showing `pending approval`, recording an explicit decision, and having no execution tool makes the
safety boundary understandable to operators and judges.

## What's next

Future versions could add tenant-scoped baselines, learned seasonal thresholds, incident-feedback
calibration, private service ingress, and integrations that prepare change plans for real operations
systems. The human decision boundary would remain: integrations could stage a plan, but WatchTower
would not silently execute high-impact infrastructure changes.

## Disclosure

Telemetry is synthetic because private streaming-platform operational data is neither available nor
appropriate for a public hackathon. Detection, correlation, ClickHouse persistence, official MCP
access, business-impact calculation, Google ADK/Gemini orchestration, and the human-decision record
are real.
