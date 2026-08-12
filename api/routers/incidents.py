"""Incident management endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, get_current_user, require_role
from api.db import get_db
from api.models import AuditEvent, Incident
from api.schemas import IncidentResponse, ResolveRequest, ResolveResponse

router = APIRouter()


@router.get(
    "/incidents",
    response_model=list[IncidentResponse],
    summary="List incidents with optional filters",
)
async def list_incidents(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    state: str | None = Query(None, description="Filter by state: open | acknowledged | resolved"),
    severity: str | None = Query(
        None, description="Filter by severity: predictive | warning | critical"
    ),
    node_id: uuid.UUID | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> list[IncidentResponse]:
    q = select(Incident)
    if state:
        q = q.where(Incident.state == state)
    if severity:
        q = q.where(Incident.severity == severity)
    if node_id:
        q = q.where(Incident.node_id == node_id)
    q = q.order_by(Incident.created_at.desc()).limit(limit).offset(offset)

    result = await db.execute(q)
    return [IncidentResponse.model_validate(i) for i in result.scalars().all()]


@router.get(
    "/incidents/{incident_id}",
    response_model=IncidentResponse,
    summary="Get a single incident by ID",
)
async def get_incident(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> IncidentResponse:
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    return IncidentResponse.model_validate(incident)


@router.post(
    "/incidents/{incident_id}/acknowledge",
    response_model=ResolveResponse,
    summary="Acknowledge an open incident (operator+)",
)
async def acknowledge_incident(
    incident_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_role("operator"))],
) -> ResolveResponse:
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.state != "open":
        raise HTTPException(
            status_code=400, detail=f"Cannot acknowledge incident in state '{incident.state}'"
        )

    incident.state = "acknowledged"

    audit = AuditEvent(
        actor_id=user.id,
        action="incident.acknowledge",
        resource_type="incident",
        resource_id=str(incident_id),
        result="success",
    )
    db.add(audit)
    await db.flush()

    return ResolveResponse(id=incident.id, state=incident.state)


@router.post(
    "/incidents/{incident_id}/resolve",
    response_model=ResolveResponse,
    summary="Manually resolve an incident (operator+). Server-side health check enforced.",
)
async def resolve_incident(
    incident_id: uuid.UUID,
    body: ResolveRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_role("operator"))],
) -> ResolveResponse:
    """
    Resolve an incident. The resolution is recorded in audit_events with the
    actor_id so manual vs. automated resolutions are distinguishable.
    """
    result = await db.execute(select(Incident).where(Incident.id == incident_id))
    incident = result.scalar_one_or_none()
    if not incident:
        raise HTTPException(status_code=404, detail="Incident not found")
    if incident.state == "resolved":
        raise HTTPException(status_code=400, detail="Incident is already resolved")

    incident.state = "resolved"
    incident.resolved_at = datetime.now(UTC)

    audit = AuditEvent(
        actor_id=user.id,
        action="incident.resolve",
        resource_type="incident",
        resource_id=str(incident_id),
        result="success",
        detail={"resolution_note": body.resolution_note, "manual": True},
    )
    db.add(audit)
    await db.flush()

    return ResolveResponse(id=incident.id, state=incident.state)
