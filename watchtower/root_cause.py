from __future__ import annotations

from typing import Any

from watchtower.models import Anomaly, AnomalyKind, RootCause


class RootCauseAnalyzer:
    def analyze(self, anomaly: Anomaly, rows: list[dict[str, Any]]) -> RootCause:
        if not rows:
            return RootCause(
                summary=(
                    "The anomaly is isolated to the title and region, but node evidence is sparse."
                ),
                primary_dimension="region",
                primary_value=anomaly.region,
                evidence=["No current node returned enough samples for a stronger attribution."],
                confidence=0.55,
            )

        ranked = sorted(rows, key=lambda row: self._score(anomaly.kind, row), reverse=True)
        primary = ranked[0]
        node = str(primary.get("cdn_node", "unknown-node"))
        signal_tags = primary.get("signal_tags") or []
        if anomaly.kind == AnomalyKind.BUFFER_SPIKE:
            rate = float(primary.get("buffer_rate") or 0)
            summary = f"Playback degradation is concentrated on CDN node {node}."
            evidence = [
                f"Node buffer-event rate reached {rate:.1%} in the detection window.",
                f"The affected scope is {anomaly.title_name} in {anomaly.region}.",
            ]
        elif anomaly.kind == AnomalyKind.AD_FAILURE:
            rate = float(primary.get("ad_error_rate") or 0)
            summary = f"Ad-delivery errors are concentrated on CDN node {node}."
            evidence = [
                f"Node ad-error rate reached {rate:.1%} in the detection window.",
                f"The affected scope is {anomaly.title_name} in {anomaly.region}.",
            ]
        else:
            views = int(float(primary.get("views") or 0))
            summary = f"The viewership collapse is most visible through CDN node {node}."
            evidence = [
                f"The node delivered only {views:,} views in the detection window.",
                f"The affected scope is {anomaly.title_name} in {anomaly.region}.",
            ]
        if signal_tags:
            evidence.append(f"Synthetic source signal tags: {', '.join(map(str, signal_tags))}.")
        return RootCause(
            summary=summary,
            primary_dimension="cdn_node",
            primary_value=node,
            evidence=evidence,
            confidence=min(0.97, max(0.68, anomaly.confidence + 0.04)),
        )

    @staticmethod
    def _score(kind: AnomalyKind, row: dict[str, Any]) -> float:
        if kind == AnomalyKind.BUFFER_SPIKE:
            return float(row.get("buffer_rate") or 0)
        if kind == AnomalyKind.AD_FAILURE:
            return float(row.get("ad_error_rate") or 0)
        return -float(row.get("views") or 0)
