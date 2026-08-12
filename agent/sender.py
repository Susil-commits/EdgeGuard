"""
Agent telemetry sender — HTTPS POST to EdgeGuard API with retry/backoff.

Flow:
  1. Write event to spool (durable, survives crashes)
  2. Attempt POST to API
  3. On success: mark spool entry sent
  4. On failure: leave in spool; next drain cycle will retry

On startup/reconnect, drain() replays all unsent spool entries.
The API's idempotent event_id guarantees no duplicate metric rows.
"""

import logging
import os
import time
import uuid
from datetime import UTC, datetime

import httpx

from agent import spool
from agent.collector import MetricPoint

logger = logging.getLogger(__name__)

API_URL = os.environ.get("EDGEGUARD_API_URL", "https://localhost:8443")
NODE_ID = os.environ.get("NODE_ID", "")
AGENT_TOKEN = os.environ.get("AGENT_TOKEN", "")

MAX_RETRIES = 5
INITIAL_BACKOFF_S = 2.0
BACKOFF_MULTIPLIER = 2.0
MAX_BACKOFF_S = 60.0


def send_metrics(metrics: list[MetricPoint]) -> bool:
    """
    Send a batch of metrics to the API.
    Returns True on success, False if the batch was spooled for later retry.
    """
    event_id = str(uuid.uuid4())
    payload = {
        "node_id": NODE_ID,
        "timestamp": datetime.now(UTC).isoformat(),
        "metrics": [
            {"name": m.name, "value": m.value, "labels": m.labels}
            for m in metrics
        ],
        "event_id": event_id,
    }

    # Write to spool FIRST — ensures durability before network attempt
    spool.enqueue(event_id, payload)

    success = _post_with_retry(event_id, payload)
    if success:
        spool.mark_sent(event_id)
    return success


def replay_spool() -> tuple[int, int]:
    """
    Attempt to send all unsent spool entries.
    Returns (sent_count, failed_count).
    """
    entries = spool.drain()
    sent = 0
    failed = 0
    for event_id, payload in entries:
        if _post_with_retry(event_id, payload, max_retries=1):
            spool.mark_sent(event_id)
            sent += 1
        else:
            failed += 1
    if entries:
        logger.info("Spool replay: %d sent, %d still pending", sent, failed)
    return sent, failed


def _post_with_retry(event_id: str, payload: dict, max_retries: int = MAX_RETRIES) -> bool:
    """POST payload to /v1/telemetry with exponential backoff. Returns True on success."""
    backoff = INITIAL_BACKOFF_S
    headers = {
        "Authorization": f"Bearer {AGENT_TOKEN}",
        "Content-Type": "application/json",
        "X-Event-ID": event_id,
    }

    for attempt in range(1, max_retries + 1):
        try:
            with httpx.Client(timeout=10.0, verify=True) as client:
                resp = client.post(f"{API_URL}/v1/telemetry", json=payload, headers=headers)
                if resp.status_code == 202:
                    logger.debug("Telemetry accepted: event_id=%s", event_id)
                    return True
                elif resp.status_code == 409:
                    # Already received — idempotent, treat as success
                    logger.debug("Duplicate event_id=%s ignored by server", event_id)
                    return True
                else:
                    logger.warning(
                        "Unexpected status %s for event_id=%s (attempt %d/%d)",
                        resp.status_code, event_id, attempt, max_retries,
                    )
        except httpx.RequestError as e:
            logger.warning(
                "Network error sending event_id=%s (attempt %d/%d): %s",
                event_id, attempt, max_retries, e,
            )

        if attempt < max_retries:
            sleep_time = min(backoff, MAX_BACKOFF_S)
            logger.debug("Retrying in %.1fs...", sleep_time)
            time.sleep(sleep_time)
            backoff *= BACKOFF_MULTIPLIER

    return False
