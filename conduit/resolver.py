"""Three-plane resolver — identity, location, infrastructure.

MVP: all three planes resolve from conduit.yaml.
v1.5: location plane can optionally query Backstage API.
"""

from __future__ import annotations
from dataclasses import dataclass
from conduit.config import ConduitConfig


@dataclass
class ResolvedIdentity:
    team: str
    cost_center: str
    approvers: list[str]


@dataclass
class ResolvedLocation:
    csp: str
    region: str
    cluster: str
    saas: str


@dataclass
class ResolvedInfra:
    account_id: str | None
    vpc_id: str | None
    iam_role: str | None
    security_group: str | None


@dataclass
class FullResolution:
    identity: ResolvedIdentity
    locations: list[ResolvedLocation]
    infra: dict[str, ResolvedInfra]  # key: "csp/region"


class ResolutionError(Exception):
    def __init__(self, code: int, detail: str):
        self.code = code
        self.detail = detail


def resolve(config: ConduitConfig, sso_groups: list[str], service: str, env: str) -> FullResolution:
    """Resolve all three planes from config.

    Args:
        config: Loaded conduit.yaml
        sso_groups: Groups from SSO JWT token claims
        service: Service name from developer request
        env: Target environment

    Returns:
        FullResolution with identity, locations, and infra per location

    Raises:
        ResolutionError with HTTP status code and detail message
    """
    # --- Plane 1: Identity ---
    team_name = None
    team_config = None
    # Check which SSO group maps to a registered team
    for tname, tconf in config.teams.items():
        if tconf.sso_group in sso_groups:
            team_name = tname
            team_config = tconf
            break
    if not team_config:
        raise ResolutionError(403, f"SSO groups {sso_groups} not mapped to any registered team")

    identity = ResolvedIdentity(
        team=team_name,
        cost_center=team_config.cost_center,
        approvers=team_config.approvers,
    )

    # --- Plane 2: Location ---
    svc_config = config.services.get(service)
    if not svc_config:
        raise ResolutionError(404, f"Service '{service}' not in service registry")

    # Check team ownership
    if svc_config.team != team_name:
        raise ResolutionError(403, f"Service '{service}' belongs to team '{svc_config.team}', not '{team_name}'")

    deployments = [d for d in svc_config.deployments if d.env == env]
    if not deployments:
        avail = list({d.env for d in svc_config.deployments})
        raise ResolutionError(404, f"No deployment of '{service}' in env '{env}'. Available: {avail}")

    locations = [
        ResolvedLocation(csp=d.csp, region=d.region, cluster=d.cluster, saas=d.saas)
        for d in deployments
    ]

    # --- Plane 3: Infrastructure ---
    infra = {}
    for loc in locations:
        key = f"{loc.csp}/{loc.region}"
        account = next(
            (a for a in team_config.accounts if a.env == env and a.csp == loc.csp and a.region == loc.region),
            None,
        )
        if not account:
            raise ResolutionError(
                422, f"No Day 0 config for team '{team_name}' in {key} ({env}). Run admin setup first."
            )
        infra[key] = ResolvedInfra(
            account_id=account.account_id,
            vpc_id=account.vpc_id,
            iam_role=account.iam_role,
            security_group=account.security_group,
        )

    return FullResolution(identity=identity, locations=locations, infra=infra)
