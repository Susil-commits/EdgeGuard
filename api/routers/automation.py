"""Automation job management endpoints."""

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, get_current_user, require_role
from api.db import get_db
from api.models import AuditEvent, AutomationJob, Incident
from api.schemas import (
    AutomationJobCreateResponse,
    AutomationJobRequest,
    AutomationJobResponse,
    JobResultRequest,
    JobResultResponse,
)
from automation.allowed_playbooks import ALLOWED_PLAYBOOKS

router = APIRouter()


@router.post(
    "/automation/jobs",
    response_model=AutomationJobCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Trigger an automation job (operator+). Playbook must be in the allow-list.",
)
async def create_automation_job(
    body: AutomationJobRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(require_role("operator"))],
) -> AutomationJobCreateResponse:
    """
    Server-side playbook allow-list check — 403 if playbook is not in ALLOWED_PLAYBOOKS.
    This check runs regardless of whether triggered_by is 'manual' or 'eda'.
    """
    if body.playbook not in ALLOWED_PLAYBOOKS:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=(
                f"Playbook '{body.playbook}' is not in the allow-list. "
                f"Allowed: {list(ALLOWED_PLAYBOOKS.keys())}"
            ),
        )

    # Validate incident exists if provided
    if body.incident_id:
        inc_result = await db.execute(select(Incident).where(Incident.id == body.incident_id))
        if not inc_result.scalar_one_or_none():
            raise HTTPException(status_code=404, detail="Incident not found")

    job = AutomationJob(
        incident_id=body.incident_id,
        playbook=body.playbook,
        status="queued",
        triggered_by=body.triggered_by,
    )
    db.add(job)
    await db.flush()

    audit = AuditEvent(
        actor_id=user.id if body.triggered_by == "manual" else "eda",
        action="automation.job.create",
        resource_type="automation_job",
        resource_id=str(job.id),
        result="success",
        detail={"playbook": body.playbook, "triggered_by": body.triggered_by},
    )
    db.add(audit)
    await db.flush()

    # TODO (Phase 7): enqueue ansible-runner job via worker queue
    return AutomationJobCreateResponse(id=job.id, status="queued")


@router.get(
    "/automation/jobs",
    response_model=list[AutomationJobResponse],
    summary="List automation jobs",
)
async def list_jobs(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = 100,
    offset: int = 0,
) -> list[AutomationJobResponse]:
    result = await db.execute(
        select(AutomationJob).order_by(AutomationJob.started_at.desc()).limit(limit).offset(offset)
    )
    return [AutomationJobResponse.model_validate(j) for j in result.scalars().all()]


@router.get(
    "/automation/jobs/{job_id}",
    response_model=AutomationJobResponse,
    summary="Get a single automation job by ID",
)
async def get_job(
    job_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> AutomationJobResponse:
    result = await db.execute(select(AutomationJob).where(AutomationJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Automation job not found")
    return AutomationJobResponse.model_validate(job)


@router.post(
    "/automation/jobs/{job_id}/result",
    response_model=JobResultResponse,
    summary="Callback from ansible-runner — record job result",
)
async def record_job_result(
    job_id: uuid.UUID,
    body: JobResultRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    # This endpoint is called by the EDA runner — uses operator-level service account
    user: Annotated[CurrentUser, Depends(require_role("operator"))],
) -> JobResultResponse:
    result = await db.execute(select(AutomationJob).where(AutomationJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Automation job not found")

    job.status = body.status
    job.finished_at = datetime.now(UTC)
    job.result = {
        "output": body.output,
        "health_verified": body.health_verified,
    }

    # If health verified and job succeeded, auto-resolve the linked incident
    if body.health_verified and body.status == "success" and job.incident_id:
        inc_result = await db.execute(select(Incident).where(Incident.id == job.incident_id))
        incident = inc_result.scalar_one_or_none()
        if incident and incident.state != "resolved":
            incident.state = "resolved"
            incident.resolved_at = datetime.now(UTC)

            audit = AuditEvent(
                actor_id="automation",
                action="incident.resolve",
                resource_type="incident",
                resource_id=str(incident.id),
                result="success",
                detail={"automated": True, "job_id": str(job_id), "health_verified": True},
            )
            db.add(audit)

    await db.flush()
    return JobResultResponse(id=job.id, status=job.status)
