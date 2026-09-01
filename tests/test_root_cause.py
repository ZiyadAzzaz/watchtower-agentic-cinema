from watchtower.models import Anomaly, AnomalyKind
from watchtower.root_cause import RootCauseAnalyzer


def test_root_cause_selects_worst_buffering_node() -> None:
    anomaly = Anomaly(
        kind=AnomalyKind.BUFFER_SPIKE,
        title_id="aurora-drift",
        title_name="Aurora Drift",
        region="MENA",
        observed=0.25,
        baseline=0.02,
        deviation_percent=1150,
        confidence=0.94,
    )
    result = RootCauseAnalyzer().analyze(
        anomaly,
        [
            {"cdn_node": "me-edge-01", "buffer_rate": 0.03},
            {
                "cdn_node": "me-edge-02",
                "buffer_rate": 0.31,
                "signal_tags": ["buffer_spike"],
            },
        ],
    )
    assert result.primary_value == "me-edge-02"
    assert result.confidence >= anomaly.confidence
    assert any("31.0%" in item for item in result.evidence)
