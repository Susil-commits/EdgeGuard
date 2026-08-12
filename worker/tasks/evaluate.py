"""Rule evaluation entrypoint — called by RQ worker for each telemetry batch."""

import asyncio
import logging

from sqlalchemy import select

from api.db import AsyncSessionLocal
from api.models import Metric, Node
from worker.eventbus import publish_incident_event
from worker.rules import fingerprint, predictive, threshold

logger = logging.getLogger(__name__)


def run_evaluation(node_id: str) -> None:
    """
    RQ task entrypoint (sync wrapper around async logic).
    Runs threshold + predictive checks and upserts incidents.
    """
    asyncio.run(_evaluate(node_id))


async def _evaluate(node_id: str) -> None:
    async with AsyncSessionLocal() as db:
        # Fetch the node
        node_result = await db.execute(select(Node).where(Node.id == node_id))
        node = node_result.scalar_one_or_none()
        if not node:
            logger.warning("Evaluation requested for unknown node %s", node_id)
            return

        # Fetch last 60 metric readings per metric name for this node
        metrics_result = await db.execute(
            select(Metric)
            .where(Metric.node_id == node_id)
            .order_by(Metric.timestamp.desc())
            .limit(500)
        )
        all_metrics = metrics_result.scalars().all()

        # Group by metric name
        by_name: dict[str, list[float]] = {}
        for m in all_metrics:
            by_name.setdefault(m.metric_name, []).append(m.value)

        for metric_name, history in by_name.items():
            # Most-recent value is history[0] (DESC order)
            latest_value = history[0]

            # --- Hard threshold check ---
            threshold_incident = threshold.check(
                node_id=node_id,
                metric_name=metric_name,
                value=latest_value,
            )
            if threshold_incident:
                incident = await fingerprint.upsert_incident(db, threshold_incident)
                if incident:
                    await publish_incident_event(incident)

            # --- Predictive (EWMA) check ---
            predictive_incident = predictive.check(
                node_id=node_id,
                metric_name=metric_name,
                history=history,
            )
            if predictive_incident:
                incident = await fingerprint.upsert_incident(db, predictive_incident)
                if incident:
                    await publish_incident_event(incident)

        await db.commit()
