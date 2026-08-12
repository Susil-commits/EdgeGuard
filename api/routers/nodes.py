"""Node registration and fleet management endpoints."""

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth import CurrentUser, get_current_user
from api.db import get_db
from api.models import Node
from api.schemas import NodeRegisterRequest, NodeRegisterResponse, NodeResponse

router = APIRouter()


@router.post(
    "/nodes/register",
    response_model=NodeRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new edge node",
)
async def register_node(
    body: NodeRegisterRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> NodeRegisterResponse:
    """
    Register an edge node. Called by the agent on first start or after re-imaging.
    If the hostname already exists, returns the existing node ID (idempotent).
    """
    existing = await db.execute(select(Node).where(Node.hostname == body.hostname))
    node = existing.scalar_one_or_none()

    if node:
        return NodeRegisterResponse(id=node.id, status="already_registered")

    node = Node(
        hostname=body.hostname,
        site=body.site,
        environment=body.environment,
        os=body.os,
        agent_version=body.agent_version,
        status="registered",
    )
    db.add(node)
    await db.flush()
    return NodeRegisterResponse(id=node.id, status="registered")


@router.get(
    "/nodes",
    response_model=list[NodeResponse],
    summary="List all registered nodes",
)
async def list_nodes(
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = 100,
    offset: int = 0,
) -> list[NodeResponse]:
    result = await db.execute(select(Node).limit(limit).offset(offset))
    nodes = result.scalars().all()
    return [NodeResponse.model_validate(n) for n in nodes]


@router.get(
    "/nodes/{node_id}",
    response_model=NodeResponse,
    summary="Get a single node by ID",
)
async def get_node(
    node_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    user: Annotated[CurrentUser, Depends(get_current_user)],
) -> NodeResponse:
    result = await db.execute(select(Node).where(Node.id == node_id))
    node = result.scalar_one_or_none()
    if not node:
        raise HTTPException(status_code=404, detail="Node not found")
    return NodeResponse.model_validate(node)
