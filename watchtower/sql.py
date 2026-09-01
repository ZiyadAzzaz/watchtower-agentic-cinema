from __future__ import annotations

import re

_IDENTIFIER = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]{0,62}$")
_VALUE = re.compile(r"^[a-zA-Z0-9 _-]{1,80}$")


def _identifier(value: str) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise ValueError(f"Unsafe ClickHouse identifier: {value!r}")
    return value


def _literal(value: str) -> str:
    if not _VALUE.fullmatch(value):
        raise ValueError(f"Unsafe ClickHouse filter value: {value!r}")
    return "'" + value.replace("'", "''") + "'"


def detection_query(database: str, lookback_minutes: int, baseline_minutes: int) -> str:
    database = _identifier(database)
    lookback = int(lookback_minutes)
    baseline = int(baseline_minutes)
    if not 2 <= lookback <= 15 or not 20 <= baseline <= 360:
        raise ValueError("Detection query window is outside the approved range.")
    return f"""
WITH
  now64(3, 'UTC') AS anchor,
  current_window AS (
    SELECT
      title_id,
      region,
      avg(views) AS current_views,
      sum(starts) AS current_starts,
      sum(completions) AS current_completions,
      sum(buffer_events) / greatest(sum(starts), 1) AS current_buffer_rate,
      sum(ad_errors) / greatest(sum(ad_impressions) + sum(ad_errors), 1) AS current_ad_error_rate
    FROM {database}.telemetry_events
    WHERE event_time >= anchor - INTERVAL {lookback} MINUTE
    GROUP BY title_id, region
  ),
  baseline_window AS (
    SELECT
      title_id,
      region,
      avg(views) AS baseline_views,
      sum(buffer_events) / greatest(sum(starts), 1) AS baseline_buffer_rate,
      sum(ad_errors) / greatest(sum(ad_impressions) + sum(ad_errors), 1) AS baseline_ad_error_rate
    FROM {database}.telemetry_events
    WHERE event_time >= anchor - INTERVAL {baseline + lookback} MINUTE
      AND event_time < anchor - INTERVAL {lookback} MINUTE
    GROUP BY title_id, region
  )
SELECT
  c.title_id,
  c.region,
  c.current_views,
  b.baseline_views,
  c.current_buffer_rate,
  b.baseline_buffer_rate,
  c.current_ad_error_rate,
  b.baseline_ad_error_rate,
  c.current_starts,
  c.current_completions
FROM current_window AS c
INNER JOIN baseline_window AS b USING (title_id, region)
ORDER BY c.title_id, c.region
LIMIT 200
""".strip()


def root_cause_query(
    database: str,
    title_id: str,
    region: str,
    lookback_minutes: int,
) -> str:
    database = _identifier(database)
    title = _literal(title_id)
    region_value = _literal(region)
    lookback = int(lookback_minutes)
    if not 2 <= lookback <= 15:
        raise ValueError("Root-cause query window is outside the approved range.")
    return f"""
SELECT
  cdn_node,
  sum(views) AS views,
  sum(starts) AS total_starts,
  sum(buffer_events) AS total_buffer_events,
  sum(buffer_seconds) AS buffer_seconds,
  sum(buffer_events) / greatest(sum(starts), 1) AS buffer_rate,
  sum(ad_errors) AS total_ad_errors,
  sum(ad_errors) / greatest(sum(ad_impressions) + sum(ad_errors), 1) AS ad_error_rate,
  groupUniqArrayIf(anomaly_tag, anomaly_tag != '') AS signal_tags
FROM {database}.telemetry_events
WHERE event_time >= now64(3, 'UTC') - INTERVAL {lookback} MINUTE
  AND title_id = {title}
  AND region = {region_value}
GROUP BY cdn_node
ORDER BY buffer_rate DESC, ad_error_rate DESC, views ASC
LIMIT 10
""".strip()


def live_summary_query(database: str) -> str:
    database = _identifier(database)
    return f"""
SELECT
  count() AS event_count,
  sum(views) AS views,
  sum(starts) AS total_starts,
  sum(buffer_events) / greatest(sum(starts), 1) AS buffer_rate,
  sum(ad_impressions) AS ad_impressions,
  max(event_time) AS last_event_at
FROM {database}.telemetry_events
WHERE event_time >= now64(3, 'UTC') - INTERVAL 5 MINUTE
LIMIT 1
""".strip()


def timeseries_query(database: str) -> str:
    database = _identifier(database)
    return f"""
SELECT
  toStartOfMinute(event_time) AS minute,
  sum(views) AS views,
  sum(starts) AS total_starts,
  sum(buffer_events) / greatest(sum(starts), 1) AS buffer_rate
FROM {database}.telemetry_events
WHERE event_time >= now64(3, 'UTC') - INTERVAL 30 MINUTE
GROUP BY minute
ORDER BY minute ASC
LIMIT 30
""".strip()
