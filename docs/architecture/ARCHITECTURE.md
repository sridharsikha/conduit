# Conduit Architecture

## What Conduit is

A **single Python/FastAPI process** — runs as K8s Deployment, Docker container, or systemd service. Self-serve API for developers to provision private connections to any cloud SaaS using three fields: service, environment, bandwidth.

NOT a K8s operator. NOT a Terraform wrapper. NOT a Crossplane plugin. Standalone microservice with its own API, state, and direct CSP SDK calls.

## Runtime — single binary, not microservices

```
┌──────────────────────────────────────────────────┐
│            Conduit (single Python/FastAPI process)             │
│                                                   │
│  API server ─ Resolver ─ Policy ─ Token minter    │
│       (net/http :8443)    (async tasks)             │
│                                                   │
│  Kafka producer/consumer (confluent-kafka-go)     │
│                                                   │
│  Background workers (async tasks):                 │
│    Preflight cron │ CMDB sync │ Billing │ Lifecycle│
│                                                   │
│  CSP provisioner plugin:                          │
│    aws_sdk │ azure_sdk │ gcp_sdk │ crossplane     │
└───────────────────────┬──────────────────────────┘
                        │
         PostgreSQL ── Redis ── Kafka (Confluent)
```

No sidecar. No service mesh. Goroutines handle concurrency.

## External dependencies

| Dependency | Required | Fallback |
|-----------|----------|----------|
| PostgreSQL | yes | None — source of truth |
| Redis | yes | PG-based queue (slower) |
| Kafka | yes | Sync mode (blocks API) |
| IdP (Okta) | yes | None |
| ServiceNow | conditional | Auto-approve all |
| Backstage | conditional | Static mapping in YAML |

## Health endpoints

```
GET /healthz → liveness
GET /readyz  → {postgres: ok, redis: ok, kafka: ok, idp: ok, snow: ok}
```

## Provisioner backends

```yaml
provisioner:
  backend: aws_sdk      # default: direct SDK, zero dependencies
  # backend: crossplane  # optional: generates Composition claims
  # backend: terraform   # optional: terraform apply
```

**aws_sdk (default):** Direct CreateVpcEndpoint via AWS SDK for Go. STS AssumeRole, create, tag, poll. No external tooling.

**crossplane (optional):** Generates Composition claim YAML, applies via K8s API. Crossplane handles reconciliation + drift. Requires Crossplane installed.

**Why NOT Crossplane as hard dependency:** Conduit should be installable with `docker run conduit` + a PG connection string. Crossplane limits you to K8s-only, adds operational complexity, and couples Conduit availability to Crossplane health.

## Kafka event bus (dogfooding)

| Topic | Producer → Consumer |
|-------|---------------------|
| conn.requests | API server → Resolver |
| approval.events | SNOW webhook → Provisioner |
| provision.events | Provisioner → Billing, Audit |
| billing.usage | Metering → Flink |
| lifecycle.events | DNS proxy → Lifecycle worker |
| audit.sealed | All → Compliance (immutable) |

Conduit's own Kafka connection is provisioned through Conduit itself.

## Deploy

```bash
# Kubernetes
helm install conduit deploy/helm/conduit -n conduit-system

# Docker
docker run -d -e CONDUIT_PG_URL=postgres://... -p 8443:8443 ghcr.io/sikhasridhar/conduit:latest

# Systemd
conduit serve --config /etc/conduit/conduit.yaml

# Build from source
go build -o conduit ./cmd/conduit/
```
