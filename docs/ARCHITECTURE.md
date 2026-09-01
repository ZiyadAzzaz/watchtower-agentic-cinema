# WatchTower architecture and trust model

## Operating sequence

1. `SyntheticEventGenerator` emits one event for each fictional title/region pair.
2. `ClickHouseRepository` writes events using the ingestion identity.
3. `WatchtowerRuntime` requests a bounded baseline/current-window query through
   `OfficialClickHouseMcpClient`.
4. The client launches the official `mcp-clickhouse` package over stdio with the read-only identity.
5. `Detector` applies volume floors and adverse-deviation thresholds before any model call.
6. A flagged scope receives a second MCP query grouped by CDN node.
7. `RootCauseAnalyzer` and `ImpactEstimator` create auditable evidence and business calculations.
8. ADK's `SequentialAgent` runs four Gemini agents. The first two re-check evidence through MCP
   tools; the third explains immutable impact values; the fourth produces a structured action draft.
9. The incident is inserted into a `ReplacingMergeTree` in `pending_approval` state.
10. A human may approve or dismiss. The decision inserts a new version; no recommendation executes.

## Data model

### `telemetry_events`

`event_id`, `event_time`, `title_id`, `region`, `cdn_node`, `views`, `starts`, `completions`,
`buffer_events`, `buffer_seconds`, `ad_impressions`, `ad_errors`, `anomaly_tag`.

Events use a 14-day TTL and are ordered for title/region/time-window analytics.

### `incidents`

An append-only versioned record containing status, severity, scope, timestamps, and the complete
validated incident JSON. `argMax(payload, version)` returns the current state.

## Detection rules

- **View drop:** current mean views below 55% of the rolling baseline.
- **Buffer spike:** current rate ≥ 8% and ≥ 2.5× baseline (with a 4% floor).
- **Ad failure:** current error rate ≥ 12% and ≥ 3× baseline (with a 6% floor).
- **Noise floor:** at least 60 playback starts and a baseline of at least 30 mean views.

The thresholds are deliberately inspectable. Gemini cannot create an anomaly or modify the impact
number.

## Business impact

Affected sessions depend on anomaly type. Viewer-hours use a disclosed 41-minute average session.
Estimated revenue combines $0.11 per viewer-hour of retention value and 3.2 ads per session at an
$18 CPM. These are demo assumptions, visible on every incident through the methodology field.

## Security boundaries

| Boundary | Control |
|---|---|
| Wrong cloud project | Production validator accepts only `watchtower-507216` |
| Non-Google AI | Runtime imports Google ADK / Google Gen AI only; policy test scans imports |
| MCP writes | ClickHouse `SELECT` grant only, MCP write flag off, middleware allowlist |
| Query injection | Validated identifiers/literals, fixed windows, explicit row limits |
| Public mutation | Constant-time operator-token check |
| Autonomous action | Action agent has no tools; approve/dismiss only record state |
| Secret leakage | `.env` ignored; production secrets come from Secret Manager |
| Cost growth | min 0, max 1, event-gated Gemini, project budget alerts |

## Failure behavior

- Production fails closed when Gemini, MCP, or ClickHouse is unavailable.
- Development can create a clearly marked deterministic fallback brief for local UI work.
- Duplicate open incidents for the same type/title/region are suppressed.
- An incident cannot be decided twice; subsequent decision attempts return HTTP 409.
