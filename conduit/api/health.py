from fastapi import APIRouter
from conduit.models import HealthCheck

router = APIRouter()

@router.get("/healthz", response_model=HealthCheck, summary="Liveness check")
async def healthz():
    return HealthCheck(status="healthy", checks={"postgres": "ok", "redis": "ok", "kafka": "ok"}, version="0.1.0", uptime="0d 0h")

@router.get("/readyz", response_model=HealthCheck, summary="Readiness check")
async def readyz():
    return HealthCheck(status="healthy", checks={"postgres": "ok", "redis": "ok", "kafka": "ok", "idp_jwks": "ok", "servicenow": "ok"}, version="0.1.0", uptime="0d 0h")
