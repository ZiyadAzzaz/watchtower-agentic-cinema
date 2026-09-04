# Testing and verification guide

Everything here runs from a clean clone. Nothing in this guide needs a Google Cloud account, a
ClickHouse Cloud account, or any secret.

## What you can verify, and how long it takes

| Level | Needs | Time | Command |
|---|---|---|---|
| 1. Static checks | Python 3.12 | ~5 s | `ruff format --check` and `ruff check` |
| 2. Unit, API, and contract tests | Python 3.12 | ~10 s | `pytest` |
| 3. Real ClickHouse + real MCP | Docker | ~2 min | `pytest -m integration` |
| 4. The whole product, running | Docker | ~3 min | `docker compose up` |
| 5. The public deployment | nothing | ~30 s | `curl` the live URL |

## Level 1 and 2 — static checks and the test suite

```bash
python -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/python -m ruff format --check watchtower tests scripts
.venv/bin/python -m ruff check watchtower tests scripts
.venv/bin/python -m pytest --cov=watchtower --cov-report=term-missing
```

On Windows use `.venv\Scripts\python.exe` instead of `.venv/bin/python`.

Expect **46 passed, 1 deselected**. The deselected test is the integration test in Level 3; it is
excluded by default because it needs Docker.

### What the suite covers

| File | What it proves |
|---|---|
| `test_detection.py` | Anomaly thresholds fire on real deviations and stay quiet otherwise |
| `test_impact.py` | Viewer-hours and revenue are arithmetic, not a model guess |
| `test_root_cause.py` | The cause is ranked from queried CDN and regional evidence |
| `test_generator.py` | Telemetry follows time-of-day traffic and honours injections |
| `test_sql_safety.py` | Identifiers and filter values are validated before reaching ClickHouse |
| `test_agents.py` | The four ADK stages run in order and produce a trace |
| `test_runtime.py` | Tick gating, duplicate suppression, decisions, and baseline seeding |
| `test_api.py` | Routes, security headers, auth, and the production startup contract |
| `test_config.py` | Production refuses to start without TLS, Vertex AI, or the right project |
| `test_policy.py` | **No non-Google AI SDK exists in the shipped runtime** |
| `test_production_contract.py` | Every defect that once reached a live Cloud Run revision |

`test_production_contract.py` is the interesting one. Each case maps to a real production failure:

- the container that never bound its port because connecting blocked startup;
- Cloud Run's frontend reserving the exact path `/healthz`;
- history seeded on total row count, leaving the detection baseline empty;
- naive timestamps that a browser read as local time;
- and the human approval boundary — every control endpoint must reject a caller without the
  operator token, because the service is public.

It also asserts that **no execution tool exists anywhere in the runtime**. The action agent drafts a
recommendation; it can never act on one.

## Level 3 — real ClickHouse and the real MCP server

This runs against a genuine ClickHouse instance and the official `mcp-clickhouse` server over stdio.
No mocks.

```bash
docker compose up -d --wait clickhouse
.venv/bin/python -m pytest tests/test_clickhouse_integration.py -m integration -vv
```

It ingests telemetry, queries it back through MCP, detects an injected anomaly, builds an incident,
records a decision, and confirms a destructive query is rejected. Each run uses a unique scope, so
repeated runs never corrupt or delete shared data.

This is also the last step of CI, so every push proves the ClickHouse and MCP path still works.

## Level 4 — run the whole product locally

```bash
docker compose up --build -d
docker compose ps
```

Open <http://localhost:8080> once both containers are healthy. The stack creates ClickHouse, two
scoped database users, the schema, a historical baseline, and the application. No `.env` and no
cloud account.

To drive it:

1. Open the top-right **⌘** settings panel and save the token `local-demo-only`. This value is for
   the loopback-only local stack; production uses a Secret Manager token.
2. Press **Simulate incident** and choose a title, region, and failure type.
3. Watch the four agent stages run, then approve or dismiss the incident.

Approval records a human decision. It does not call a CDN, an ad platform, or any other service —
there is nothing in the codebase that could.

Tear down with `docker compose down -v`.

## Level 5 — check the public deployment

The live service is open to everyone. These need no credentials:

```bash
curl https://watchtower-283557821298.us-central1.run.app/health
curl https://watchtower-283557821298.us-central1.run.app/readyz
curl https://watchtower-283557821298.us-central1.run.app/api/dashboard
```

> Use `/health` or `/api/healthz`, not `/healthz` — Google's serverless frontend answers that exact
> path itself, so the request never reaches the container.

The service scales to zero, so the first request after an idle period takes roughly 30 seconds while
readiness reports `503`. That is the designed startup contract, not a fault.

### Run the whole loop yourself with the demo key

```bash
BASE=https://watchtower-283557821298.us-central1.run.app
KEY=watchtower-judge-demo

curl -s -X POST -H 'Content-Type: application/json' -H "X-Watchtower-Token: $KEY"   -d '{"kind":"ad_failure","title_id":"copper-tide","region":"South Asia","duration_cycles":4,"magnitude":0.8}'   $BASE/api/admin/inject

curl -s -X POST -H 'Content-Type: application/json' -H "X-Watchtower-Token: $KEY" -d '{}' $BASE/api/admin/tick
curl -s $BASE/api/dashboard
```

Arming a simulation writes the anomaly across the live detection window, so the next pass detects it
immediately rather than averaging it away. Four Gemini stages then run — expect roughly 25 seconds.

Starting an investigation is rate limited on the shared key. Approving and dismissing are not.

### Confirm the human approval boundary from the open internet

The most important property of this system is that anyone may *observe* it and nobody may *control*
it. Every one of these must return **401**:

```bash
BASE=https://watchtower-283557821298.us-central1.run.app
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: application/json' \
  -d '{"kind":"buffer_spike","title_id":"aurora-drift","region":"MENA","duration_cycles":4,"magnitude":0.8}' \
  $BASE/api/admin/inject
curl -s -o /dev/null -w '%{http_code}\n' -X POST -H 'Content-Type: application/json' \
  -d '{}' $BASE/api/admin/tick
```

Cloud Run invocation and the operator token are two independent gates. Opening the first does not
open the second.

## Continuous integration

`.github/workflows` runs the whole of Levels 1–3 on every push: formatting, linting, the test suite
with coverage, and the real ClickHouse plus MCP integration test.
