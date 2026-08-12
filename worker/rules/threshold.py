"""Threshold-based rule engine.

Rules are loaded from THRESHOLD_RULES (environment-configurable YAML in production,
hardcoded defaults here for Phase 5). Each rule defines:
  - metric_name: the metric to watch
  - operator: '>' | '<' | '>=' | '<=' | '=='
  - threshold: the numeric value
  - severity: 'warning' | 'critical'
  - rule_id: unique string identifying the rule (used in fingerprint)
"""

import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class IncidentCandidate:
    node_id: str
    rule_id: str
    severity: str
    metric_name: str
    value: float
    threshold_value: float
    metadata: dict


# Default rules — in production, load from a YAML config file or DB
THRESHOLD_RULES = [
    {
        "rule_id": "cpu_high",
        "metric_name": "cpu_percent",
        "operator": ">=",
        "threshold": 90.0,
        "severity": "warning",
    },
    {
        "rule_id": "cpu_critical",
        "metric_name": "cpu_percent",
        "operator": ">=",
        "threshold": 98.0,
        "severity": "critical",
    },
    {
        "rule_id": "memory_high",
        "metric_name": "memory_percent",
        "operator": ">=",
        "threshold": 85.0,
        "severity": "warning",
    },
    {
        "rule_id": "memory_critical",
        "metric_name": "memory_percent",
        "operator": ">=",
        "threshold": 95.0,
        "severity": "critical",
    },
    {
        "rule_id": "disk_high",
        "metric_name": "disk_percent",
        "operator": ">=",
        "threshold": 80.0,
        "severity": "warning",
    },
    {
        "rule_id": "disk_critical",
        "metric_name": "disk_percent",
        "operator": ">=",
        "threshold": 90.0,
        "severity": "critical",
    },
    {
        "rule_id": "service_inactive",
        "metric_name": "service_active",
        "operator": "==",
        "threshold": 0.0,  # 0 = inactive, 1 = active
        "severity": "critical",
    },
]

_OPERATORS = {
    ">": lambda v, t: v > t,
    "<": lambda v, t: v < t,
    ">=": lambda v, t: v >= t,
    "<=": lambda v, t: v <= t,
    "==": lambda v, t: v == t,
}


def check(
    node_id: str,
    metric_name: str,
    value: float,
) -> IncidentCandidate | None:
    """
    Evaluate all threshold rules against a single metric value.
    Returns the highest-severity matching rule's IncidentCandidate, or None.
    """
    matches: list[IncidentCandidate] = []

    for rule in THRESHOLD_RULES:
        if rule["metric_name"] != metric_name:
            continue

        op_fn = _OPERATORS.get(rule["operator"])
        if op_fn is None:
            logger.warning("Unknown operator '%s' in rule %s", rule["operator"], rule["rule_id"])
            continue

        if op_fn(value, rule["threshold"]):
            matches.append(
                IncidentCandidate(
                    node_id=node_id,
                    rule_id=rule["rule_id"],
                    severity=rule["severity"],
                    metric_name=metric_name,
                    value=value,
                    threshold_value=rule["threshold"],
                    metadata={"operator": rule["operator"], "threshold": rule["threshold"]},
                )
            )

    if not matches:
        return None

    # Return highest severity match (critical > warning)
    severity_order = {"critical": 2, "warning": 1, "predictive": 0}
    return max(matches, key=lambda c: severity_order.get(c.severity, 0))
