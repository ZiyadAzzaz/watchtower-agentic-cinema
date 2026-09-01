from __future__ import annotations

from watchtower.models import Anomaly, AnomalyKind, MetricSnapshot


class Detector:
    """Deterministic statistical guardrail before any Gemini invocation."""

    min_views = 60
    min_baseline_views = 30

    def detect(self, snapshot: MetricSnapshot) -> Anomaly | None:
        if (
            snapshot.current_starts < self.min_views
            or snapshot.baseline_views < self.min_baseline_views
        ):
            return None

        candidates: list[Anomaly] = []
        if snapshot.current_views < snapshot.baseline_views * 0.55:
            candidates.append(
                self._anomaly(
                    snapshot,
                    AnomalyKind.VIEW_DROP,
                    snapshot.current_views,
                    snapshot.baseline_views,
                    lower_is_bad=True,
                )
            )
        if snapshot.current_buffer_rate >= 0.08 and snapshot.current_buffer_rate >= max(
            snapshot.baseline_buffer_rate * 2.5, 0.04
        ):
            candidates.append(
                self._anomaly(
                    snapshot,
                    AnomalyKind.BUFFER_SPIKE,
                    snapshot.current_buffer_rate,
                    snapshot.baseline_buffer_rate,
                )
            )
        if snapshot.current_ad_error_rate >= 0.12 and snapshot.current_ad_error_rate >= max(
            snapshot.baseline_ad_error_rate * 3.0, 0.06
        ):
            candidates.append(
                self._anomaly(
                    snapshot,
                    AnomalyKind.AD_FAILURE,
                    snapshot.current_ad_error_rate,
                    snapshot.baseline_ad_error_rate,
                )
            )
        return max(candidates, key=lambda item: item.confidence, default=None)

    @staticmethod
    def _anomaly(
        snapshot: MetricSnapshot,
        kind: AnomalyKind,
        observed: float,
        baseline: float,
        *,
        lower_is_bad: bool = False,
    ) -> Anomaly:
        denominator = max(abs(baseline), 1e-9)
        raw_deviation = (observed - baseline) / denominator
        adverse_deviation = -raw_deviation if lower_is_bad else raw_deviation
        confidence = min(0.99, 0.72 + min(0.27, adverse_deviation * 0.28))
        return Anomaly(
            kind=kind,
            title_id=snapshot.title_id,
            title_name=snapshot.title_name,
            region=snapshot.region,
            observed=observed,
            baseline=baseline,
            deviation_percent=round(raw_deviation * 100, 1),
            confidence=round(confidence, 3),
        )
