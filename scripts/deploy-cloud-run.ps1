[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Image,

    [Parameter(Mandatory = $true)]
    [string]$ClickHouseHost,

    [string]$Region = "us-central1",
    [switch]$AllowPublic,
    [switch]$ForcePrivate
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$ProjectId = "watchtower-507216"
$Service = "watchtower"
$RuntimeIdentity = "watchtower-runtime@$ProjectId.iam.gserviceaccount.com"
$ExpectedSecrets = @(
    "watchtower-clickhouse-app-password",
    "watchtower-clickhouse-mcp-password",
    "watchtower-admin-token",
    "watchtower-demo-token"
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

if ($AllowPublic -and $ForcePrivate) {
    throw "Choose either -AllowPublic or -ForcePrivate, not both."
}

# Deployment must not silently change who may invoke the service. Passing
# --no-allow-unauthenticated by default would revoke public access on every
# routine redeploy of an intentionally public release, so the invoker policy is
# left exactly as it is unless a switch asks for a change.
$AuthFlag = @()
if ($AllowPublic) {
    Write-Warning "This release will be public. Continue only after the explicit release checkpoint."
    $AuthFlag = @("--allow-unauthenticated")
}
elseif ($ForcePrivate) {
    Write-Warning "This release will revoke public invocation and make the service private."
    $AuthFlag = @("--no-allow-unauthenticated")
}
else {
    Write-Host "Invoker policy left unchanged. Use -AllowPublic or -ForcePrivate to change it."
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
    "WATCHTOWER_ADMIN_TOKEN=watchtower-admin-token:latest",
    "WATCHTOWER_DEMO_TOKEN=watchtower-demo-token:latest"
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
    @AuthFlag

if ($LASTEXITCODE -ne 0) {
    throw "Cloud Run deployment failed."
}

& gcloud run services describe $Service `
    --project=$ProjectId `
    --region=$Region `
    --format="yaml(metadata.name,status.url,spec.template.metadata.annotations,spec.template.spec.containerConcurrency)"

& gcloud run services get-iam-policy $Service `
    --project=$ProjectId `
    --region=$Region `
    --format="yaml(bindings)"
