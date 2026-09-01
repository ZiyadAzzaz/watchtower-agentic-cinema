import pytest

from watchtower.detection import Detector
from watchtower.models import AnomalyKind, MetricSnapshot


def snapshot(**overrides) -> MetricSnapshot:
    values = {
        "title_id": "aurora-drift",
        "title_name": "Aurora Drift",
        "region": "MENA",
        "current_views": 100,
        "baseline_views": 105,
        "current_buffer_rate": 0.02,
        "baseline_buffer_rate": 0.018,
        "current_ad_error_rate": 0.01,
        "baseline_ad_error_rate": 0.009,
        "current_starts": 500,
        "current_completions": 420,
    }
    values.update(overrides)
    return MetricSnapshot(**values)


def test_normal_window_is_not_flagged() -> None:
    assert Detector().detect(snapshot()) is None


@pytest.mark.parametrize(
    ("overrides", "kind"),
    [
        ({"current_views": 40}, AnomalyKind.VIEW_DROP),
        ({"current_buffer_rate": 0.22}, AnomalyKind.BUFFER_SPIKE),
        ({"current_ad_error_rate": 0.31}, AnomalyKind.AD_FAILURE),
    ],
)
def test_expected_anomaly_is_flagged(overrides, kind) -> None:
    anomaly = Detector().detect(snapshot(**overrides))
    assert anomaly is not None
    assert anomaly.kind == kind
    assert anomaly.title_id == "aurora-drift"
    assert anomaly.confidence >= 0.72


def test_low_volume_window_is_suppressed() -> None:
    assert Detector().detect(snapshot(current_starts=20, current_buffer_rate=0.5)) is None
