import pytest

from watchtower.catalog import REGIONS, TITLES
from watchtower.generator import SyntheticEventGenerator
from watchtower.models import AnomalyInjectionRequest, AnomalyKind
from watchtower.repository import MemoryRepository


def test_generator_covers_original_catalog_and_regions() -> None:
    generator = SyntheticEventGenerator(MemoryRepository())
    events = generator.generate_cycle()
    assert len(events) == len(TITLES) * len(REGIONS)
    assert {event.title_id for event in events} == {title.id for title in TITLES}
    assert all(event.views >= 0 and event.ad_impressions >= 0 for event in events)


def test_buffer_injection_is_labeled_and_concentrated() -> None:
    repository = MemoryRepository()
    generator = SyntheticEventGenerator(repository)
    generator.inject(
        AnomalyInjectionRequest(
            kind=AnomalyKind.BUFFER_SPIKE,
            title_id="aurora-drift",
            region="MENA",
            duration_cycles=2,
            magnitude=0.8,
        )
    )
    target = next(
        event
        for event in generator.generate_cycle()
        if event.title_id == "aurora-drift" and event.region == "MENA"
    )
    assert target.anomaly_tag == AnomalyKind.BUFFER_SPIKE.value
    assert target.buffer_events / target.starts >= 0.18
    assert target.cdn_node == "me-edge-02"


def test_backfill_fills_the_detection_window_with_the_anomaly() -> None:
    """An anomaly present in only the last few cycles is averaged away."""
    repository = MemoryRepository()
    generator = SyntheticEventGenerator(repository)
    request = AnomalyInjectionRequest(
        kind=AnomalyKind.AD_FAILURE,
        title_id="glass-harbor",
        region="Europe",
        duration_cycles=4,
        magnitude=0.8,
    )
    written = generator.backfill_injection(request, lookback_minutes=5, spacing_seconds=15)
    assert written == 20, "five minutes at fifteen-second spacing"

    events = [e for e in repository.events if e.title_id == "glass-harbor"]
    assert len(events) == 20
    assert all(e.region == "Europe" for e in events)
    # Every backfilled row carries the anomaly, so the window average crosses
    # the detection threshold instead of being diluted by normal traffic.
    assert all(e.anomaly_tag == "ad_failure" for e in events)
    rate = sum(e.ad_errors for e in events) / max(
        1, sum(e.ad_impressions + e.ad_errors for e in events)
    )
    assert rate >= 0.12, "must clear the ad-failure detection threshold"


def test_backfill_rejects_a_title_outside_the_fictional_catalog() -> None:
    generator = SyntheticEventGenerator(MemoryRepository())
    request = AnomalyInjectionRequest(
        kind=AnomalyKind.VIEW_DROP, title_id="aurora-drift", region="MENA"
    )
    object.__setattr__(request, "title_id", "not-a-real-title")
    with pytest.raises(ValueError, match="Unknown fictional title_id"):
        generator.backfill_injection(request, lookback_minutes=5)
