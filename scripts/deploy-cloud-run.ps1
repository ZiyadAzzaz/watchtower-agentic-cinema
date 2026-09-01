[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Image,

    [Parameter(Mandatory = $true)]
    [string]$ClickHouseHost,

    [string]$Region = "us-central1",
    [switch]$AllowPublic
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectId = "watchtower-507216"
$Service = "watchtower"
$RuntimeIdentity = "watchtower-runtime@$ProjectId.iam.gserviceaccount.com"
$ExpectedSecrets = @(
    "watchtower-clickhouse-app-password",
    "watchtower-clickhouse-mcp-password",
    "watchtower-admin-token"
)

$ResolvedProject = & gcloud projects describe $ProjectId --project=$ProjectId --format="value(projectId)"
if ($LASTEXITCODE -ne 0 -or $ResolvedProject.Trim() -ne $ProjectId) {
    throw "Refusing deployment: target project did not resolve to $ProjectId."
}

foreach ($SecretName in $ExpectedSecrets) {
    & gcloud secrets describe $SecretName --project=$ProjectId --format="value(name)" | Out-Null
    if ($LASTEXITCODE -ne 0) {
        throw "Missing Secret Manager secret: $SecretName"
    }
}

$AuthFlag = if ($AllowPublic) { "--allow-unauthenticated" } else { "--no-allow-unauthenticated" }
if ($AllowPublic) {
    Write-Warning "This release will be public. Continue only after the explicit release checkpoint."
}

$Environment = @(
    "WATCHTOWER_ENV=production",
    "WATCHTOWER_BOOTSTRAP_SCHEMA=false",
    "GOOGLE_CLOUD_PROJECT=$ProjectId",
    "GOOGLE_CLOUD_LOCATION=$Region",
    "GOOGLE_GENAI_USE_VERTEXAI=true",
    "CLICKHOUSE_HOST=$ClickHouseHost",
    "CLICKHOUSE_PORT=8443",
    "CLICKHOUSE_DATABASE=watchtower",
    "CLICKHOUSE_USER=watchtower_app",
    "CLICKHOUSE_MCP_USER=watchtower_mcp",
    "CLICKHOUSE_SECURE=true",
    "CLICKHOUSE_VERIFY=true"
) -join ","

$Secrets = @(
    "CLICKHOUSE_PASSWORD=watchtower-clickhouse-app-password:latest",
    "CLICKHOUSE_MCP_PASSWORD=watchtower-clickhouse-mcp-password:latest",
    "WATCHTOWER_ADMIN_TOKEN=watchtower-admin-token:latest"
) -join ","

& gcloud run deploy $Service `
    --project=$ProjectId `
    --region=$Region `
    --platform=managed `
    --image=$Image `
    --service-account=$RuntimeIdentity `
    --set-env-vars=$Environment `
    --set-secrets=$Secrets `
    --min-instances=0 `
    --max-instances=1 `
    --concurrency=20 `
    --cpu=1 `
    --memory=512Mi `
    --timeout=120 `
    $AuthFlag

if ($LASTEXITCODE -ne 0) {
    throw "Cloud Run deployment failed."
}

& gcloud run services describe $Service `
    --project=$ProjectId `
    --region=$Region `
    --format="yaml(metadata.name,status.url,spec.template.metadata.annotations,spec.template.spec.containerConcurrency)"
