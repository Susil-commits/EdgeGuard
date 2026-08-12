"""SQLAlchemy ORM models for all EdgeGuard database tables.

Uses dialect-agnostic column types:
  - String(36) for UUIDs (works on both SQLite and PostgreSQL)
  - JSON for json blobs (SQLite uses TEXT, PostgreSQL uses JSON)

For production PostgreSQL deployments, Alembic migrations can upgrade these
to native UUID/JSONB types for better performance.
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from api.db import Base


def utcnow() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

class Node(Base):
    __tablename__ = "nodes"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    hostname: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    site: Mapped[str] = mapped_column(String(255), nullable=True)
    environment: Mapped[str] = mapped_column(String(100), nullable=True)
    os: Mapped[str] = mapped_column(String(255), nullable=True)
    agent_version: Mapped[str] = mapped_column(String(50), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="registered")
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=True, onupdate=utcnow
    )

    metrics: Mapped[list["Metric"]] = relationship(back_populates="node", cascade="all, delete")
    incidents: Mapped[list["Incident"]] = relationship(back_populates="node", cascade="all, delete")


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

class Metric(Base):
    __tablename__ = "metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )
    event_id: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    metric_name: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[float] = mapped_column(nullable=False)
    labels: Mapped[dict] = mapped_column(JSON, nullable=True, default=dict)

    node: Mapped["Node"] = relationship(back_populates="metrics")

    __table_args__ = (
        Index("ix_metrics_node_timestamp", "node_id", "timestamp"),
        Index("ix_metrics_name_timestamp", "metric_name", "timestamp"),
    )


# ---------------------------------------------------------------------------
# Incidents
# ---------------------------------------------------------------------------

class Incident(Base):
    __tablename__ = "incidents"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    node_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("nodes.id", ondelete="CASCADE"), nullable=False
    )
    fingerprint: Mapped[str] = mapped_column(String(255), nullable=False)
    # severity: 'predictive' | 'warning' | 'critical'
    severity: Mapped[str] = mapped_column(String(50), nullable=False)
    # state: 'open' | 'acknowledged' | 'resolved'
    state: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    rule: Mapped[str] = mapped_column(String(255), nullable=False)
    occurrence_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    metadata_: Mapped[dict] = mapped_column("metadata", JSON, nullable=True, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
    resolved_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)

    node: Mapped["Node"] = relationship(back_populates="incidents")
    automation_jobs: Mapped[list["AutomationJob"]] = relationship(
        back_populates="incident", cascade="all, delete"
    )

    __table_args__ = (
        Index("ix_incidents_fingerprint_state", "fingerprint", "state"),
    )


# ---------------------------------------------------------------------------
# Automation Jobs
# ---------------------------------------------------------------------------

class AutomationJob(Base):
    __tablename__ = "automation_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    incident_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("incidents.id", ondelete="CASCADE"),
        nullable=True,
    )
    playbook: Mapped[str] = mapped_column(String(255), nullable=False)
    # status: 'queued' | 'running' | 'success' | 'failed'
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="queued")
    # triggered_by: 'eda' | 'manual'
    triggered_by: Mapped[str] = mapped_column(String(50), nullable=False, default="manual")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, nullable=True)

    incident: Mapped["Incident"] = relationship(back_populates="automation_jobs")


# ---------------------------------------------------------------------------
# Audit Events
# ---------------------------------------------------------------------------

class AuditEvent(Base):
    __tablename__ = "audit_events"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    actor_id: Mapped[str] = mapped_column(String(255), nullable=False)
    action: Mapped[str] = mapped_column(String(255), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(100), nullable=True)
    resource_id: Mapped[str] = mapped_column(String(255), nullable=True)
    result: Mapped[str] = mapped_column(String(50), nullable=False, default="success")
    detail: Mapped[dict] = mapped_column(JSON, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )


# ---------------------------------------------------------------------------
# Users (local auth — swapped for Keycloak in Phase 13)
# ---------------------------------------------------------------------------

class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="viewer")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow
    )
