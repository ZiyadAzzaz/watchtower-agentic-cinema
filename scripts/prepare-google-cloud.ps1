[CmdletBinding()]
param([string]$Region = "us-central1")

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectId = "watchtower-507216"
$ServiceAccountName = "watchtower-runtime"
$ServiceAccount = "$ServiceAccountName@$ProjectId.iam.gserviceaccount.com"
$Apis = @(
    "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "run.googleapis.com",
    "secretmanager.googleapis.com"
)

$ResolvedProject = & gcloud projects describe $ProjectId --project=$ProjectId --format="value(projectId)"
if ($LASTEXITCODE -ne 0 -or $ResolvedProject.Trim() -ne $ProjectId) {
    throw "Refusing setup: target project did not resolve to $ProjectId."
}

& gcloud services enable @Apis --project=$ProjectId
if ($LASTEXITCODE -ne 0) {
    throw "Required API enablement failed."
}

& gcloud iam service-accounts describe $ServiceAccount --project=$ProjectId | Out-Null
if ($LASTEXITCODE -ne 0) {
    & gcloud iam service-accounts create $ServiceAccountName `
        --project=$ProjectId `
        --display-name="WatchTower Cloud Run runtime"
    if ($LASTEXITCODE -ne 0) {
        throw "Runtime service-account creation failed."
    }
}

& gcloud projects add-iam-policy-binding $ProjectId `
    --project=$ProjectId `
    --member="serviceAccount:$ServiceAccount" `
    --role="roles/aiplatform.user" `
    --condition=None | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Vertex AI role binding failed."
}

Write-Output "Prepared $ProjectId in $Region."
Write-Output "Secrets and per-secret accessor grants are intentionally deferred until real ClickHouse Cloud credentials exist."
