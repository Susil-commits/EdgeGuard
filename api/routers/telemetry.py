"""Telemetry ingestion endpoint — receives metric batches from agents."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from api.db import get_db
from api.models import Metric, Node
from api.schemas import TelemetryRequest, TelemetryResponse
from worker.queue import enqueue_evaluation

router = APIRouter()


@router.post(
    "/telemetry",
    response_model=TelemetryResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Ingest a batch of metrics from an edge node agent",
)
async def ingest_telemetry(
    body: TelemetryRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> TelemetryResponse:
    """
    Idempotent telemetry ingestion. Each metric point in the batch shares the
    batch event_id combined with metric name as the unique key to prevent duplicates
    on agent replay after a WAN outage.

    After writing, enqueues a rule-evaluation job for the worker.
    """
    # Verify node exists
    node_result = await db.execute(select(Node).where(Node.id == body.node_id))
    node = node_result.scalar_one_or_none()
    if not node:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Node {body.node_id} not found. Register the node first.",
        )

    # Update last_seen on the node
    node.last_seen = datetime.now(UTC)
    node.status = "online"

    # Upsert each metric point — ON CONFLICT DO NOTHING (idempotent)
    for point in body.metrics:
        # Compound event_id: batch_event_id + metric_name ensures uniqueness per metric per batch
        compound_event_id = f"{body.event_id}:{point.name}"
        stmt = (
            pg_insert(Metric)
            .values(
                node_id=body.node_id,
                event_id=compound_event_id,
                timestamp=body.timestamp,
                metric_name=point.name,
                value=point.value,
                labels=point.labels,
            )
            .on_conflict_do_nothing(index_elements=["event_id"])
        )
        await db.execute(stmt)

    await db.flush()

    # Enqueue rule evaluation for this node (fire-and-forget; worker picks it up)
    try:
        enqueue_evaluation(node_id=str(body.node_id))
    except Exception:
        # If Redis is unavailable, don't fail the ingestion — data is safe in Postgres
        pass

    return TelemetryResponse(accepted=True, event_id=body.event_id)
