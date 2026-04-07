# Conduit

**Self-serve private networking for any cloud SaaS.** One API, one portal, one bill.

Conduit is an open-source NaaS orchestrator that lets developers request private connectivity to managed cloud services — Kafka, Snowflake, Databricks, MongoDB Atlas, Redis, Elastic — with zero infrastructure knowledge. Three fields in, private endpoint out.

```bash
POST /api/v1/connections
{ "service": "order-svc", "environment": "prod", "bandwidth_mbps": 500 }

# Developer gets: bootstrap URL, private IP, API keys, K8s configmap
# System handles: SSO → team lookup → service registry → VPC/IAM → SNOW approval → CSP provisioning
```

## Quick start

```bash
# From source
git clone https://github.com/sikhasridhar/conduit.git
cd conduit
pip install -e .
conduit serve --config examples/acme-corp/conduit.yaml

# Docker
docker run -d -e CONDUIT_PG_URL=postgres://... -p 8443:8443 ghcr.io/sikhasridhar/conduit:latest

# Kubernetes
helm install conduit deploy/helm/conduit -n conduit-system
```

**Single Python process.** Not microservices. Not a K8s operator. Not a Terraform wrapper. Runs anywhere — K8s, Docker, systemd. Calls CSP APIs directly via AWS/Azure/GCP SDKs.

## Interactive prototype

[Live demo](https://sikhasridhar.github.io/conduit/) — 11-tab prototype with realistic data: 4 teams, 7 SaaS providers, 18 connections across AWS/Azure/GCP. Tabs: Architecture, Day 0 setup, Service registry, Developer portal, API playground, Approval flow, Topology, Billing, Lifecycle, Roadmap, Day 0 checklist.

---

## Why Conduit exists

Every cloud SaaS company — Confluent, Snowflake, Databricks, MongoDB Atlas — faces the same problem. Their customers need private connectivity, and today that means:

1. Developer files a ticket
2. Network engineer provisions a VPC endpoint manually
3. Repeat for every environment, region, and CSP
4. Nobody tracks cost, nobody knows who approved what

Conduit replaces this with a self-serve API backed by three resolution planes that eliminate infrastructure from the developer's world.

## Architecture

```
                              ┌─────────────────────────────────────────┐
                              │          Conduit orchestrator           │
Developer ──► API Gateway ──► │                                         │
  {svc,env}    (Kong/Envoy)   │  ┌──────────┐ ┌──────────┐ ┌────────┐ │
                              │  │ Identity  │ │ Location │ │ Infra  │ │
                              │  │  plane    │ │  plane   │ │ plane  │ │
                              │  │ (SSO/IdP) │ │(Backstage│ │(Day 0  │ │
                              │  │           │ │ /ArgoCD) │ │ config)│ │
                              │  └─────┬─────┘ └────┬─────┘ └───┬────┘ │
                              │        │             │           │      │
                              │        ▼             ▼           ▼      │
                              │  ┌─────────────────────────────────┐   │
                              │  │        Policy engine            │   │
                              │  │  auto-approve / SNOW routing    │   │
                              │  └───────────┬─────────────────────┘   │
                              └──────────────┼─────────────────────────┘
                     ┌───────────────────────┼───────────────────────┐
                     ▼                       ▼                       ▼
              ┌────────────┐         ┌──────────────┐        ┌────────────┐
              │ ServiceNow │         │   CSP APIs   │        │  Confluent │
              │ (approval) │────────►│ (provision)  │───────►│  (accept)  │
              └────────────┘  token  └──────────────┘        └────────────┘
```

### Three planes

| Plane | Source | Resolves | Owner |
|-------|--------|----------|-------|
| **Identity** | SSO/IdP (Okta, Azure AD) | Who is asking, team, cost center, approver | Security/IT |
| **Location** | Service registry (Backstage, ArgoCD) | Which CSP(s), region(s), cluster(s) | Platform eng |
| **Infrastructure** | Day 0 config registry | VPC, subnets, IAM role, security group | Platform eng |

The developer interacts with none of these planes. They say `service + environment` and Conduit resolves the rest.

## Features

- **Three-plane resolution** — SSO identity → service registry → Day 0 config → provisioning
- **Multi-cloud** — AWS PrivateLink, Azure Private Endpoint, GCP Private Service Connect
- **Multi-region** — automatically provisions endpoints in every region where a service runs
- **Serverless endpoints** — wake-on-DNS-query, hibernate on idle. Dev endpoints cost $0.78/day instead of $9.36 (92% savings)
- **Three lifecycle modes** — always-on (prod), scheduled (perf), serverless (dev/QA)
- **Revocation governance** — self-serve for dev, MFA step-up for perf, SNOW CHG + grace period for prod, emergency break-glass
- **ServiceNow integration** — RITM for creation, CHG for deletion, CMDB CI references, webhook-driven approval
- **Token-gated provisioning** — short-lived JWT approval tokens scoped to specific resources
- **Policy engine** — auto-approve dev/QA, require SNOW approval for prod
- **Billing & chargeback** — per-connection metering, team cost attribution, CSP breakdown
- **Pre-flight validation** — nightly cron re-checks IAM roles, security groups, DNS, quotas
- **Day 0 config registry** — platform team registers cloud accounts once, developers never touch infra

## Quick start

```bash
# Clone
git clone https://github.com/sikhasridhar/conduit.git
cd conduit

# Run the interactive prototype (no backend needed)
open web/index.html

# Or deploy with Helm
helm install conduit deploy/helm/conduit -n conduit-system
```

## Project structure

```
conduit/
├── cmd/conduit/          # Main entry point
├── pkg/
│   ├── resolver/         # Three-plane resolution engine
│   │   ├── identity.go   # SSO/IdP group → team/cost center
│   │   ├── location.go   # Service registry → CSP/region/cluster
│   │   └── infra.go      # Day 0 config → VPC/IAM/SG
│   ├── policy/           # Auto-approve vs SNOW routing rules
│   ├── snow/             # ServiceNow Table API integration
│   │   ├── ritm.go       # Create/close RITMs
│   │   ├── cmdb.go       # CMDB CI sync
│   │   └── webhook.go    # Approval callback handler
│   ├── provisioner/      # CSP-specific endpoint creation
│   │   ├── aws/          # PrivateLink (create-vpc-endpoint)
│   │   ├── azure/        # Private Endpoint
│   │   └── gcp/          # Private Service Connect
│   ├── billing/          # Metering, chargeback, cost attribution
│   └── config/           # Day 0 config registry
├── api/v1/               # OpenAPI spec + generated types
├── internal/
│   ├── gateway/          # API gateway middleware (JWT, rate limit)
│   └── token/            # Approval token minting (JWT signing)
├── docs/
│   ├── architecture/     # Architecture decision records
│   └── day0/             # Day 0 setup guides per CSP
├── web/                  # Interactive prototype (static HTML)
├── deploy/
│   ├── helm/             # Helm chart
│   └── terraform/        # Day 0 IaC templates
├── examples/
│   ├── acme-corp/        # Full example with 4 teams, 8 services
│   └── minimal/          # Minimal single-team setup
└── .github/workflows/    # CI/CD
```

## Roadmap

| Release | Focus | Key capabilities |
|---------|-------|-------------------|
| **v1.0 — MVP** | Orchestrator core | Three-plane resolution, POST /connections (3 fields), SNOW RITM integration, token-gated AWS PrivateLink provisioning, always-on endpoints, basic billing, delete governance |
| **v1.1** | Multi-cloud | Azure Private Endpoint + GCP PSC provisioners, multi-region parallel provisioning |
| **v1.5** | Developer experience | `/env?format=` endpoint (dotenv, k8s-configmap, k8s-secret), CLI, webhook callbacks |
| **v2.0 — Add-on** | Lifecycle (paid tier) | Scheduled endpoints (cron), **serverless endpoints (DNS wake-on-connect)**, CoreDNS plugin, idle detection, cost optimization dashboard |
| **v2.5** | Multi-provider | Snowflake, Databricks, MongoDB Atlas acceptor plugins |
| **v3.0** | Enterprise | Jira/PagerDuty approval plugins, Terraform provider (`conduit_connection`), GitOps mode |

## Day 0 setup

Before developers can request connections, the platform team must register:

1. **SSO groups** — map IdP groups to teams and cost centers
2. **Cloud accounts** — VPCs, IAM roles, security groups per team/env/CSP
3. **Service registry** — which services run where (Backstage/ArgoCD)
4. **ServiceNow** — catalog item, assignment groups, CMDB CIs
5. **Conduit config** — policy rules, approval token signing key

See [Day 0 checklist](docs/day0/CHECKLIST.md) for the complete 42-item setup guide.

## Supported SaaS providers

Conduit is provider-agnostic. The provisioner layer creates private endpoints — what sits on the other side is pluggable:

| Provider | Connection type | Status |
|----------|----------------|--------|
| Confluent Cloud (Kafka) | PrivateLink / PE / PSC | ✅ Prototype |
| Snowflake | PrivateLink / PE / PSC | 🔲 Planned |
| Databricks | PrivateLink / PE / PSC | 🔲 Planned |
| MongoDB Atlas | PrivateLink / PE | 🔲 Planned |
| Elastic Cloud | PrivateLink | 🔲 Planned |
| Redis Cloud | PrivateLink | 🔲 Planned |

## API

```bash
# Request a connection (developer's only API call)
curl -X POST https://conduit.internal/api/v1/connections \
  -H "Authorization: Bearer $SSO_TOKEN" \
  -d '{"service": "order-svc", "environment": "prod", "bandwidth_mbps": 500}'

# Response (auto-approved)
200 OK
{
  "connection_id": "conn-2411-a8f3",
  "connections": [
    {"bootstrap": "pkc-prod01.us-east-1.aws.confluent.cloud:9092", "private_ip": "10.0.1.47"},
    {"bootstrap": "pkc-prod01.europe-west1.gcp.confluent.cloud:9092", "private_ip": "10.9.0.5"}
  ],
  "env_vars": {
    "KAFKA_BOOTSTRAP_SERVERS": "pkc-prod01....:9092,pkc-prod01....:9092",
    "KAFKA_API_KEY": "XXXXXXXX",
    "KAFKA_API_SECRET": "********"
  }
}

# Response (pending SNOW approval)
202 Accepted
{
  "request_id": "REQ-2411",
  "status": "PENDING_APPROVAL",
  "snow_ritm": "RITM0042411",
  "poll_url": "/api/v1/connections/REQ-2411/status"
}
```

## Contributing

Conduit is in early development. Contributions welcome in:

- **CSP provisioners** — Azure Private Endpoint and GCP PSC adapters
- **SaaS acceptor plugins** — Snowflake, Databricks, MongoDB Atlas, Redis Cloud, Elastic Cloud
- **IdP integrations** — Google Workspace, Ping Identity
- **Service registry adapters** — Backstage plugin, ArgoCD controller
- **Terraform Day 0 modules** — IaC for AWS/Azure/GCP account setup
- **Crossplane Composition** — alternative provisioner backend using Crossplane claims

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

## How Conduit compares

| Capability | Conduit | Crossplane | Terraform | Confluent CLI/TF |
|-----------|---------|------------|-----------|-----------------|
| Self-serve API for developers | **yes** | no (YAML + kubectl) | no (HCL files) | Confluent only |
| Web portal + API playground | **yes** | no (Upbound is commercial) | no | Cloud console |
| SSO identity → team resolution | **yes** | no | no | no |
| Service registry integration | **yes** | no | no | no |
| SNOW/ITSM approval workflow | **yes** | no | no | no |
| Multi-SaaS (Confluent + Snowflake + ...) | **yes** | per-provider CRDs | per-provider modules | Confluent only |
| Billing / chargeback | **yes** | no | no | no |
| Serverless endpoints (wake-on-DNS) | **yes** | no | no | no |
| Infrastructure reconciliation / drift | no (use Crossplane) | **yes** | **yes** (plan/apply) | no |
| GitOps-native | planned v3.0 | **yes** | yes (Atlantis) | yes (TF provider) |

**Conduit + Crossplane is complementary, not competitive.** Conduit handles identity, resolution, approval, billing, lifecycle. Crossplane handles infrastructure reconciliation. Use `provisioner: crossplane` in conduit.yaml to delegate VPC endpoint creation to Crossplane while keeping the orchestration layer in Conduit.

## License

Apache 2.0

## Author

**Sridhar Sikha** — Principal Product Manager | [LinkedIn](https://linkedin.com/in/sikhasridhar)

Built from experience building multi-tenant NaaS orchestration at Cisco (SASE platform, $1B market) and network edge gateway products at Ruckus Networks. The three-plane architecture is the product vision I would build next.
