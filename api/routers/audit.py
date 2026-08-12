"""Audit log read endpoint."""

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, get_current_user
from api.db import get_db
from api.models import AuditEvent
from api.schemas import AuditEventResponse

router = APIRouter()


@router.get(
    "/audit",
    response_model=list[AuditEventResponse],
    summary="Read the audit event log (all authenticated users)",
)
async def list_audit_events(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    action: str | None = Query(
        None, description="Filter by action string, e.g. 'incident.resolve'"
    ),
    actor_id: str | None = Query(None),
    limit: int = Query(100, le=500),
    offset: int = 0,
) -> list[AuditEventResponse]:
    q = select(AuditEvent).order_by(AuditEvent.timestamp.desc())
    if action:
        q = q.where(AuditEvent.action == action)
    if actor_id:
        q = q.where(AuditEvent.actor_id == actor_id)
    q = q.limit(limit).offset(offset)

    result = await db.execute(q)
    return [AuditEventResponse.model_validate(e) for e in result.scalars().all()]
