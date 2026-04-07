# Conduit API reference

Base URL: `https://conduit.internal/api/v1`

---

## Request headers (all endpoints)

| Header | Value | Required | Description |
|--------|-------|----------|-------------|
| `Authorization` | `Bearer <JWT>` | **required** | SSO token from IdP. Conduit extracts `sub`, `groups`, `email` claims. |
| `Content-Type` | `application/json` | required (POST) | JSON request body. |
| `X-Request-ID` | `uuid` | optional | Idempotency key. Conduit generates one if omitted. |
| `X-Step-Up` | `string` | conditional | MFA token. Required for perf/prod DELETE. |

## Response headers (all endpoints)

| Header | Description |
|--------|-------------|
| `X-Request-ID` | Echoed or generated request ID for tracing. |
| `X-RateLimit-Remaining` | Remaining requests in current window. |
| `X-Conduit-Resolved-Team` | Team resolved from SSO group (debug). |

---

## POST /connections

**Request a connection.** The developer's primary API call.

### Request body

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `service` | string | **required** | Service name in service registry. | `"order-svc"` |
| `environment` | string | **required** | Target environment. | `"prod"` |
| `bandwidth_mbps` | integer | **required** | Requested bandwidth. Affects cost + policy. | `500` |
| `topics` | string[] | optional | Kafka topics. For cross-team policy check. | `["orders-events"]` |
| `lifecycle` | string | optional | Override: `always_on`, `scheduled`, `serverless`. Defaults from policy. | `"serverless"` |
| `ttl_hours` | integer | optional | Auto-expire after N hours. 0 = no expiry. | `24` |
| `webhook_url` | string | optional | POST callback on ACTIVE (instead of polling). | `"https://..."` |

### Response — 200 OK (auto-approved)

```json
{
  "connection_id": "conn-2411-a8f3",
  "status": "ACTIVE",
  "service": "order-svc",
  "environment": "dev",
  "lifecycle": "serverless",
  "resolved": {
    "team": "Commerce",
    "cost_center": "CC-3100",
    "approval": "auto"
  },
  "connections": [
    {
      "csp": "aws",
      "region": "us-east-1",
      "bootstrap": "pkc-dev01.us-east-1.aws.confluent.cloud:9092",
      "private_ip": "10.10.1.12",
      "endpoint_id": "vpce-0dev1234",
      "connection_type": "PrivateLink"
    }
  ],
  "env_vars": {
    "KAFKA_BOOTSTRAP_SERVERS": "pkc-dev01.us-east-1.aws.confluent.cloud:9092",
    "KAFKA_API_KEY": "XXXXXXXXXXXXXXXX",
    "KAFKA_API_SECRET": "********",
    "KAFKA_SECURITY_PROTOCOL": "SASL_SSL",
    "KAFKA_SASL_MECHANISM": "PLAIN"
  },
  "billing": {
    "projected_monthly": "$23.40",
    "endpoint_hourly": 0.013,
    "data_egress_per_gb": 0.01
  },
  "created_at": "2026-04-06T08:30:00Z",
  "ttl_hours": 0
}
```

### Response — 202 Accepted (pending SNOW approval)

```json
{
  "request_id": "REQ-2411",
  "status": "PENDING_APPROVAL",
  "snow_ritm": "RITM0042411",
  "approver": "james.liu@acme.com",
  "reason": "Production environment requires manager approval",
  "resolved": {
    "team": "Commerce",
    "locations": 2,
    "projected_monthly": "$123.60"
  },
  "poll_url": "/api/v1/connections/REQ-2411/status",
  "poll_interval_sec": 10
}
```

### Status codes

| Code | Meaning |
|------|---------|
| 200 | Auto-approved. Connection active. |
| 202 | Pending SNOW approval. Poll or wait for webhook. |
| 400 | Missing required field. |
| 403 | SSO group not registered (no Day 0 config for team). |
| 404 | Service not in registry, or no deployment in this env. |
| 422 | No Day 0 config for resolved CSP/region. |
| 429 | Rate limited. |
| 502 | IAM role assumption failed (Day 0 config stale). |
| 504 | CSP endpoint creation timed out (>90s). |

---

## GET /connections/{id}/status

**Poll approval + provisioning status.**

### Path parameters

| Param | Type | Description |
|-------|------|-------------|
| `id` | string | Request ID (REQ-2411) or connection ID (conn-2411-a8f3). |

### Response

```json
{
  "status": "PROVISIONING",
  "snow_ritm": "RITM0042411",
  "approved_by": "james.liu@acme.com",
  "approved_at": "2026-04-06T08:22:00Z",
  "provisioning_progress": {
    "aws/us-east-1": "creating_endpoint",
    "gcp/europe-west1": "accepting_attachment"
  }
}
```

### Status transitions

```
PENDING_APPROVAL → APPROVED → PROVISIONING → ACTIVE
                                                ↕
                                           HIBERNATING ↔ WAKING
                                                ↓
                                            DRAINING → REVOKED
```

---

## GET /connections/{id}/env

**Get env vars for code integration.**

### Query parameters

| Param | Type | Values | Default |
|-------|------|--------|---------|
| `format` | string | `json`, `dotenv`, `k8s-configmap`, `k8s-secret`, `docker` | `json` |

### Response — format=dotenv

```
KAFKA_BOOTSTRAP_SERVERS=pkc-prod01.us-east-1.aws.confluent.cloud:9092
KAFKA_API_KEY=XXXXXXXXXXXXXXXX
KAFKA_API_SECRET=yyyyyyyyyyyyyyyy
KAFKA_SECURITY_PROTOCOL=SASL_SSL
KAFKA_SASL_MECHANISM=PLAIN
```

### Response — format=k8s-configmap

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: kafka-config-conn-2411
  labels:
    conduit.io/connection: conn-2411-a8f3
    conduit.io/service: order-svc
data:
  KAFKA_BOOTSTRAP_SERVERS: "pkc-prod01....:9092"
  KAFKA_SECURITY_PROTOCOL: "SASL_SSL"
```

---

## GET /connections

**List my connections.** Scoped to caller's SSO group.

### Query parameters

| Param | Type | Description | Default |
|-------|------|-------------|---------|
| `status` | string | `active`, `hibernating`, `pending`, `revoked`, `all` | `active` |
| `service` | string | Filter by service name. | — |
| `environment` | string | Filter by environment. | — |
| `page` | integer | Page number (20 per page). | 1 |

---

## DELETE /connections/{id}

**Revoke a connection.** Governance varies by environment.

### Conditional headers

| Header | When required | Description |
|--------|---------------|-------------|
| `X-Step-Up` | perf + prod | MFA token. If missing → 401 with `step_up_url`. |
| `X-Reason` | emergency only | Mandatory reason for break-glass. |

### Response by environment

**Dev/QA → 200 OK (immediate)**
```json
{ "status": "REVOKED", "revoked_at": "2026-04-06T..." }
```

**Perf → 401 (MFA required, if X-Step-Up missing)**
```json
{
  "error": "MFA_REQUIRED",
  "step_up_url": "https://acme.okta.com/mfa/challenge?session=..."
}
```

**Perf → 200 OK (with valid X-Step-Up)**
```json
{ "status": "REVOKED" }
```

**Prod → 202 Accepted (SNOW CHG + 30-min grace)**
```json
{
  "status": "PENDING_REVOCATION",
  "snow_chg": "CHG0054321",
  "grace_period_minutes": 30,
  "teardown_at": "2026-04-06T10:52:00Z",
  "cancel_url": "/api/v1/connections/CONN-001/cancel-delete"
}
```

---

## POST /connections/{id}/cancel-delete

**Cancel pending prod revocation during grace period.**

| Code | Response |
|------|----------|
| 200 | `{ "status": "ACTIVE", "message": "Revocation cancelled. CHG closed." }` |
| 409 | `{ "error": "TEARDOWN_IN_PROGRESS", "message": "Grace period expired." }` |

---

## curl examples

```bash
# Request a connection
curl -s -X POST https://conduit.internal/api/v1/connections \
  -H "Authorization: Bearer $SSO_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"service":"order-svc","environment":"prod","bandwidth_mbps":500}'

# Poll status
curl -s https://conduit.internal/api/v1/connections/REQ-2411/status \
  -H "Authorization: Bearer $SSO_TOKEN"

# Get env vars as .env file
curl -s "https://conduit.internal/api/v1/connections/conn-2411/env?format=dotenv" \
  -H "Authorization: Bearer $SSO_TOKEN" > .env

# Pipe K8s configmap directly to kubectl
curl -s "https://conduit.internal/api/v1/connections/conn-2411/env?format=k8s-configmap" \
  -H "Authorization: Bearer $SSO_TOKEN" | kubectl apply -f -

# Delete dev connection (immediate)
curl -s -X DELETE https://conduit.internal/api/v1/connections/conn-2411 \
  -H "Authorization: Bearer $SSO_TOKEN"

# Delete prod connection (with MFA)
curl -s -X DELETE https://conduit.internal/api/v1/connections/conn-2411 \
  -H "Authorization: Bearer $SSO_TOKEN" \
  -H "X-Step-Up: $MFA_TOKEN"

# Cancel a pending prod delete
curl -s -X POST https://conduit.internal/api/v1/connections/conn-2411/cancel-delete \
  -H "Authorization: Bearer $SSO_TOKEN"
```
