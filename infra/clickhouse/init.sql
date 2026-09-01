CREATE DATABASE IF NOT EXISTS watchtower;

CREATE TABLE IF NOT EXISTS watchtower.titles (
  title_id LowCardinality(String),
  name String,
  genre LowCardinality(String),
  description String,
  accent_from FixedString(7),
  accent_to FixedString(7),
  baseline_popularity Float32
) ENGINE = ReplacingMergeTree ORDER BY title_id;

CREATE TABLE IF NOT EXISTS watchtower.telemetry_events (
  event_id UUID,
  event_time DateTime64(3, 'UTC'),
  title_id LowCardinality(String),
  region LowCardinality(String),
  cdn_node LowCardinality(String),
  views UInt32,
  starts UInt32,
  completions UInt32,
  buffer_events UInt32,
  buffer_seconds Float64,
  ad_impressions UInt32,
  ad_errors UInt32,
  anomaly_tag LowCardinality(String)
) ENGINE = MergeTree
PARTITION BY toDate(event_time)
ORDER BY (title_id, region, event_time, event_id)
TTL event_time + INTERVAL 14 DAY DELETE;

CREATE TABLE IF NOT EXISTS watchtower.incidents (
  incident_id UUID,
  status LowCardinality(String),
  severity LowCardinality(String),
  title_id LowCardinality(String),
  region LowCardinality(String),
  created_at DateTime64(3, 'UTC'),
  updated_at DateTime64(3, 'UTC'),
  version UInt32,
  payload String
) ENGINE = ReplacingMergeTree(version)
ORDER BY incident_id;

CREATE USER IF NOT EXISTS watchtower_app IDENTIFIED WITH sha256_password BY 'local-app-only';
CREATE USER IF NOT EXISTS watchtower_mcp IDENTIFIED WITH sha256_password BY 'local-mcp-only';

GRANT SELECT, INSERT ON watchtower.* TO watchtower_app;
GRANT SELECT ON watchtower.* TO watchtower_mcp;
