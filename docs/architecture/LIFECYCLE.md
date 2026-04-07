# Endpoint lifecycle modes

Conduit supports three lifecycle modes for private endpoints, configured per environment.

## Always on (prod default)

Endpoint lives 24/7. Zero cold start. $9.36/day per endpoint (2 AZs).

## Scheduled (perf/staging default)

Endpoint alive during business hours only. Cron-based wake and hibernate.

```yaml
scheduled:
  wake_cron: "0 8 * * 1-5"      # Mon-Fri 8am
  hibernate_cron: "0 18 * * 1-5" # Mon-Fri 6pm
```

Cost: $3.90/day (58% savings vs always-on).

## Serverless (dev/QA default)

Endpoint only exists when traffic flows. Created on first connection attempt, destroyed after idle timeout.

### Wake-on-connect mechanism

DNS interception is the wake signal. Conduit runs a CoreDNS plugin (or Route53 Resolver rule) that catches queries for SaaS provider domains.

1. Service pod does DNS lookup for `pkc-dev01.us-east-1.aws.confluent.cloud`
2. Conduit DNS proxy detects the connection is hibernating
3. DNS response is held (not NXDOMAIN) while endpoint is provisioned (30-90s)
4. VPC endpoint created using cached Day 0 config, Confluent accepts
5. DNS returns private IP, Kafka client connects
6. Idle timer starts (30 min default)
7. No traffic for 30 min → 5-min drain → delete VPC endpoint

Cost: $0.78/day assuming 2 hours active (92% savings vs always-on).

### Key design decisions

- **DNS is the wake signal, not a proxy.** No sidecar in the data path. Clean separation.
- **No re-approval on wake.** Original SNOW approval is still valid. Same endpoint spec.
- **State preserved on hibernate.** API keys, Confluent attachment ID, Day 0 config all cached. Only the VPC endpoint (the expensive part) is destroyed.

## Revocation governance

| Environment | Auth | Approval | Grace period |
|------------|------|----------|-------------|
| Dev/QA | SSO only | None | None |
| Perf/staging | MFA step-up | None | None |
| Production | MFA step-up | SNOW change request (CHG) | 30 min |
| Emergency | MFA + conduit-admin + reason | Post-facto SNOW incident | None |

### Production delete flow

1. Developer calls `DELETE /api/v1/connections/{id}`
2. Policy engine: prod → SNOW CHG + step-up required
3. Returns 202 with CHG number and MFA challenge URL
4. Manager approves CHG in ServiceNow
5. Developer completes MFA step-up
6. Both gates passed → 30-min grace period starts
7. Connection stays live during grace, cancel URL available
8. After 30 min → teardown: delete endpoint, revoke Confluent, rotate key, seal audit, close CHG

### Emergency revoke (break-glass)

```
DELETE /api/v1/admin/connections/CONN-001?emergency=true
X-Step-Up: $MFA_TOKEN
X-Reason: "Security incident — credential compromise"
```

Immediate teardown. SNOW incident auto-created post-facto.
