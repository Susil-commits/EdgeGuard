"""
Event bus — publishes incident events to Redis pub/sub.

Channel: edgeguard:incidents
Payload: JSON-serialized incident event

The EDA runner (ansible-rulebook) watches a webhook endpoint that this module POSTs to.
Redis pub/sub is also published for any internal consumers.

Architecture decision: the EDA runner uses the webhook source plugin
(ansible.eda.webhook) rather than a Redis source because:
1. It's the standard pattern shown in Red Hat EDA docs
2. It decouples the event bus implementation from the EDA runner
3. It's easier to demo (visible HTTP traffic in logs)
"""

import json
import logging
from datetime import datetime

import httpx
import redis as redis_lib

from api.config import settings
from api.models import Incident

logger = logging.getLogger(__name__)


def _get_redis() -> redis_lib.Redis:
    return redis_lib.from_url(settings.REDIS_URL)


async def publish_incident_event(incident: Incident) -> None:
    """
    Publish an incident event to:
    1. Redis pub/sub channel 'edgeguard:incidents'
    2. EDA webhook endpoint (async HTTP POST)

    Called by the worker after a new incident is created or escalated.
    Errors are caught and logged — a failed publish does not roll back the incident.
    """
    payload = {
        "incident_id": str(incident.id),
        "node_id": str(incident.node_id),
        "severity": incident.severity,
        "rule": incident.rule,
        "state": incident.state,
        "occurrence_count": incident.occurrence_count,
        "metadata": incident.metadata_ or {},
        "published_at": datetime.utcnow().isoformat(),
    }
    payload_json = json.dumps(payload)

    # 1. Redis pub/sub
    try:
        r = _get_redis()
        r.publish("edgeguard:incidents", payload_json)
        logger.debug("Published to Redis channel edgeguard:incidents: %s", incident.id)
    except Exception as e:
        logger.warning("Redis publish failed for incident %s: %s", incident.id, e)

    # 2. EDA webhook POST
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.post(
                settings.EDA_WEBHOOK_URL,
                content=payload_json,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
            logger.debug("EDA webhook accepted incident %s: HTTP %s", incident.id, resp.status_code)
    except Exception as e:
        logger.warning("EDA webhook POST failed for incident %s: %s", incident.id, e)
