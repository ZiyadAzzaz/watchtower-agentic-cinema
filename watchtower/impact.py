from __future__ import annotations

from watchtower.models import Anomaly, AnomalyKind, ImpactEstimate, MetricSnapshot, Severity


class ImpactEstimator:
    """Auditable business-impact math; Gemini never invents the dollar figure."""

    average_session_minutes = 41.0
    ad_cpm_usd = 18.0
    subscription_value_per_viewer_hour = 0.11

    def estimate(self, anomaly: Anomaly, snapshot: MetricSnapshot) -> ImpactEstimate:
        if anomaly.kind == AnomalyKind.VIEW_DROP:
            affected = max(0, round(snapshot.baseline_views - snapshot.current_views))
        elif anomaly.kind == AnomalyKind.BUFFER_SPIKE:
            excess_rate = max(0.0, snapshot.current_buffer_rate - snapshot.baseline_buffer_rate)
            affected = round(snapshot.current_starts * min(1.0, excess_rate * 2.4))
        else:
            excess_rate = max(0.0, snapshot.current_ad_error_rate - snapshot.baseline_ad_error_rate)
            affected = round(snapshot.current_starts * min(1.0, excess_rate))

        lost_hours = affected * self.average_session_minutes / 60
        lost_ads = affected * 3.2
        revenue_loss = lost_hours * self.subscription_value_per_viewer_hour + (
            lost_ads / 1000 * self.ad_cpm_usd
        )
        severity = self._severity(affected, revenue_loss, anomaly.confidence)
        return ImpactEstimate(
            lost_viewer_hours=round(lost_hours, 1),
            estimated_revenue_loss_usd=round(revenue_loss, 2),
            affected_sessions=affected,
            severity=severity,
            methodology=(
                "Affected sessions x 41-minute average session; revenue combines "
                "$0.11/viewer-hour retention value and 3.2 ads/session at $18 CPM."
            ),
        )

    @staticmethod
    def _severity(affected: int, loss: float, confidence: float) -> Severity:
        score = affected * confidence + loss * 4
        if score >= 900:
            return Severity.CRITICAL
        if score >= 400:
            return Severity.HIGH
        if score >= 120:
            return Severity.MEDIUM
        return Severity.LOW
