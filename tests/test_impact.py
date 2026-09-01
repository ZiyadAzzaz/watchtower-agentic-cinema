from tests.test_detection import snapshot
from watchtower.impact import ImpactEstimator
from watchtower.models import Anomaly, AnomalyKind


def anomaly(kind: AnomalyKind) -> Anomaly:
    return Anomaly(
        kind=kind,
        title_id="aurora-drift",
        title_name="Aurora Drift",
        region="MENA",
        observed=0.2,
        baseline=0.02,
        deviation_percent=900,
        confidence=0.92,
    )


def test_impact_is_numeric_auditable_and_monotonic() -> None:
    estimator = ImpactEstimator()
    small = estimator.estimate(
        anomaly(AnomalyKind.BUFFER_SPIKE),
        snapshot(current_starts=200, current_buffer_rate=0.2),
    )
    large = estimator.estimate(
        anomaly(AnomalyKind.BUFFER_SPIKE),
        snapshot(current_starts=2000, current_buffer_rate=0.35),
    )
    assert small.lost_viewer_hours > 0
    assert small.estimated_revenue_loss_usd > 0
    assert large.estimated_revenue_loss_usd > small.estimated_revenue_loss_usd
    assert "$0.11/viewer-hour" in large.methodology
