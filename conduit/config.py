"""Load conduit.yaml — services, teams, accounts, policy, SaaS providers."""

from __future__ import annotations
from pathlib import Path
from pydantic import BaseModel
import yaml
import os


class Deployment(BaseModel):
    env: str
    csp: str
    region: str
    cluster: str
    saas: str


class ServiceConfig(BaseModel):
    team: str
    deployments: list[Deployment]


class Account(BaseModel):
    env: str
    csp: str
    region: str
    account_id: str | None = None
    vpc_id: str | None = None
    iam_role: str | None = None
    security_group: str | None = None


class TeamConfig(BaseModel):
    sso_group: str
    cost_center: str
    approvers: list[str]
    accounts: list[Account]


class SaaSRegion(BaseModel):
    csp: str
    region: str
    cluster: str
    endpoint_service: str | None = None


class SaaSProvider(BaseModel):
    name: str
    type: str
    api_url: str | None = None
    regions: list[SaaSRegion]


class ConduitConfig(BaseModel):
    services: dict[str, ServiceConfig] = {}
    teams: dict[str, TeamConfig] = {}
    saas_providers: dict[str, SaaSProvider] = {}
    provisioner_backend: str = "aws_sdk"
    lifecycle_defaults: dict[str, str] = {
        "prod": "always_on",
        "perf": "scheduled",
        "staging": "scheduled",
        "qa": "serverless",
        "dev": "serverless",
    }


def load_config(path: str | None = None) -> ConduitConfig:
    """Load config from YAML file or env var."""
    config_path = path or os.getenv("CONDUIT_CONFIG", "conduit.yaml")
    p = Path(config_path)
    if not p.exists():
        return ConduitConfig()
    with open(p) as f:
        raw = yaml.safe_load(f)
    return ConduitConfig(**raw) if raw else ConduitConfig()
