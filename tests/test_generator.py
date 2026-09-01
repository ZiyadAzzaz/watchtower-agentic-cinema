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
