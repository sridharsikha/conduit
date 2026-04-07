"""Developer API — POST /connections, GET /connections, DELETE /connections/{id}."""

from __future__ import annotations
from datetime import datetime, timezone
from uuid import uuid4
from fastapi import APIRouter, Request, Response, HTTPException, Header
from conduit.models import (
    ConnectionRequest, ConnectionResponse, PendingResponse,
    StatusResponse, RevokedResponse, PendingRevocationResponse,
    EndpointInfo, ResolvedContext, EnvVars, BillingProjection, Status,
)
from conduit.resolver import resolve, ResolutionError

router = APIRouter()

# In-memory store for MVP. Replace with PostgreSQL.
_connections: dict[str, dict] = {}


@router.post(
    "/connections",
    response_model=ConnectionResponse | PendingResponse,
    status_code=200,
    summary="Request a private connection",
    description="Developer's primary API. Three required fields: service, environment, bandwidth_mbps. "
    "Returns 200 (auto-approved) or 202 (pending SNOW approval).",
)
async def create_connection(req: ConnectionRequest, request: Request):
    config = request.app.state.config

    # Extract SSO claims (MVP: mock from header)
    sso_groups = request.headers.get("X-SSO-Groups", "eng-commerce").split(",")

    # Three-plane resolution
    try:
        resolved = resolve(config, sso_groups, req.service, req.environment)
    except ResolutionError as e:
        raise HTTPException(status_code=e.code, detail=e.detail)

    # Policy: auto-approve dev/qa, SNOW for perf/prod
    is_auto = req.environment in ("dev", "qa")

    lifecycle = req.lifecycle or config.lifecycle_defaults.get(req.environment, "always_on")

    if is_auto:
        conn_id = f"conn-{uuid4().hex[:8]}"
        endpoints = []
        for loc in resolved.locations:
            infra = resolved.infra[f"{loc.csp}/{loc.region}"]
            ep_id = f"{'vpce' if loc.csp == 'aws' else 'pe' if loc.csp == 'azure' else 'psc'}-{uuid4().hex[:8]}"
            endpoints.append(EndpointInfo(
                csp=loc.csp, region=loc.region,
                bootstrap=f"{loc.cluster}.{loc.region}.{loc.csp}.confluent.cloud:9092",
                private_ip=f"10.{hash(loc.region) % 255}.1.{hash(conn_id) % 255}",
                endpoint_id=ep_id,
                connection_type="PrivateLink" if loc.csp == "aws" else "Private Endpoint" if loc.csp == "azure" else "PSC",
            ))

        resp = ConnectionResponse(
            connection_id=conn_id, service=req.service, environment=req.environment,
            lifecycle=lifecycle,
            resolved=ResolvedContext(
                team=resolved.identity.team, cost_center=resolved.identity.cost_center,
                approval="auto", saas_provider=resolved.locations[0].saas,
            ),
            connections=endpoints,
            env_vars=EnvVars(
                KAFKA_BOOTSTRAP_SERVERS=",".join(e.bootstrap for e in endpoints),
                KAFKA_API_KEY="XXXXXXXXXXXXXXXX", KAFKA_API_SECRET="********",
                KAFKA_SECURITY_PROTOCOL="SASL_SSL", KAFKA_SASL_MECHANISM="PLAIN",
            ),
            billing=BillingProjection(projected_monthly=f"${len(endpoints) * 71.40:.2f}"),
            created_at=datetime.now(timezone.utc),
        )
        _connections[conn_id] = {"response": resp, "status": Status.active}
        return resp

    else:
        req_id = f"REQ-{uuid4().hex[:4].upper()}"
        resp = PendingResponse(
            request_id=req_id, snow_ritm=f"RITM004{uuid4().hex[:4].upper()}",
            approver=resolved.identity.approvers[0] if resolved.identity.approvers else "unknown",
            reason=f"{req.environment.capitalize()} environment requires manager approval",
            poll_url=f"/api/v1/connections/{req_id}/status",
        )
        _connections[req_id] = {"response": resp, "status": Status.pending_approval, "resolved": resolved}
        return Response(content=resp.model_dump_json(), status_code=202, media_type="application/json")


@router.get("/connections", summary="List my connections")
async def list_connections(status: str = "active", service: str | None = None, environment: str | None = None):
    results = []
    for cid, data in _connections.items():
        if hasattr(data.get("response"), "connection_id"):
            results.append({"connection_id": cid, "status": data["status"]})
    return {"connections": results, "total": len(results)}


@router.get("/connections/{conn_id}/status", response_model=StatusResponse, summary="Poll approval status")
async def get_status(conn_id: str):
    if conn_id not in _connections:
        raise HTTPException(404, f"Connection {conn_id} not found")
    data = _connections[conn_id]
    return StatusResponse(status=data["status"])


@router.get("/connections/{conn_id}/env", summary="Get env vars for code integration")
async def get_env(conn_id: str, format: str = "json"):
    if conn_id not in _connections:
        raise HTTPException(404, f"Connection {conn_id} not found")
    data = _connections[conn_id]
    resp = data.get("response")
    if not hasattr(resp, "env_vars"):
        raise HTTPException(409, "Connection not yet active")
    env = resp.env_vars.model_dump(exclude_none=True)

    if format == "dotenv":
        body = "\n".join(f"{k}={v}" for k, v in env.items())
        return Response(content=body, media_type="text/plain")
    elif format == "k8s-configmap":
        body = f"apiVersion: v1\nkind: ConfigMap\nmetadata:\n  name: kafka-config-{conn_id}\ndata:\n"
        body += "\n".join(f"  {k}: \"{v}\"" for k, v in env.items())
        return Response(content=body, media_type="text/yaml")
    return env


@router.delete("/connections/{conn_id}", summary="Revoke a connection")
async def delete_connection(conn_id: str, x_step_up: str | None = Header(None)):
    if conn_id not in _connections:
        raise HTTPException(404, f"Connection {conn_id} not found")
    data = _connections[conn_id]
    resp = data.get("response")
    env = resp.environment if hasattr(resp, "environment") else "dev"

    if env in ("perf", "staging") and not x_step_up:
        raise HTTPException(401, detail={
            "error": "MFA_REQUIRED",
            "step_up_url": "https://acme.okta.com/mfa/challenge?session=...",
        })

    if env == "prod":
        from datetime import timedelta
        return PendingRevocationResponse(
            snow_chg=f"CHG005{uuid4().hex[:4].upper()}",
            teardown_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            cancel_url=f"/api/v1/connections/{conn_id}/cancel-delete",
        )

    data["status"] = Status.revoked
    return RevokedResponse(revoked_at=datetime.now(timezone.utc))
