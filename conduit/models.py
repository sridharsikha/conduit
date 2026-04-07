"""Request/response models for Conduit API."""

from __future__ import annotations
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class Environment(str, Enum):
    dev = "dev"
    qa = "qa"
    perf = "perf"
    staging = "staging"
    prod = "prod"


class Lifecycle(str, Enum):
    always_on = "always_on"
    scheduled = "scheduled"
    serverless = "serverless"


class Status(str, Enum):
    pending_approval = "PENDING_APPROVAL"
    approved = "APPROVED"
    provisioning = "PROVISIONING"
    active = "ACTIVE"
    hibernating = "HIBERNATING"
    waking = "WAKING"
    draining = "DRAINING"
    pending_revocation = "PENDING_REVOCATION"
    revoked = "REVOKED"


# --- Requests ---


class ConnectionRequest(BaseModel):
    """The developer's primary API call. Three required fields."""

    service: str = Field(..., description="Service name from service registry (YAML config or Backstage)")
    environment: Environment = Field(..., description="Target environment")
    bandwidth_mbps: int = Field(..., ge=1, le=10000, description="Requested bandwidth in Mbps")
    topics: list[str] | None = Field(None, description="Kafka topic names for cross-team policy check")
    lifecycle: Lifecycle | None = Field(None, description="Override lifecycle mode. Defaults from policy per env.")
    ttl_hours: int = Field(0, ge=0, description="Auto-expire after N hours. 0 = no expiry.")
    webhook_url: str | None = Field(None, description="POST callback URL when connection becomes ACTIVE")

    model_config = {"json_schema_extra": {"examples": [
        {"service": "order-svc", "environment": "prod", "bandwidth_mbps": 500}
    ]}}


# --- Responses ---


class EndpointInfo(BaseModel):
    csp: str
    region: str
    bootstrap: str
    private_ip: str
    endpoint_id: str
    connection_type: str  # PrivateLink, Private Endpoint, PSC


class ResolvedContext(BaseModel):
    team: str
    cost_center: str
    approval: str  # "auto" or "snow"
    saas_provider: str | None = None


class EnvVars(BaseModel):
    KAFKA_BOOTSTRAP_SERVERS: str | None = None
    KAFKA_API_KEY: str | None = None
    KAFKA_API_SECRET: str | None = None
    KAFKA_SECURITY_PROTOCOL: str | None = None
    KAFKA_SASL_MECHANISM: str | None = None


class BillingProjection(BaseModel):
    projected_monthly: str
    endpoint_hourly: float = 0.013
    data_egress_per_gb: float = 0.01


class ConnectionResponse(BaseModel):
    """200 OK — auto-approved, connection active."""

    connection_id: str
    status: Status = Status.active
    service: str
    environment: str
    lifecycle: str
    resolved: ResolvedContext
    connections: list[EndpointInfo]
    env_vars: EnvVars
    billing: BillingProjection
    created_at: datetime


class PendingResponse(BaseModel):
    """202 Accepted — pending SNOW approval."""

    request_id: str
    status: Status = Status.pending_approval
    snow_ritm: str
    approver: str
    reason: str
    poll_url: str
    poll_interval_sec: int = 10


class StatusResponse(BaseModel):
    status: Status
    snow_ritm: str | None = None
    approved_by: str | None = None
    approved_at: datetime | None = None
    provisioning_progress: dict[str, str] | None = None


class RevokedResponse(BaseModel):
    status: Status = Status.revoked
    revoked_at: datetime | None = None


class PendingRevocationResponse(BaseModel):
    status: Status = Status.pending_revocation
    snow_chg: str
    grace_period_minutes: int = 30
    teardown_at: datetime
    cancel_url: str


class HealthCheck(BaseModel):
    status: str
    checks: dict[str, str]
    version: str
    uptime: str
