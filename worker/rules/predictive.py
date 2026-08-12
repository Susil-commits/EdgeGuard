"""
EWMA-based predictive rule engine.

Algorithm: Exponentially Weighted Moving Average with trend projection.
Given a history of N metric values and a configurable horizon, project whether
the metric will breach a hard threshold within that horizon.

This is deliberately simple and explainable in an interview:
  - alpha = smoothing factor (0 < alpha < 1; higher = more reactive)
  - trend = rate of change between consecutive EWMA values
  - projected = current EWMA + trend * horizon_minutes
  - If projected >= threshold: raise a 'predictive' severity incident

Why EWMA and not a full ML model:
  - No training data required
  - O(n) time, O(1) space
  - Fully explainable: "It's a smoothed moving average extrapolated forward"
  - Matches the pattern behind Red Hat Insights trending anomaly detection
"""

import logging

from worker.rules.threshold import IncidentCandidate

logger = logging.getLogger(__name__)

# Predictive rules — parallel to threshold rules but with a horizon
PREDICTIVE_RULES = [
    {
        "rule_id": "disk_trend",
        "metric_name": "disk_percent",
        "threshold": 90.0,
        "horizon_minutes": 360,  # 6 hours
        "severity": "predictive",
    },
    {
        "rule_id": "memory_trend",
        "metric_name": "memory_percent",
        "threshold": 95.0,
        "horizon_minutes": 60,  # 1 hour
        "severity": "predictive",
    },
    {
        "rule_id": "cpu_trend",
        "metric_name": "cpu_percent",
        "threshold": 98.0,
        "horizon_minutes": 30,
        "severity": "predictive",
    },
]

ALPHA = 0.3  # EWMA smoothing factor
MIN_HISTORY = 5  # Need at least 5 data points to project


def project_breach(history: list[float], threshold: float, horizon_minutes: int) -> bool:
    """
    Return True if the EWMA trend projects a threshold breach within horizon_minutes.

    history: list of values in DESCENDING time order (newest first)
    threshold: the hard limit to project toward
    horizon_minutes: how far ahead to project
    """
    if len(history) < MIN_HISTORY:
        return False

    # Reverse to chronological order for EWMA calculation
    chronological = list(reversed(history[:60]))  # cap at 60 points

    ewma = chronological[0]
    trend = 0.0
    for v in chronological[1:]:
        new_ewma = ALPHA * v + (1 - ALPHA) * ewma
        trend = new_ewma - ewma
        ewma = new_ewma

    projected = ewma + trend * horizon_minutes
    return projected >= threshold


def check(
    node_id: str,
    metric_name: str,
    history: list[float],
) -> IncidentCandidate | None:
    """
    Run predictive checks for a metric. Returns an IncidentCandidate with
    severity='predictive' if a future breach is projected, or None.
    """
    for rule in PREDICTIVE_RULES:
        if rule["metric_name"] != metric_name:
            continue

        if project_breach(history, rule["threshold"], rule["horizon_minutes"]):
            logger.info(
                "Predictive breach projected: node=%s metric=%s rule=%s",
                node_id, metric_name, rule["rule_id"],
            )
            return IncidentCandidate(
                node_id=node_id,
                rule_id=rule["rule_id"],
                severity="predictive",
                metric_name=metric_name,
                value=history[0] if history else 0.0,
                threshold_value=rule["threshold"],
                metadata={
                    "horizon_minutes": rule["horizon_minutes"],
                    "algorithm": "ewma",
                    "alpha": ALPHA,
                },
            )

    return None
