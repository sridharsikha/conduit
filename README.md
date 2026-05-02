# Conduit

**Self-serve private networking for any cloud SaaS.**
Developers request connections through a portal. Infra teams stop being a bottleneck. Finance gets per-team chargeback for free.

Conduit replaces the ticket-driven, multi-team workflow that today gates every private endpoint to Confluent, Snowflake, Databricks, MongoDB Atlas and others. Three fields in, private endpoint out. The infrastructure teams set the policy once; the developers self-serve from there.

[**Live prototype →**](https://sridharsikha.github.io/conduit/)

---

## What this is

A network-as-a-service orchestrator that sits between your developers and the cloud APIs. It hides the infrastructure detail — VPCs, IAM roles, security groups, DNS zones, CSP-specific endpoint types — behind a single API and portal.

```bash
POST /api/v1/connections
Authorization: Bearer <SSO_TOKEN>
{ "service": "order-svc", "environment": "prod", "bandwidth_mbps": 500 }

# Developer gets back: bootstrap URL, private IP, API keys, k8s configmap
# Conduit handles: SSO → team, registry → CSP/region, Day 0 → VPC/IAM, SNOW → approval, CSP API → provisioning
```

The developer does not specify CSP, region, VPC, IAM role, or security group. The orchestrator resolves all of that from three independent planes: identity (who is asking), location (where the service runs), and infrastructure (which VPC + IAM to use).

## Why this exists

Today, getting a developer connected privately to a managed SaaS service is a six-team workflow.

| Step | Who owns it | What they do | Typical wait |
|------|-------------|--------------|--------------|
| 1 | Developer | Files a ticket | — |
| 2 | Network team | Provisions VPC endpoint | 3–5 days |
| 3 | Identity team | Creates IAM role, SG | 2–3 days |
| 4 | SaaS admin | Accepts the link on the SaaS side | 1–2 days |
| 5 | DNS team | Adds private hosted zone | 1–2 days |
| 6 | Finance | Assigns cost code | 1–3 days |

End-to-end: two to three weeks. No shared system of record. No cost attribution. No audit trail. Drift later in the year breaks connections nobody owns.

Multiply that by every environment, every region, every SaaS provider. Most enterprises today have hundreds of private endpoints provisioned this way; nobody can answer "which team owns endpoint vpce-0abc1234" without a Slack archaeology session.

## What Conduit changes

| | Before | After |
|---|--------|-------|
| **Time-to-endpoint** | 2–3 weeks | 90 seconds (auto-approved) · 4–6 hours (SNOW-approved) |
| **Teams in the workflow** | 6 (network, identity, SaaS admin, DNS, finance, requester) | 1 (requester) for dev/QA · 2 (requester + manager) for prod |
| **Cost attribution** | Manual, after the fact, often missing | Per-connection from minute one, rolled up by team / CSP / SaaS |
| **Drift detection** | Nobody owns it | Pre-flight cron re-validates IAM, SG, DNS, quotas nightly |
| **Audit trail** | Slack threads + ticket archives | Immutable record per connection, RITM-anchored |
| **Multi-cloud parity** | Each CSP is a separate project | One API, one portal, all three CSPs |
| **Multi-SaaS parity** | Each SaaS has its own networking guide | Same UX for Confluent, Snowflake, Databricks, Mongo, ... |

## What developers experience

A web portal with three fields. Or a CLI. Or an API call from inside their CI.

```bash
$ conduit connect order-svc --env prod --bw 500
✓ SSO resolved → team: Commerce, cost center: CC-3100
✓ Service registry → deployed in AWS us-east-1, GCP europe-west1
✓ Day 0 config matched → vpc-0comm-prod (us-east-1), commerce-vpc-eu (europe-west1)
✓ Policy: prod → SNOW approval required
✓ RITM0042401 created, routed to james.liu@acme.com
✓ Approved. Provisioning 2 endpoints in parallel.
✓ Active.

KAFKA_BOOTSTRAP_SERVERS=pkc-prod01.us-east-1.aws.confluent.cloud:9092,pkc-prod01.europe-west1.gcp.confluent.cloud:9092
KAFKA_API_KEY=...
```

What's missing from the developer's view: the words VPC, IAM, security group, route table, DNS, peering, PrivateLink, region, account, subnet. That's the point.

## What infra teams experience

The platform team registers the contract once: SSO groups, cloud accounts, VPCs, IAM roles, security groups, the policy rules. Day 0 is a one-time onboarding artifact — not a recurring ticket queue.

After Day 0, the infra team's role narrows to:
1. **Reviewing pre-flight cron alerts** — IAM role got revoked, security group is missing the 9092 rule, endpoint quota is at 80%
2. **Reviewing policy violations** — a team requested a connection outside their cost center
3. **Adding new SaaS providers or CSPs** — register acceptor plugins, not endpoints

This is the actual value. The infra team stops being on the critical path of every developer ticket. They define the contract, the system enforces it, drift gets detected and surfaced.

## Dashboards and analytics, first-class

Per-team chargeback isn't a quarterly report you build later. It falls out of the data model on day one because every connection carries the SSO group, cost center, CSP, region, environment, and SaaS provider as first-class metadata.

Out of the box:
- **Cost dashboard** — by team, by CSP, by region, by SaaS, by environment, drill-down to individual connection
- **Service velocity** — time from request to active endpoint, approval cycle time, queue depth in SNOW
- **Drift detection** — pre-flight cron status per Day 0 config, IAM role health, SG drift from baseline
- **Audit trail** — every state transition recorded, RITM-anchored, immutable
- **Lifecycle** — always-on / scheduled / serverless modes, idle hibernation savings, scheduled provisioning windows
- **Quota tracking** — endpoint count vs CSP limit per account, per region, per service

The same data that makes the developer experience fast also makes the analytics free. There is no separate ETL.

## Architecture

```
                              ┌─────────────────────────────────────────┐
                              │           Conduit orchestrator           │
Developer  ─►  API gateway ─► │                                          │
 {svc,env}     (Kong/Envoy)   │  ┌──────────┐ ┌──────────┐ ┌─────────┐  │
                              │  │ Identity │ │ Location │ │  Infra  │  │
                              │  │  plane   │ │   plane  │ │  plane  │  │
                              │  │ (SSO/IdP)│ │ (registry)│ │ (Day 0) │  │
                              │  └─────┬────┘ └────┬─────┘ └───┬─────┘  │
                              │        │           │           │        │
                              │        ▼           ▼           ▼        │
                              │  ┌─────────────────────────────────┐    │
                              │  │      Policy + token mint        │    │
                              │  └───────────┬─────────────────────┘    │
                              └──────────────┼─────────────────────────┘
                                             ▼
                          ┌────────────────────────────────────┐
                          │    Provisioner workers (per CSP)   │
                          │    AWS    │    Azure   │    GCP    │
                          └─────┬─────────┬─────────────┬──────┘
                                │             │             │
                                ▼             ▼             ▼
                          PrivateLink     Private EP        PSC
                          Peering, TGW    VNet peering      VPC peering
                          PNI, Egress PL  ExpressRoute      Cloud VPN
```

### Three planes

| Plane | Source | Resolves | Owner |
|-------|--------|----------|-------|
| **Identity** | SSO/IdP (Okta, Azure AD) | Caller identity, team, cost center, approver | Security/IT |
| **Location** | Service registry (Backstage, ArgoCD) | CSP, region, cluster where the service runs | Platform eng |
| **Infrastructure** | Day 0 config registry | VPC, subnets, IAM role, security group | Platform eng |

The developer interacts with none of these planes. They give `service + environment + bandwidth` and Conduit resolves the rest.

## Multi-tenant from the start

One Conduit instance serves every team in an organization. Tenant key is the SSO group on the inbound JWT. Per-tenant state — cost centers, approvers, quotas, policy — lives in the config registry, not in separate deployments.

Adding a team means registering an SSO group, a cost center, a default approver list, and one or more cloud accounts. No platform changes, no redeploy.

Endpoints themselves are isolated at the CSP layer (security groups, NSGs, firewall rules, IAM role boundaries) — not by separate Conduit installs.

## Connectivity surface (Confluent example)

Conduit's provisioner library covers every private connectivity option each CSP exposes for managed SaaS. For Confluent specifically that's six options today:

| Option | Direction | When to pick |
|--------|-----------|--------------|
| Public TLS | one-way | Dev, demo, low volume |
| VPC / VNet Peering | bidirectional | Single region, IP plan permits |
| Transit Gateway (AWS) | bidirectional | Many VPCs, transitive routing |
| **PrivateLink Gateway** (Feb 2026 standard) | one-way (in) | Default for production |
| **PNI / Multi-VPC ENI** | one-way (in) | Highest throughput, lowest unit cost |
| Cluster Linking | CCN ↔ CCN bridge | Cross-region, cross-cloud, hybrid |

The decision matrix, full deployment topologies for each, and the on-prem-via-Equinix-Fabric path are documented in the [Confluent deep-dive tab](https://sridharsikha.github.io/conduit/) of the live prototype.

## Quick start

```bash
# From source
git clone https://github.com/sridharsikha/conduit.git
cd conduit
pip install -e .
conduit serve --config examples/conduit.yaml

# Or just open the prototype
open docs/index.html

# Docker
docker run -d -p 8443:8443 ghcr.io/sridharsikha/conduit:latest

# Kubernetes (Helm chart — v3.0)
helm install conduit deploy/helm/conduit -n conduit-system
```

Single Python process. Not microservices, not a Kubernetes operator, not a Terraform wrapper. Calls CSP APIs directly via the AWS / Azure / GCP SDKs.

## Day 0 setup

Before developers can request connections, the platform team registers:

1. **SSO groups** — IdP groups mapped to teams and cost centers
2. **Cloud accounts** — VPCs, IAM roles, security groups per team / env / CSP
3. **Service registry** — which services run where (Backstage / ArgoCD)
4. **ServiceNow** — catalog item, assignment groups, CMDB CIs
5. **Conduit config** — policy rules, approval token signing key

See [docs/architecture/ARCHITECTURE.md](docs/architecture/ARCHITECTURE.md) for the complete setup guide. The interactive prototype includes a Day 0 admin tab that walks through this.

## Supported SaaS providers

Conduit is provider-agnostic. The provisioner layer creates private endpoints; the SaaS-side acceptor is pluggable.

| Provider | Connection type | Status |
|----------|-----------------|--------|
| Confluent Cloud | PrivateLink Gateway, Peering, TGW, PNI, Cluster Linking | ✅ Prototype |
| Snowflake | PrivateLink / PE / PSC | 🔲 Planned |
| Databricks | PrivateLink / PE / PSC | 🔲 Planned |
| MongoDB Atlas | PrivateLink / PE | 🔲 Planned |
| Elastic Cloud | PrivateLink | 🔲 Planned |
| Redis Cloud | PrivateLink | 🔲 Planned |

## Roadmap

| Release | Focus | Capabilities |
|---------|-------|--------------|
| v1.0 | Orchestrator core | Three-plane resolution, AWS PrivateLink Gateway provisioner, SNOW integration, basic billing |
| v1.1 | Multi-cloud | Azure Private Endpoint + GCP PSC, multi-region parallel provisioning |
| v1.5 | Developer experience | `/env?format=` (dotenv, k8s-configmap, k8s-secret), CLI, webhook callbacks |
| v2.0 | Lifecycle | Scheduled endpoints, serverless (DNS wake-on-connect), idle hibernation, cost optimization dashboard |
| v2.5 | Multi-provider | Snowflake, Databricks, MongoDB Atlas acceptor plugins |
| v3.0 | Enterprise | Jira / PagerDuty plugins, Terraform provider (`conduit_connection`), GitOps mode |

## How Conduit compares

| Capability | Conduit | Crossplane | Terraform | SaaS-native CLI |
|-----------|---------|------------|-----------|-----------------|
| Self-serve API for developers | ✅ | YAML + kubectl | HCL files | Per-vendor |
| Web portal + API playground | ✅ | Upbound (commercial) | ❌ | Cloud console |
| SSO identity → team resolution | ✅ | ❌ | ❌ | ❌ |
| Service registry integration | ✅ | ❌ | ❌ | ❌ |
| ITSM approval workflow | ✅ | ❌ | ❌ | ❌ |
| Multi-SaaS in one portal | ✅ | per-provider CRDs | per-provider modules | Single vendor only |
| Per-team chargeback / analytics | ✅ | ❌ | ❌ | ❌ |
| Service velocity dashboards | ✅ | ❌ | ❌ | ❌ |
| Drift detection (pre-flight cron) | ✅ | ✅ (reconcile loop) | ✅ (plan/apply) | ❌ |
| GitOps-native | v3.0 | ✅ | Atlantis | per-vendor |

**Conduit + Crossplane is complementary.** Conduit owns identity, resolution, approval, billing, lifecycle, dashboards. Crossplane owns infrastructure reconciliation. Use `provisioner: crossplane` in conduit.yaml to delegate VPC endpoint creation to Crossplane while keeping the orchestration layer in Conduit.

## Contributing

Conduit is in early development. Contributions welcome in:

- CSP provisioners (Azure PE, GCP PSC adapters)
- SaaS acceptor plugins (Snowflake, Databricks, MongoDB Atlas, Redis, Elastic)
- IdP integrations (Google Workspace, Ping)
- Service registry adapters (Backstage plugin, ArgoCD controller)
- Terraform Day 0 modules
- Crossplane Composition (alternative provisioner backend)

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

Apache 2.0

## Author

**Sridhar Sikha** — [LinkedIn](https://linkedin.com/in/sikhasridhar)

Conduit is the platform-PM artifact for the question every cloud-SaaS networking team is solving today: how do you make private connectivity feel like a developer self-serve product instead of a multi-team ticket queue. The three-plane resolver, the Day 0 contract, and the per-team chargeback that falls out of the data model are the design choices that make that work.
