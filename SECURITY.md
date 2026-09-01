# Security policy

Please report vulnerabilities privately to the repository owner rather than opening a public issue.

Do not include credentials, service URLs containing secrets, customer data, or exploit payloads in a
public report. WatchTower's intended deployment uses separate ClickHouse identities, verified TLS,
Secret Manager, a dedicated Cloud Run service account, an operator token, and no action-execution
tools.

Supported version: the latest commit on `main` during the 2026 hackathon period.
