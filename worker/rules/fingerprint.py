"""
Incident fingerprinting and deduplication.

Fingerprint = sha256(node_id + ":" + rule_id)
  - For threshold rules: "threshold:<rule_id>"
  - For predictive rules: "predictive:<rule_id>"

The UNIQUE partial index on (fingerprint) WHERE state = 'open' in Postgres
ensures at-most-one open incident per fingerprint at the DB level.
On a duplicate: increment occurrence_count and update severity if escalated.
"""

import hashlib
import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models import Incident
from worker.rules.threshold import IncidentCandidate

logger = logging.getLogger(__name__)

SEVERITY_ORDER = {"predictive": 0, "warning": 1, "critical": 2}


def make_fingerprint(node_id: str, rule_id: str) -> str:
    """Stable fingerprint for deduplication. Changing this format invalidates open incidents."""
    raw = f"{node_id}:{rule_id}"
    return hashlib.sha256(raw.encode()).hexdigest()


async def upsert_incident(
    db: AsyncSession, candidate: IncidentCandidate
) -> Incident | None:
    """
    Find an open incident with the same fingerprint and increment occurrence_count,
    or create a new one. Returns the incident if created or escalated, None if
    it's a routine increment (to avoid flooding the event bus).
    """
    fingerprint = make_fingerprint(candidate.node_id, candidate.rule_id)

    existing_result = await db.execute(
        select(Incident).where(
            Incident.fingerprint == fingerprint,
            Incident.state == "open",
        )
    )
    existing = existing_result.scalar_one_or_none()

    if existing:
        existing.occurrence_count += 1

        # Escalate severity if the new candidate is higher
        if SEVERITY_ORDER.get(candidate.severity, 0) > SEVERITY_ORDER.get(existing.severity, 0):
            existing.severity = candidate.severity
            logger.info("Incident %s escalated to %s", existing.id, candidate.severity)
            await db.flush()
            return existing  # Return so it's re-published to the event bus

        await db.flush()
        return None  # Routine increment — don't re-publish

    # New incident
    incident = Incident(
        node_id=candidate.node_id,
        fingerprint=fingerprint,
        severity=candidate.severity,
        state="open",
        rule=candidate.rule_id,
        occurrence_count=1,
        metadata_=candidate.metadata,
    )
    db.add(incident)
    await db.flush()
    logger.info(
        "New incident created: node=%s rule=%s severity=%s id=%s",
        candidate.node_id, candidate.rule_id, candidate.severity, incident.id,
    )
    return incident
