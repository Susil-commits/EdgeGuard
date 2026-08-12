"""Pydantic request/response schemas for all EdgeGuard API endpoints."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------


class NodeRegisterRequest(BaseModel):
    hostname: str = Field(..., min_length=1, max_length=255)
    site: str | None = None
    environment: str | None = None
    os: str | None = None
    agent_version: str | None = None


class NodeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    hostname: str
    site: str | None
    environment: str | None
    os: str | None
    agent_version: str | None
    status: str
    last_seen: datetime | None


class NodeRegisterResponse(BaseModel):
    id: uuid.UUID
    status: str


# ---------------------------------------------------------------------------
# Telemetry
# ---------------------------------------------------------------------------


class MetricPoint(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    value: float
    labels: dict[str, Any] = Field(default_factory=dict)


class TelemetryRequest(BaseModel):
    node_id: uuid.UUID
    timestamp: datetime
    metrics: list[MetricPoint] = Field(..., min_length=1)
    event_id: str = Field(..., min_length=1, max_length=255, description="Idempotency key")


class TelemetryResponse(BaseModel):
    accepted: bool
    event_id: str


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------


class IncidentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    node_id: uuid.UUID
    fingerprint: str
    severity: str
    state: str
    rule: str
    occurrence_count: int
    created_at: datetime
    resolved_at: datetime | None


class ResolveRequest(BaseModel):
    resolution_note: str | None = None


class ResolveResponse(BaseModel):
    id: uuid.UUID
    state: str


# ---------------------------------------------------------------------------
# Automation Jobs
# ---------------------------------------------------------------------------


class AutomationJobRequest(BaseModel):
    incident_id: uuid.UUID | None = None
    playbook: str = Field(..., min_length=1, max_length=255)
    params: dict[str, Any] = Field(default_factory=dict)
    triggered_by: str = Field("manual", pattern="^(eda|manual)$")


class AutomationJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    incident_id: uuid.UUID | None
    playbook: str
    status: str
    triggered_by: str
    started_at: datetime | None
    finished_at: datetime | None
    result: dict | None


class AutomationJobCreateResponse(BaseModel):
    id: uuid.UUID
    status: str


class JobResultRequest(BaseModel):
    status: str = Field(..., pattern="^(success|failed)$")
    output: str | None = None
    health_verified: bool = False


class JobResultResponse(BaseModel):
    id: uuid.UUID
    status: str


# ---------------------------------------------------------------------------
# Audit
# ---------------------------------------------------------------------------


class AuditEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor_id: str
    action: str
    resource_type: str | None
    resource_id: str | None
    result: str
    timestamp: datetime


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str
    password: str
