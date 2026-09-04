from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from watchtower.catalog import CDN_NODES, REGIONS, TITLE_BY_ID, TITLES
from watchtower.models import AnomalyInjectionRequest, AnomalyKind, TelemetryEvent
from watchtower.repository import Repository

REGION_FACTOR = {
    "North America": 1.16,
    "Europe": 1.05,
    "MENA": 0.82,
    "South Asia": 1.10,
    "Latin America": 0.91,
}
REGION_UTC_OFFSET = {
    "North America": -5,
    "Europe": 1,
    "MENA": 3,
    "South Asia": 5,
    "Latin America": -3,
}


@dataclass
class ActiveInjection:
    request: AnomalyInjectionRequest
    cycles_remaining: int


class SyntheticEventGenerator:
    def __init__(self, repository: Repository, seed: int = 20260901):
        self.repository = repository
        self.random = random.Random(seed)
        self.injections: dict[tuple[str, str], ActiveInjection] = {}

    def inject(self, request: AnomalyInjectionRequest) -> None:
        self.injections[(request.title_id, request.region)] = ActiveInjection(
            request=request,
            cycles_remaining=request.duration_cycles,
        )

    def generate_cycle(self, at: datetime | None = None) -> list[TelemetryEvent]:
        at = at or datetime.now(UTC)
        events: list[TelemetryEvent] = []
        for title in TITLES:
            for region in REGIONS:
                injection = self.injections.get((title.id, region))
                events.append(
                    self._event(title.id, title.baseline_popularity, region, at, injection)
                )
        for key, injection in list(self.injections.items()):
            injection.cycles_remaining -= 1
            if injection.cycles_remaining <= 0:
                del self.injections[key]
        return events

    def tick(self, at: datetime | None = None) -> int:
        return self.repository.insert_events(self.generate_cycle(at))

    def backfill_injection(
        self,
        request: AnomalyInjectionRequest,
        lookback_minutes: int,
        spacing_seconds: int = 15,
        now: datetime | None = None,
    ) -> int:
        """Fill the live detection window with the armed anomaly.

        Detection compares an average over the lookback window against a
        baseline. An anomaly present in only the last few cycles is averaged
        away by the normal traffic already sitting in that window, so a
        simulation that merely arms the signal can appear to do nothing. A
        simulation control is expected to be immediate and deterministic, so
        the window is written directly for the affected title and region. The
        baseline window is untouched, and detection still reads the result back
        out of ClickHouse exactly as it does for organic traffic.
        """
        now = now or datetime.now(UTC)
        title = TITLE_BY_ID.get(request.title_id)
        if title is None:
            raise ValueError("Unknown fictional title_id.")

        injection = ActiveInjection(request=request, cycles_remaining=request.duration_cycles)
        seconds = max(1, int(lookback_minutes) * 60)
        offsets = range(seconds, 0, -max(1, int(spacing_seconds)))
        events = [
            self._event(
                title.id,
                title.baseline_popularity,
                request.region,
                now - timedelta(seconds=offset),
                injection,
            )
            for offset in offsets
        ]
        return self.repository.insert_events(events)

    def seed_history(self, minutes: int = 75, now: datetime | None = None) -> int:
        now = now or datetime.now(UTC)
        count = 0
        for minutes_ago in range(minutes, 4, -1):
            count += self.tick(now - timedelta(minutes=minutes_ago))
        return count

    def _event(
        self,
        title_id: str,
        popularity: float,
        region: str,
        at: datetime,
        injection: ActiveInjection | None,
    ) -> TelemetryEvent:
        local_hour = (at.hour + REGION_UTC_OFFSET[region]) % 24
        evening_peak = 0.66 + 0.42 * (1 + math.cos((local_hour - 21) * math.pi / 12))
        expected_views = 92 * popularity * REGION_FACTOR[region] * evening_peak
        views = max(12, round(expected_views * self.random.uniform(0.91, 1.09)))
        starts = max(views, round(views * self.random.uniform(1.05, 1.13)))
        completions = round(starts * self.random.uniform(0.72, 0.88))
        buffer_rate = self.random.uniform(0.012, 0.028)
        ad_error_rate = self.random.uniform(0.006, 0.018)
        cdn_node = self.random.choice(CDN_NODES[region])
        anomaly_tag = ""
        if injection:
            request = injection.request
            anomaly_tag = request.kind.value
            if request.kind == AnomalyKind.VIEW_DROP:
                views = max(2, round(views * (1 - request.magnitude)))
                starts = max(views, round(starts * (1 - request.magnitude * 0.9)))
                completions = min(completions, views)
            elif request.kind == AnomalyKind.BUFFER_SPIKE:
                buffer_rate = max(0.18, request.magnitude * 0.42)
                cdn_node = CDN_NODES[region][1]
            elif request.kind == AnomalyKind.AD_FAILURE:
                ad_error_rate = max(0.24, request.magnitude * 0.55)
        buffer_events = round(starts * buffer_rate)
        buffer_seconds = buffer_events * self.random.uniform(4.2, 8.8)
        ad_opportunities = max(1, round(views * self.random.uniform(2.6, 3.8)))
        ad_errors = round(ad_opportunities * ad_error_rate)
        ad_impressions = max(0, ad_opportunities - ad_errors)
        return TelemetryEvent(
            timestamp=at,
            title_id=title_id,
            region=region,
            cdn_node=cdn_node,
            views=views,
            starts=starts,
            completions=completions,
            buffer_events=buffer_events,
            buffer_seconds=round(buffer_seconds, 2),
            ad_impressions=ad_impressions,
            ad_errors=ad_errors,
            anomaly_tag=anomaly_tag,
        )
