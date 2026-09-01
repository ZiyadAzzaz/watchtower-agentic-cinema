# WatchTower project report

**Report date:** September 1, 2026

**Google Cloud target:** `watchtower-507216` only

**Competition:** Agentic Cinema: The Blockbuster Hackathon — ClickHouse Track

## Executive status

WatchTower is implemented and has passed local and Cloud end-to-end demonstrations. ClickHouse
Cloud now contains the WatchTower schema and fictional catalog, with independent scoped application
and read-only MCP identities. The complete path is working: synthetic live telemetry, deterministic
detection, official MCP investigation, quantified impact, four real Gemini/ADK agent stages through
Vertex AI, and a persisted human approval decision.

Production deployment and public publication are intentionally not represented as complete. The
private Cloud Run deployment is waiting for explicit authorization to transfer the three local
runtime secrets to Google Secret Manager. Public service and repository access remain a separate
release checkpoint.

## Completion matrix

| Area | Status | Evidence |
|---|---|---|
| Original implementation | Complete | New standalone workspace; no Verity source or resource used |
| Fictional catalog | Complete | 12 original titles and code-native gradient covers |
| Generator and injection | Complete | Real ClickHouse writes and authenticated control endpoint |
| Detection and impact | Complete | Deterministic thresholds and auditable USD/viewer-hour method |
| Official ClickHouse MCP | Complete locally and in Cloud | Official package over stdio, persistent session, read-only user and middleware |
| Four-agent ADK workflow | Complete | `SequentialAgent` with Detector, Root-Cause, Impact, and Action agents |
| Human approval | Complete | Pending-by-default approve/dismiss flow; no execution tool exists |
| Web product | Complete locally | Responsive FastAPI dashboard on `127.0.0.1:8080` |
| Automated verification | Complete | 22 unit/API/policy tests plus 1 real ClickHouse/MCP integration test |
| Google budget guardrail | Complete | $80 gross-cost budget with $25/$50/$75/$80 alerts |
| Google runtime foundation | Complete | Five required APIs enabled; dedicated Vertex AI runtime identity created |
| Vertex AI Gemini | Complete | Controlled Gemini 2.5 Flash run completed four real ADK stages in `watchtower-507216` |
| ClickHouse Cloud | Complete | TLS schema, catalog, scoped app user, scoped MCP user, and Cloud pipeline verified |
| Cloud Run URL | Blocked | Secret Manager transfer requires explicit authorization; public release remains gated |
| GitHub repository | Private and pushed | `ZiyadAzzaz/watchtower-agentic-cinema`; public release requires approval |
| Devpost/video | Prepared | Copy and three-minute runbook ready; recording/submission remains a human action |

## What was built

- A FastAPI web service and polished dependency-free operator dashboard.
- Synthetic time-of-day telemetry for five regions and 12 fictional titles.
- Three controllable incidents: view collapse, buffering spike, and ad-delivery failure.
- Rolling ClickHouse baseline/current-window analysis with fixed, bounded SQL.
- Official `mcp-clickhouse` calls at runtime using a dedicated `SELECT`-only identity.
- A second MCP middleware boundary that rejects mutations, comments, multiple statements, unknown
  tables, and unbounded output.
- A real Google ADK four-agent `SequentialAgent`; Gemini is invoked only after deterministic gates.
- Quantified affected sessions, lost viewer-hours, revenue impact, severity, and methodology.
- Versioned incident state and a visible human decision boundary.
- Production validation, Docker packaging, Cloud Run scripts, CI, MIT license, security and demo
  documentation.

## Verification results

| Check | Result |
|---|---|
| Ruff formatting | Pass |
| Ruff lint | Pass |
| Unit/API/policy suite | 22 passed, 1 integration deselected |
| Coverage | 71% overall; critical deterministic modules 84–100% |
| Real ClickHouse + official MCP | 1 passed |
| Real ClickHouse Cloud pipeline | Pass; TLS, scoped users, official MCP, incident and decision verified |
| Real Vertex AI Gemini | Pass; Gemini 2.5 Flash, four ADK stages and MCP evidence tools |
| Destructive MCP query | Rejected as required |
| Docker image build | Pass |
| Container health | App running; ClickHouse healthy |
| Live dashboard API | Operational, 12 titles, real timeline data |
| Missing admin token | HTTP 401 |
| Authenticated anomaly workflow | 1 incident created, 4 agent trace steps |
| Human decision | Pending incident changed to approved; no action executed |

## Problems found and resolutions

1. **ClickHouse aggregate aliases conflicted with source column names.** ClickHouse expanded an alias
   inside another aggregate and rejected the dashboard query. Output aliases were made unambiguous
   and the real container endpoint was re-tested successfully.
2. **Official MCP result envelopes varied.** The parser now handles text envelopes, structured
   content, and column-plus-positional-row responses.
3. **Starting one MCP process per query was slow and wasteful.** The client now maintains one
   lifecycle-managed stdio session with serialized access and clean application shutdown.
4. **Repeat integration runs accumulated live test telemetry.** The integration test now writes a
   unique test scope per run, proving behavior without deleting shared local data.
5. **Local Docker mutation endpoints saw a bridge address, not loopback.** The local stack now uses
   an explicit demo operator token while remaining bound only to `127.0.0.1`.
6. **GitHub CLI credentials were invalid.** Device re-authentication succeeded. The verified `main`
   branch is backed up in a new private repository; visibility remains gated for release review.
7. **Local ADC quota attribution referenced the prior project.** No Gemini request was made in that
   state. The local ADC quota project was changed to `watchtower-507216`; explicit runtime project
   configuration now overrides unrelated `gcloud` defaults.
8. **ClickHouse Cloud initially rejected a generated password.** The generator now guarantees the
   Cloud password-policy character classes while retaining a strong random component.
9. **A transient ClickHouse Cloud wake timeout interrupted one diagnostic.** The fail-closed test was
   retried after wake-up and the complete real Gemini/MCP path passed.

## Cost and cloud safety

The project-scoped Google Cloud budget is named `WatchTower hard guardrail - 80 USD`, budget ID
`a6e67826-68d2-4f3c-9dd1-c6865afde710`. It covers project number `283557821298`, excludes credits,
starts August 31, 2026, and alerts on actual spend at 31.25%, 62.5%, 93.75%, and 100%—exactly $25,
$50, $75, and $80.

No payment method, billing-account link, or unrelated budget was changed. Google budget alerts are
notifications, not automatic spending caps. Cloud Run is therefore additionally constrained to
scale-to-zero and one maximum instance. No billing-disabling automation was created because that
would violate the instruction not to change billing and can damage unrelated project services.

The local Docker services incur no Google Cloud spend. Before provisioning ClickHouse Cloud, redeem
the official credit, select the smallest viable service, and configure its $100/$200/$300 monitoring
checkpoints.

## Immediate human actions

1. Submit the Google hackathon credit request form immediately if it is still open:
   <https://forms.gle/XPe837tzogh8L5sX6>. Form submission cannot be completed or verified by this
   workspace agent.
2. Configure ClickHouse Cloud spend checkpoints at $100, $200, and $300 in its console; never add a
   personal payment method.
3. Explicitly authorize transferring the three generated runtime secrets from local `.env` to
   Secret Manager in `watchtower-507216`.
4. Verify the private Cloud Run deployment, then approve public repository and service access.
5. Record the three-minute demo, upload it publicly, and complete Devpost before the official
   September 9 deadline.

## Release plan

The remaining sequence is dependency-driven: prepare ClickHouse Cloud and secrets, run the guarded
Google Cloud setup, build and deploy a private Cloud Run revision, run the same end-to-end tests on
the hosted URL, review current spend, obtain explicit public-release approval, publish the service
and GitHub repository, record the demo, and submit Devpost. At $25, $50, or $75 Google spend—or
$100/$200 ClickHouse spend—work pauses for review. At the hard caps, all new spending work stops.

## Competition assessment

The implementation is designed to score strongly on technical depth, product coherence, credible
business impact, and originality. No engineering process can guarantee first place; the remaining
hosted proof, concise demo story, and complete submission are essential to make the work judgeable.
