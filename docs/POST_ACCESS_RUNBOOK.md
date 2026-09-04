# Post-access execution runbook

This is the exact private-release sequence to run when cloud-command approval returns. It targets
`watchtower-507216` explicitly and does not modify billing or the Verity project.

## 1. Lock and verify the target

```powershell
$ErrorActionPreference = "Stop"
gcloud config configurations activate watchtower
$project = gcloud config get-value project
if ($project.Trim() -ne "watchtower-507216") { throw "Wrong Google Cloud project: $project" }
gcloud auth application-default set-quota-project watchtower-507216
```

## 2. Confirm the first-revision diagnosis

```powershell
gcloud run services logs read watchtower `
  --project=watchtower-507216 `
  --region=us-central1 `
  --limit=100
```

Read only the WatchTower service logs. Confirm the first revision failed before listening while
remote initialization was in progress. If the logs identify a different root cause, stop and fix
that cause before deploying.

## 3. Re-run local gates

```powershell
conda activate watch-tower
python -m ruff format --check watchtower tests scripts
python -m ruff check watchtower tests scripts
python -m pytest --cov=watchtower --cov-report=term-missing
git diff --check
```

Expected unit result: 24 passed and one integration test deselected.

## 4. Verify the secret-free Cloud Build context

```powershell
$uploadFiles = gcloud meta list-files-for-upload
if ($uploadFiles -match '(^|[\\/])\.env($|\r?\n)') { throw ".env would be uploaded" }
$uploadFiles
```

The list must not contain `.env`, credentials, internal briefs, or local caches.

## 5. Build the corrected private image

```powershell
$image = "us-central1-docker.pkg.dev/watchtower-507216/watchtower/watchtower:startup-fix-20260902"
gcloud builds submit `
  --project=watchtower-507216 `
  --region=us-central1 `
  --tag=$image `
  .
if ($LASTEXITCODE -ne 0) { throw "Cloud Build failed" }
```

Record the build ID and immutable image digest in `PROJECT_REPORT.md`.

## 6. Deploy privately with fixed limits

```powershell
.\scripts\deploy-cloud-run.ps1 `
  -Image $image `
  -ClickHouseHost "<clickhouse-cloud-host>.us-central1.gcp.clickhouse.cloud"
```

Substitute the real ClickHouse Cloud endpoint from the owner's console. The endpoint is deliberately
not recorded in this public repository: it is password-protected and TLS-verified, but publishing it
would hand an unnecessary target to credential-stuffing traffic.

Do not pass `-AllowPublic`. The script enforces minimum instances 0, maximum instances 1,
concurrency 20, 1 CPU, 512 MiB, verified TLS, Secret Manager, and the dedicated runtime identity.

## 7. Authenticated health and readiness

```powershell
$serviceUrl = gcloud run services describe watchtower `
  --project=watchtower-507216 `
  --region=us-central1 `
  --format="value(status.url)"
$identityToken = gcloud auth print-identity-token
$cloudHeaders = @{ Authorization = "Bearer $identityToken" }

Invoke-RestMethod -Uri "$serviceUrl/api/healthz" -Headers $cloudHeaders

$ready = $false
for ($attempt = 1; $attempt -le 60; $attempt++) {
  try {
    $response = Invoke-RestMethod -Uri "$serviceUrl/readyz" -Headers $cloudHeaders
    if ($response.status -eq "operational") { $ready = $true; break }
  } catch {
    Start-Sleep -Seconds 5
  }
}
if (-not $ready) { throw "WatchTower did not become ready within five minutes" }
```

Cloud Run's frontend answers the exact path `/healthz` itself, so hosted checks must use `/health` or
`/api/healthz`. Both are the same handler; `/healthz` is kept for the local Docker stack.

## 8. Dashboard and authentication rejection

```powershell
$dashboard = Invoke-RestMethod -Uri "$serviceUrl/api/dashboard" -Headers $cloudHeaders
if ($dashboard.titles.Count -ne 12) { throw "Expected 12 fictional titles" }
if ($dashboard.status.environment -ne "production") { throw "Expected production environment" }

$unauthorizedRejected = $false
try {
  Invoke-RestMethod `
    -Method Post `
    -Uri "$serviceUrl/api/admin/inject" `
    -Headers ($cloudHeaders + @{ "Content-Type" = "application/json" }) `
    -Body '{"kind":"buffer_spike","title_id":"aurora-drift","region":"MENA","duration_cycles":4,"magnitude":0.8}'
} catch {
  if ([int]$_.Exception.Response.StatusCode -eq 401) { $unauthorizedRejected = $true }
}
if (-not $unauthorizedRejected) { throw "Missing operator token was not rejected" }
```

## 9. One controlled hosted incident

This retrieves the already-authorized operator token into memory and never prints it.

```powershell
$operatorToken = gcloud secrets versions access latest `
  --secret=watchtower-admin-token `
  --project=watchtower-507216
$adminHeaders = @{
  Authorization = "Bearer $identityToken"
  "X-Watchtower-Token" = $operatorToken.Trim()
  "Content-Type" = "application/json"
}
$incidentBody = @{
  kind = "buffer_spike"
  title_id = "aurora-drift"
  region = "MENA"
  duration_cycles = 4
  magnitude = 0.8
} | ConvertTo-Json

Invoke-RestMethod `
  -Method Post `
  -Uri "$serviceUrl/api/admin/inject" `
  -Headers $adminHeaders `
  -Body $incidentBody

1..3 | ForEach-Object {
  Invoke-RestMethod `
    -Method Post `
    -Uri "$serviceUrl/api/admin/tick" `
    -Headers $adminHeaders `
    -Body '{}'
}
```

## 10. Verify evidence, agents, persistence, and approval

```powershell
$dashboard = Invoke-RestMethod -Uri "$serviceUrl/api/dashboard" -Headers $cloudHeaders
$incident = $dashboard.incidents |
  Where-Object {
    $_.anomaly.title_id -eq "aurora-drift" -and
    $_.anomaly.region -eq "MENA" -and
    $_.status -eq "pending_approval"
  } |
  Select-Object -First 1

if (-not $incident) { throw "Controlled hosted incident was not persisted" }
if ($incident.agent_trace.Count -ne 4) { throw "Expected four agent trace stages" }
if (-not $incident.root_cause.evidence) { throw "Expected MCP-derived evidence" }
if ($incident.impact.affected_sessions -le 0) { throw "Expected quantified impact" }

$decisionBody = @{
  note = "Approved by the human operator during private hosted verification; no action executed."
} | ConvertTo-Json
Invoke-RestMethod `
  -Method Post `
  -Uri "$serviceUrl/api/incidents/$($incident.id)/approve" `
  -Headers $adminHeaders `
  -Body $decisionBody

$verified = Invoke-RestMethod -Uri "$serviceUrl/api/dashboard" -Headers $cloudHeaders
$approved = $verified.incidents | Where-Object { $_.id -eq $incident.id } | Select-Object -First 1
if ($approved.status -ne "approved") { throw "Approval was not persisted" }

$operatorToken = $null
$adminHeaders = $null
```

## 11. Confirm private access and cost limits

```powershell
gcloud run services describe watchtower `
  --project=watchtower-507216 `
  --region=us-central1 `
  --format="yaml(metadata.name,status.url,status.latestReadyRevisionName,spec.template.metadata.annotations,spec.template.spec.containerConcurrency,spec.template.spec.serviceAccountName)"

$policy = gcloud run services get-iam-policy watchtower `
  --project=watchtower-507216 `
  --region=us-central1 `
  --format=json | ConvertFrom-Json
$publicMember = $policy.bindings.members | Where-Object { $_ -in @("allUsers", "allAuthenticatedUsers") }
if ($publicMember) { throw "Private checkpoint failed: public invoker found" }
```

Verify `autoscaling.knative.dev/minScale: '0'`, `autoscaling.knative.dev/maxScale: '1'`, concurrency
20, and the dedicated WatchTower runtime service account. Stop for owner review if Google gross spend
has reached $25, $50, $75, or $80, or ClickHouse spend has reached $100, $200, or $300.

## 12. Documentation, commit, push, and CI

Update `PROJECT_REPORT.md` with the ready revision, private URL, build ID/digest, hosted incident ID,
test evidence, and current owner-reported spend. Do not include the operator token or passwords.

```powershell
git status --short
git diff --check
git add .
git commit -m "Complete private WatchTower deployment"
git push origin main

$run = gh run list `
  --repo ZiyadAzzaz/watchtower-agentic-cinema `
  --limit 1 `
  --json databaseId,status,conclusion,url | ConvertFrom-Json
gh run watch $run.databaseId `
  --repo ZiyadAzzaz/watchtower-agentic-cinema `
  --exit-status
```

## 13. Mandatory stop before publication

Do not make Cloud Run or GitHub public yet. First reconfirm:

- no real third-party media, artwork, title, studio asset, or customer data exists;
- no non-Google AI SDK exists in the shipped runtime or dependency manifests;
- the project is original contest-period work;
- Google and ClickHouse spend remain below their pause/stop checkpoints; and
- the project owner explicitly approves both public Cloud Run invocation and public repository
  visibility.
