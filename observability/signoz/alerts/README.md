# SigNoz Alerts → Port Webhook

Optional demo alerts that complement the primary `POST /evaluate` evaluator API.

## Configuration

Set the Port remediation webhook URL (from Person C):

```bash
export PORT_REMEDIATION_WEBHOOK_URL=http://localhost:3001/webhooks/signoz
```

## Alert definitions

| File | Trigger | Threshold |
|------|---------|-----------|
| [`latency-alert.json`](./latency-alert.json) | p95 Product Snapshot latency | > 2.2s |
| [`error-alert.json`](./error-alert.json) | Product Snapshot error rate | > 1% |

## Setup in SigNoz UI

1. Start SigNoz: `npm run signoz:up`
2. Open http://localhost:8080 → **Alerts** → **New Alert**
3. Create alerts matching the JSON definitions above
4. Set notification channel to **Webhook** with Person C's URL
5. Test with `npm run telemetry:scenarios` then flip to `pricing-v2-break` telemetry

## Webhook payload (both alerts)

Person C should accept:

```json
{
  "alert_type": "latency_threshold | error_rate_threshold",
  "factory_run_id": "RUN-001",
  "candidate_id": "BASELINE",
  "scenario": "baseline-v1",
  "message": "...",
  "signoz_filter": "..."
}
```

## Primary vs alert path

| Path | When | Owner |
|------|------|-------|
| `POST http://localhost:8090/evaluate` | After each factory run (deterministic) | Person C invokes |
| SigNoz webhook | Real-time threshold breach (demo drama) | Person B configures, Person C receives |

The evaluator API remains the source of truth for candidate PASS/FAIL and score.

## Coordination checklist for Person C

- [ ] Provide `PORT_REMEDIATION_WEBHOOK_URL`
- [ ] Confirm webhook handler creates/updates Port incident
- [ ] Map `factory_run_id` / `candidate_id` to Port entities
- [ ] Deduplicate alert + evaluate events for same run
