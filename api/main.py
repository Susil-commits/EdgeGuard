"""EdgeGuard API — main application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_fastapi_instrumentator import Instrumentator

from api.db import Base, engine
from api.routers import audit, automation, incidents, nodes, telemetry
from api.routers import auth as auth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (Alembic handles migrations in prod)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield


app = FastAPI(
    title="EdgeGuard API",
    description="Hybrid-edge monitoring and self-healing automation platform",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — tighten in production via ALLOWED_ORIGINS env var
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Prometheus metrics at /metrics
Instrumentator().instrument(app).expose(app)

# Routers
app.include_router(auth_router.router, prefix="/v1", tags=["auth"])
app.include_router(nodes.router, prefix="/v1", tags=["nodes"])
app.include_router(telemetry.router, prefix="/v1", tags=["telemetry"])
app.include_router(incidents.router, prefix="/v1", tags=["incidents"])
app.include_router(automation.router, prefix="/v1", tags=["automation"])
app.include_router(audit.router, prefix="/v1", tags=["audit"])


@app.get("/health", tags=["health"])
async def health() -> dict:
    """Health check endpoint. Used by Docker/K8s readiness probes."""
    return {"status": "ok", "version": "0.1.0"}
