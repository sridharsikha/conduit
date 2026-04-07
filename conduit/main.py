"""Conduit — self-serve private networking for any cloud SaaS."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from conduit.api.connections import router as connections_router
from conduit.api.admin import router as admin_router
from conduit.api.billing import router as billing_router
from conduit.api.health import router as health_router
from conduit.config import load_config


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Load config, connect to PG/Redis/Kafka on startup."""
    app.state.config = load_config()
    # TODO: init db pool, redis, kafka producer
    yield
    # TODO: close connections


app = FastAPI(
    title="Conduit",
    description="Self-serve private networking for any cloud SaaS. "
    "Three fields in, private endpoint out.",
    version="0.1.0",
    docs_url="/docs",       # Swagger UI — free API playground
    redoc_url="/redoc",     # ReDoc — clean API reference
    lifespan=lifespan,
)

app.include_router(health_router, tags=["health"])
app.include_router(connections_router, prefix="/api/v1", tags=["connections"])
app.include_router(admin_router, prefix="/api/v1/admin", tags=["admin"])
app.include_router(billing_router, prefix="/api/v1/billing", tags=["billing"])
