# WatchTower — Professional Project and Deployment Report

**Report date:** September 4, 2026

**Project owner:** Ziyad Azzaz

**Google Cloud project:** `watchtower-507216` only

**Competition:** Agentic Cinema: The Blockbuster Hackathon — ClickHouse Track

**Repository:** <https://github.com/ZiyadAzzaz/watchtower-agentic-cinema> (public)

**Live application:** <https://watchtower-283557821298.us-central1.run.app>

**Current release state:** **Publicly released and verified.** Demo recording and Devpost submission remain.

## 1. Executive summary

WatchTower is a human-governed streaming incident-intelligence system. It continuously generates and
stores fictional streaming telemetry, detects operational anomalies using deterministic rules,
investigates evidence through the official ClickHouse MCP server, calculates business impact, and
uses a four-stage Google ADK/Gemini workflow to prepare an executive response. Every proposed action
stops at a visible human approval boundary; the system contains no autonomous remediation tool.

The complete application and cloud data path have been independently verified against ClickHouse
Cloud and Vertex AI in `watchtower-507216`. Three production credentials are now stored in Google
Secret Manager with secret-level access for a dedicated runtime service account. A private container
image was built successfully in Google Cloud and stored in Artifact Registry.

On September 4, 2026 the private hosted release was completed. Four further defects that only appear
in the real Cloud Run environment were found and fixed (Section 9, items 13–16), and revision
`watchtower-00006-gz8` is now live, private, and fully verified end to end: authenticated health and
readiness, a 12-title production dashboard backed by ClickHouse Cloud, rejection of unauthenticated
control requests, one controlled incident investigated through the official ClickHouse MCP server by
four real Gemini 2.5 Flash agents, quantified impact, and a persisted human approval.

No resource, IAM policy, service, credential, deployment, or billing setting in the separate Verity
project was changed.

## 2. Product objective

Streaming operations teams often see a metric change before they understand its cause or financial
importance. WatchTower converts that fragmented workflow into one governed investigation:

1. Synthetic streaming events arrive in ClickHouse.
2. Deterministic rules detect a view collapse, buffering spike, or ad-delivery failure.
3. The official ClickHouse MCP server retrieves bounded, read-only evidence.
4. Root cause and impact modules create an auditable technical and commercial assessment.
5. Four specialized Gemini agents produce a structured incident brief and recommended action.
6. A human operator approves or dismisses the recommendation.
7. The decision and agent trace are persisted for review.

The project uses an original fictional catalog so the demonstration has no dependency on copyrighted
movie artwork, external entertainment APIs, or another project’s data.

## 3. System architecture

| Layer | Implementation | Responsibility |
|---|---|---|
| Product interface | FastAPI and dependency-free HTML/CSS/JavaScript | Live dashboard, incident timeline, simulation controls, approval UI |
| Event generation | Python synthetic generator | Time-of-day traffic across 12 titles and five regions |
| Operational store | ClickHouse Cloud | Telemetry, incidents, decisions, and analytical aggregation |
| Detection | Deterministic Python rules | Explainable view, buffering, and advertising thresholds |
| Evidence access | Official `mcp-clickhouse` over stdio | Read-only, bounded investigation queries |
| Defense in depth | WatchTower MCP middleware | Rejects mutations, comments, multiple statements, unknown tables, and unbounded output |
| Agent orchestration | Google ADK `SequentialAgent` | Detector, Root-Cause, Impact, and Action stages |
| Model provider | Gemini 2.5 Flash through Vertex AI | Structured reasoning after deterministic event gates |
| Governance | Versioned incident decision workflow | Pending-by-default approve/dismiss boundary |
| Runtime | Private Google Cloud Run | Scale-to-zero hosted application |
| Secrets | Google Secret Manager | Application DB password, MCP DB password, operator token |
| Image storage/build | Artifact Registry and Cloud Build | Private reproducible application container |

## 4. Implementation delivered

### 4.1 Data and demonstration

- Twelve original titles with code-native gradient artwork.
- Five operating regions and multiple CDN nodes.
- Realistic time-of-day telemetry and historical baseline seeding.
- Three controllable incident types: view drop, buffer spike, and ad failure.
- Unique test scopes so repeated integration runs do not delete or corrupt shared data.

### 4.2 Detection and business impact

- Fixed, auditable anomaly thresholds rather than opaque model-only detection.
- Rolling current and baseline windows implemented with bounded ClickHouse SQL.
- Root-cause ranking based on real queried CDN and regional evidence.
- Affected sessions, lost viewer-hours, estimated revenue loss, severity, and methodology.
- Duplicate-open-incident protection.

### 4.3 Agentic workflow

- A real four-stage Google ADK sequential workflow.
- Gemini is event-gated and is not invoked for every routine telemetry tick.
- Each agent receives MCP-derived evidence and produces a traceable stage result.
- Production fails closed if Vertex AI is unavailable; it does not silently present a fallback as a
  real model response.
- Explicit runtime environment selection locks production to `watchtower-507216`.

### 4.4 Human governance and security

- All incidents default to `pending_approval`.
- Approve and dismiss actions require the operator token in production.
- Decisions are versioned and persisted.
- There is no infrastructure-remediation or destructive action tool.
- ClickHouse application and MCP identities are independent and least-privileged.
- MCP identity has `SELECT` access only.
- Application identity has only the `SELECT` and `INSERT` access required by WatchTower.
- Security headers include CSP, clickjacking protection, MIME protection, referrer restrictions,
  and browser capability restrictions.

## 5. Cloud resources created in WatchTower

All listed resources belong to `watchtower-507216`; project number `283557821298`.

| Resource | State |
|---|---|
| Vertex AI API | Enabled |
| Artifact Registry API | Enabled |
| Cloud Build API | Enabled |
| Cloud Run API | Enabled |
| Secret Manager API | Enabled |
| Runtime service account | `watchtower-runtime@watchtower-507216.iam.gserviceaccount.com` |
| Runtime model permission | `roles/aiplatform.user` |
| Artifact Registry repository | Private `watchtower` repository in `us-central1` |
| Secret: application DB password | `watchtower-clickhouse-app-password` |
| Secret: MCP DB password | `watchtower-clickhouse-mcp-password` |
| Secret: operator token | `watchtower-admin-token` |
| Secret access | Granted individually to the runtime service account only |
| First container image | `watchtower:3f6d79a` |
| First image digest | `sha256:2694a2a56f63923e716d33792c39c2fd8ca8c6830bf7b167ee9351919a56f25b` |
| Cloud Build ID | `9266dfe2-8ff7-41de-b75a-cf913ffb784b` — successful |
| **Released container image** | `watchtower:baseline-fix-20260904` |
| **Released image digest** | `sha256:e10cea5c563846334b4cc218af358c972f8a8cb0deb85e905ff7996ed0ab5001` (build `ef43a82e-57ea-4898-b3ec-708cbadb9707`) |
| **Cloud Run service** | Private `watchtower`; ready revision `watchtower-00006-gz8` serving 100% of traffic |
| **Public service URL** | <https://watchtower-283557821298.us-central1.run.app> |

The build upload was inspected before submission: 35 files totaling approximately 139 KB were
included. `.env`, Git metadata, tests, internal briefs, and local caches were excluded. No secret
value was displayed or included in the container context.

## 6. ClickHouse Cloud state

- TLS endpoint configured in `us-central1`.
- `watchtower` database, schema, tables, and fictional catalog initialized.
- Scoped `watchtower_app` ingestion identity created.
- Scoped `watchtower_mcp` read-only identity created.
- Local `.env` contains the scoped identities rather than the database administrator identity.
- Bootstrap is disabled for production runtime.
- End-to-end cloud verification passed for ingestion, official MCP reads, detection, root-cause
  evidence, impact, four agent stages, incident persistence, approval persistence, and destructive
  query rejection.

Secret values are intentionally absent from this report.

## 7. Google Cloud isolation and cost safety

### 7.1 Strict project isolation

- Active gcloud configuration: `watchtower`.
- Active CLI project: `watchtower-507216`.
- ADC quota project: `watchtower-507216`.
- Runtime code explicitly sets the WatchTower project, location, and Vertex AI mode.
- Deployment scripts contain the fixed WatchTower project ID and validate it before mutation.
- The older `default` gcloud configuration for `verity-506800` remains saved but inactive.
- No Verity cloud resource or billing setting was touched.

### 7.2 Google Cloud budget guardrail

The project budget is `WatchTower hard guardrail - 80 USD`, budget ID
`a6e67826-68d2-4f3c-9dd1-c6865afde710`. It uses gross spend with credits excluded and alerts at:

- $25
- $50
- $75
- $80

No payment method, billing-account link, or unrelated billing configuration was changed. Google
Cloud budgets send notifications; they are not automatic hard spending caps. Cloud Run is therefore
configured with zero minimum instances, one maximum instance, one CPU, 512 MiB memory, concurrency
20, and a 120-second request timeout. Work must pause for review at the defined checkpoints.

ClickHouse Cloud cost checkpoints of $100, $200, and $300 must be configured manually in the
ClickHouse console. Database credentials cannot configure account-level billing alerts.

## 8. Verification evidence

| Check | Result |
|---|---|
| Ruff formatting | Pass |
| Ruff lint | Pass |
| Unit/API/policy suite after the September 4 corrections | **26 passed, 1 integration deselected** |
| Coverage after the September 4 corrections | **68% overall**; critical deterministic modules 82–100% |
| Production startup regression | Pass; health listens while readiness remains closed |
| Real local ClickHouse and official MCP integration | Pass |
| Real ClickHouse Cloud pipeline | Pass |
| Real Vertex AI Gemini 2.5 Flash execution | Pass |
| Four Google ADK stages | Pass |
| Destructive MCP query | Rejected as required |
| Docker image build | Pass |
| Cloud Build and private Artifact Registry push | Pass |
| Authentication without operator token | HTTP 401 |
| Controlled anomaly workflow | Incident and four-stage trace created |
| Human decision | Pending incident changed to approved; no action executed |
| Latest pushed GitHub CI before lifecycle correction | Pass — run `33545631480` |
| **Hosted `/health` and `/api/healthz` (identity token)** | **Pass — `{"status":"ok","service":"watchtower"}`** |
| **Hosted `/readyz`** | **Pass — `operational`** |
| **Hosted `/api/dashboard`** | **Pass — 12 fictional titles, `production`, `operational`** |
| **Hosted control request without operator token** | **Rejected — HTTP 401** |
| **Hosted controlled incident** | **Pass — `274e27ce-9839-40cd-8eb7-68afd12593b3`, buffer spike, +251.5% vs baseline, confidence 0.99** |
| **Hosted MCP evidence** | **Pass — 3 bounded evidence rows; cause isolated to CDN node `me-edge-02`** |
| **Hosted four-stage Gemini/ADK trace** | **Pass — Detector → Root-Cause → Impact Estimator → Action Drafter, ~25 s total, `ai_provider: Gemini on Vertex AI`** |
| **Hosted quantified impact** | **Pass — 52 affected sessions, 35.5 lost viewer-hours, $6.90, severity `low`** |
| **Hosted human approval** | **Pass — `pending_approval` → `approved`, persisted; no action executed** |
| **Hosted duplicate suppression** | **Pass — ticks 2–4 created no further incident** |
| **Hosted privacy checkpoint (pre-release)** | **Pass — Cloud Run IAM policy contained no bindings before the approved release** |
| **Public judge-mode smoke test** | **Pass — no credentials: dashboard, 12 titles, `operational`; cold start to ready in 28 s** |
| **Public control-endpoint lockdown** | **Pass — `inject`, `tick`, `approve`, and a wrong token all rejected 401 from the open internet** |
| **Hosted cost limits** | **Pass — minScale 0, maxScale 1, concurrency 20, 1 vCPU, 512 MiB, 120 s timeout** |

All corrections above are committed and built. The evidence in this table was produced against the
live private Cloud Run revision `watchtower-00006-gz8`, not against a local process.

## 9. Problems discovered and resolutions

1. **ClickHouse aggregate aliases conflicted with source column names.** Output aliases were made
   unambiguous and the real query was retested.
2. **Official MCP response envelopes varied.** The parser now accepts text, structured content, and
   column-plus-positional-row representations.
3. **One MCP process per query was inefficient.** The client now maintains a serialized persistent
   stdio session and closes it during application shutdown.
4. **Integration runs accumulated telemetry.** Each run now uses a unique scope without deleting
   shared data.
5. **Docker bridge traffic was not loopback.** Local mutations use an explicit demonstration token
   while ports remain bound to `127.0.0.1`.
6. **Initial GitHub CLI credentials were invalid.** Device authentication was renewed and the source
   was pushed to a new private repository.
7. **ADC previously attributed quota to another local project.** No Gemini request was sent in that
   state. ADC and the active gcloud configuration now use `watchtower-507216`, and runtime selection
   is explicit.
8. **ClickHouse rejected an initially generated password.** Generation now guarantees required
   character classes while preserving strong randomness.
9. **A sleeping ClickHouse Cloud service caused one transient timeout.** Fail-closed verification was
   retried after wake-up and passed.
10. **Cloud Build context lacked an explicit Google ignore file.** `.gcloudignore` was added and the
    exact upload list was verified before the build.
11. **The first Cloud Run revision did not listen before remote initialization completed.** The
    production lifespan now starts initialization asynchronously, exposes only lightweight health
    during startup, and gates readiness/data/control endpoints until success. A regression test was
    added and the 24-test suite passes.
12. **Local tooling blocked cloud commands after the first revision.** Deployment work paused on
    September 2 because of a restriction in the local development environment rather than any cloud
    service. No workaround was attempted and no WatchTower resource was affected. Access was
    restored on September 4, 2026 and the queued sequence was executed in full.
13. **The ClickHouse client connected while the application object was being constructed.** The
    asynchronous-initialization fix in item 11 was not sufficient: `ClickHouseRepository.__init__`
    called `clickhouse_connect.get_client(...)`, which performs a real TLS handshake and a
    `SELECT version(), timezone()` round trip. That call ran synchronously inside the FastAPI
    lifespan, before the background task could start, so a sleeping ClickHouse Cloud service still
    blocked the event loop until the read timed out and the container exited with status 3. The
    connection is now created lazily on first use behind a thread lock, no network call occurs
    during construction, and the production initialization task retries a waking datastore six
    times with exponential backoff. A regression test asserts that constructing the repository
    never contacts ClickHouse.
14. **Cloud Run's frontend reserves the exact path `/healthz`.** Requests to `/healthz` were
    answered by Google with a generic HTML 404 and never reached the container; the response
    carried none of WatchTower's security headers, while `/healthz/` returned the application's own
    307 redirect and `/nope` returned the application's own 404. The same handler is now also
    published at `/health` and `/api/healthz`, and readiness at `/ready` and `/api/readyz`. Cloud
    Run's startup probe is a TCP check and was never affected.
15. **The MCP stdio session was created in one asyncio task and reused from another.** The official
    MCP stdio client opens an anyio task group, and anyio requires the task that enters a cancel
    scope to be the task that exits it. Because the persistent session was opened lazily inside
    whichever HTTP request arrived first, the next request raised
    `RuntimeError: Attempted to exit a cancel scope that isn't the current task's current cancel
    scope`, and every request after that raised `ClosedResourceError`. Every hosted detection tick
    therefore returned HTTP 500. The client now owns a dedicated long-lived session task that
    enters and exits the exit stack itself and serves queries from an `asyncio.Queue`; this
    preserves the previous serialized access, discards a broken session so the next call rebuilds
    it, and fails any queued request cleanly on shutdown. Verified against real ClickHouse Cloud by
    issuing three queries from three independent tasks through one persistent session.
16. **Seeding was gated on total row count, so the detection baseline went stale.** Detection
    compares a five-minute live window against the preceding sixty-minute baseline window, but
    history was only seeded when the table held fewer than 1,200 rows in total. Telemetry written
    days earlier satisfied that check while leaving both windows empty, so the hosted service
    ingested events and reported healthy yet could never raise an incident. Seeding is now driven
    by the number of rows inside the baseline window, and a detection tick re-seeds a thin baseline
    before generating, so the service self-heals after any idle gap. A regression test stores
    three-day-old history and asserts it is re-seeded once and not re-seeded again.

## 10. Current status matrix

| Area | Status |
|---|---|
| Core application | Complete |
| Dashboard and controls | Complete |
| Detection and impact | Complete |
| Official ClickHouse MCP | Complete |
| Four-agent ADK/Gemini workflow | Complete |
| Human approval boundary | Complete |
| ClickHouse Cloud | Complete and verified |
| Vertex AI | Complete and verified |
| Secret Manager | Complete |
| Runtime least-privilege IAM | Complete |
| Private container build | Complete |
| Cloud Run lifecycle correction | Complete and verified in production |
| Corrected private Cloud Run revision | **Complete — `watchtower-00006-gz8` ready and serving** |
| Hosted end-to-end verification | **Complete — all eleven hosted checks pass** |
| GitHub | Private; September 4 corrections committed and pushed |
| Public service/repository | **Released September 4, 2026 under explicit owner approval** |
| Demo video and Devpost | Prepared materials exist; recording/submission pending |

## 11. Execution record and remaining sequence

Sections 1–12 of `docs/POST_ACCESS_RUNBOOK.md` were executed in order on September 4, 2026. Every
numbered step completed, including the four corrections in Section 9 items 13–16 that were required
to make the hosted revision behave correctly. Four Cloud Build runs and four Cloud Run revisions were
consumed reaching the working release; only `watchtower-00006-gz8` serves traffic.

What remains, in order:

1. Record the current Google Cloud and ClickHouse Cloud console spend totals (owner action).
2. Obtain the owner's explicit approval for public Cloud Run invocation and public repository
   visibility — Section 13 of the runbook.
3. Record the three-minute demo using `docs/DEMO_SCRIPT.md`.
4. Submit on Devpost using `docs/DEVPOST_SUBMISSION.md`.
5. Run a final judge-mode smoke test from a logged-out browser.

Public access remains a separate release checkpoint. The service and repository must not be made
public without explicit approval.

## 12. Judge-readiness plan

After private verification, the final competition sequence is:

1. Approve public Cloud Run invocation and repository visibility separately.
2. Execute the three-minute demo runbook with a clean incident narrative.
3. Record the dashboard, anomaly injection, MCP evidence, four agent stages, quantified impact, and
   human approval boundary.
4. Upload the video publicly.
5. Complete Devpost with the prepared architecture, technical story, source, and live URL.
6. Perform a final judge-mode smoke test from a logged-out browser.

The implementation is designed to compete strongly on technical depth, credible ClickHouse use,
agentic orchestration, safety, originality, and product coherence. No engineering process can
guarantee first place, but completing the hosted proof and presenting the human-governed story
clearly will make the work fully judgeable.

## 13. Final professional assessment

WatchTower is no longer a prototype concept: its core product, data platform, MCP integration,
deterministic intelligence, Gemini agents, governance model, cloud secrets, IAM, and container build
have all been implemented and tested. The remaining work is operational rather than architectural:
publish the corrected private revision, verify it end to end, then execute the separately authorized
public release and competition submission.

The project remains safely isolated from Verity, secret values remain protected, production access
remains private, and cloud costs are constrained and monitored.

## 14. September 2 follow-up readiness audit

### Local tooling restriction and contest runway

Cloud deployment work was paused on September 2 by a restriction in the local development
environment, not by any cloud service. It was not a Google Cloud quota, a ClickHouse policy, an
organization restriction, or a project IAM failure, and no WatchTower resource was affected. Access
was restored on September 4 and the queued sequence was executed in full.

The contest deadline of September 9, 2026 at 2:00 PM Pacific Daylight Time is September 10 at 00:00
Cairo time, which left adequate runway for deployment, verification, and submission.

### Google-only AI audit

The shipped runtime and dependency manifests were scanned for OpenAI, Anthropic, Cohere, Mistral,
Groq, Bedrock/Boto3, Hugging Face Transformers, LangChain, LlamaIndex, CrewAI, AutoGen, and Semantic
Kernel model/framework imports or packages. The result is **zero non-Google AI dependencies or
imports in the shipped runtime**. The only forbidden vendor strings found in the repository are
deliberate assertions in `tests/test_policy.py`; that passing test prevents those imports from being
added to `watchtower/`. Runtime AI imports are exclusively Google ADK and Google Gen AI.

### Actual spend evidence

- **Google Cloud:** no budget alert has been reported. The only defensible observed bound is below
  the first $25 gross-cost checkpoint at the last observable check; an exact accrued amount is not
  available from repository data or the budget resource.
- **ClickHouse Cloud:** no owner-console total has been supplied. Database credentials cannot read
  organization billing, so the current exact amount is unknown.

Neither value is estimated or invented. The owner must record both console totals before public
release. The standalone ClickHouse owner action is in `docs/CLICKHOUSE_BILLING_ALERTS.md`.

### Preparation completed while blocked

- Devpost submission text expanded into paste-ready sections with only public URL placeholders.
- Demo runbook reconciled with the current UI, persisted incident history, and model latency.
- README rewritten for reproducible Docker and real-Vertex host workflows.
- Standalone $100/$200/$300 ClickHouse billing checkpoint instructions added.
- Exact private rebuild, deployment, authenticated test, incident, policy, Git, and CI command
  sequence added in `docs/POST_ACCESS_RUNBOOK.md`.
- Public release remains gated on originality/media/AI re-audit, spend review, and explicit owner
  approval.

## 15. September 4 private release record

### Sequence executed

| Runbook section | Result |
|---|---|
| 1. Lock and verify the target | Configuration `watchtower`, project `watchtower-507216`, ADC quota project set |
| 2. Confirm the first-revision diagnosis | `HealthCheckContainerError` on `watchtower-00001-8nc`; container never listened on `PORT=8080` |
| 3. Re-run local gates | Ruff format and lint clean; 26 passed, 1 integration deselected |
| 4. Verify the secret-free build context | 35 files, ~149 KB; no `.env`, credentials, briefs, or caches |
| 5. Build the corrected private image | Build `ef43a82e-57ea-4898-b3ec-708cbadb9707`, digest `sha256:e10cea5c…` |
| 6. Deploy privately with fixed limits | Revision `watchtower-00006-gz8` ready, 100% of traffic, `--no-allow-unauthenticated` |
| 7. Authenticated health and readiness | `/health` and `/api/healthz` return `ok`; `/readyz` returns `operational` |
| 8. Dashboard and authentication rejection | 12 fictional titles, `production`/`operational`; token-less control request rejected 401 |
| 9. One controlled hosted incident | Buffer spike armed for `aurora-drift` / MENA; incident created on the first tick |
| 10. Evidence, agents, persistence, approval | 3 MCP evidence rows, 4 Gemini stages, quantified impact, approval persisted |
| 11. Private access and cost limits | No IAM bindings; minScale 0, maxScale 1, concurrency 20, 1 vCPU, 512 MiB, 120 s |
| 12. Documentation, commit, push, CI | This section; committed and pushed to the private repository |

### Hosted incident evidence

- **Incident:** `274e27ce-9839-40cd-8eb7-68afd12593b3`
- **Anomaly:** buffer spike on the fictional title `aurora-drift` in MENA
- **Observed vs baseline:** 0.185 vs 0.053 buffer-event rate — **+251.5%**, confidence **0.99**
- **Root cause from bounded MCP evidence:** degradation concentrated on CDN node `me-edge-02`
- **Impact:** 52 affected sessions, 35.5 lost viewer-hours, **$6.90**, severity `low`
- **Agent trace:** Detector → Root-Cause → Impact Estimator → Action Drafter, four stages, ~25 s
- **Model path:** `ai_provider` reported `Gemini on Vertex AI` after the run
- **Decision:** `pending_approval` → `approved` with an operator note; **no action was executed**

### Cost position

- **Google Cloud:** the `WatchTower hard guardrail - 80 USD` budget remains configured with alerts at
  31%, 63%, 94%, and 100% of $80 — that is $25, $50, $75, and $80. **No budget alert has fired.**
  The exact accrued amount is not readable from the budget resource and must be read by the owner in
  the Cloud Billing console. The pre-existing `verity alert` budget on the same billing account was
  listed while enumerating budgets and was **not modified**; no Verity resource was touched.
- **ClickHouse Cloud:** database credentials cannot read organization billing. The $100 / $200 / $300
  checkpoints are an owner action in the ClickHouse console — see
  `docs/CLICKHOUSE_BILLING_ALERTS.md`. No total is recorded here because none was observed.

Neither figure is estimated. Both console totals must be recorded by the owner before public release.

### Google-only AI position, re-confirmed

`tests/test_policy.py` continues to pass. The shipped runtime imports `google.adk` and `google.genai`
only. No OpenAI, Anthropic, Cohere, Mistral, Groq, Bedrock, Hugging Face Transformers, LangChain,
LlamaIndex, CrewAI, AutoGen, or Semantic Kernel package or import exists in `watchtower/`,
`requirements.txt`, or `pyproject.toml`. The corrections made on September 4 touched only lifecycle,
transport, and seeding logic; no dependency was added.

## 16. September 4 public release

The project owner gave explicit approval to publish both the Cloud Run service and the GitHub
repository. Section 13 of the runbook was satisfied and executed.

### Pre-publication audit

| Check | Result |
|---|---|
| Secret files anywhere in Git history | None. `.env` was never tracked; `.gitignore` excludes it and every variant |
| Secret values anywhere in Git history | None. The only match was the test fixture literal in `tests/test_config.py` |
| Non-Google AI SDK in runtime or manifests | None. Runtime AI imports are `google.adk` and `google.genai` only |
| Real third-party media, artwork, or metadata | None. All 12 titles are original; the UI contains **no external URLs at all** and every cover is code-native gradient art |
| ClickHouse Cloud endpoint in public docs | Redacted from `docs/POST_ACCESS_RUNBOOK.md` before publication |
| Google Cloud budget checkpoint | No alert fired at $25, $50, $75, or $80 |
| ClickHouse Cloud checkpoint | No checkpoint reported as reached by the owner |

### Publication actions

1. `roles/run.invoker` granted to `allUsers` on the `watchtower` Cloud Run service. No revision was
   redeployed and no runtime configuration changed; `watchtower-00006-gz8` still serves all traffic
   with minScale 0 and maxScale 1.
2. Repository visibility changed from private to public.

### Post-release verification, performed with no credentials of any kind

| Check | Result |
|---|---|
| `GET /` | 200 |
| `GET /api/healthz` | 200 |
| `GET /readyz` from a cold, scaled-to-zero service | 503 during initialization, then `operational` after 28 s |
| `GET /api/dashboard` | 12 fictional titles, `production`, `operational`, 8,760 events |
| `POST /api/admin/inject` | **401** |
| `POST /api/admin/tick` | **401** |
| `POST /api/incidents/{id}/approve` | **401** |
| `POST /api/admin/tick` with an incorrect operator token | **401** |

The human approval boundary therefore holds against the open internet: anyone may observe WatchTower,
and nobody without the operator token may inject an anomaly, advance the loop, or record a decision.

### Known residual item

`docs/POST_ACCESS_RUNBOOK.md` was committed in `a24d446` containing the ClickHouse Cloud endpoint
hostname before it was redacted, so that hostname remains readable in the public Git history. The
endpoint is protected by TLS verification and scoped, least-privilege passwords held in Secret
Manager, and no credential was ever committed. Removing it from history would require a rewrite and
force-push, which has not been performed.

### Remaining work

1. Record the three-minute demo using `docs/DEMO_SCRIPT.md`.
2. Submit on Devpost using `docs/DEVPOST_SUBMISSION.md`, with the live URL and public repository.
3. Record the Google Cloud and ClickHouse Cloud console spend totals (owner action).
