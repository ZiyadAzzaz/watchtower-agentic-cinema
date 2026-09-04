# Guarded production deployment

The production target is fixed in code and scripts to `watchtower-507216`. No script reads or
changes the active `gcloud` default project, and no script contains a billing command.

## Required external state

1. A smallest-viable ClickHouse Cloud service funded by the hackathon credit.
2. Database `watchtower`, schema from `infra/clickhouse/init.sql`, an application identity with
   `SELECT, INSERT`, and a separate MCP identity with `SELECT` only.
3. Four Secret Manager secrets: `watchtower-clickhouse-app-password`,
   `watchtower-clickhouse-mcp-password`, `watchtower-admin-token`, and
   `watchtower-demo-token`.
4. An Artifact Registry image built from the checked Dockerfile.

Never reuse the local passwords in `docker-compose.yml`. Generate independent production values.

## Google Cloud preparation

Run `scripts/prepare-google-cloud.ps1`. It enables only Vertex AI, Artifact Registry, Cloud Build,
Cloud Run, and Secret Manager, creates the dedicated runtime identity if necessary, and grants only
Vertex AI User at project scope. Grant Secret Accessor to that identity on each of the four secrets
individually, not at project scope.

## Deploy privately first

```powershell
.\scripts\deploy-cloud-run.ps1 `
  -Image us-central1-docker.pkg.dev/watchtower-507216/watchtower/watchtower:VERSION `
  -ClickHouseHost YOUR_SERVICE.clickhouse.cloud
```

Verify `/healthz`, `/readyz`, the dashboard, a real injected incident, the official MCP trace, and a
human decision while the service requires authentication.

## Public release checkpoint

Only after the private verification and an explicit approval to make the service public, repeat the
deployment with `-AllowPublic`. This is intentionally impossible to do accidentally through the
default command.

The deployment uses request-based Cloud Run billing, min instances 0, max instances 1, concurrency
20, 1 vCPU, and 512 MiB. The application refuses production startup if TLS verification, Vertex AI,
the operator token, scoped credentials, or the exact project ID are missing.

Production remote initialization runs after the process begins listening. `/healthz` confirms that
the web process is alive; `/readyz` and operational APIs return HTTP 503 until ClickHouse
initialization succeeds. Before release, verify authentication rejection, one complete incident,
the MCP-backed trace, a recorded human decision, and the CI result for the deployed commit.

> On Cloud Run use `/health` or `/api/healthz`: Google's serverless frontend answers the exact
> path `/healthz` itself, so that request never reaches the container. All three paths are the
> same handler, and `/readyz`, `/ready`, and `/api/readyz` are likewise equivalent.
