# Set 5 - Service Health Monitor

**Scenario.** Every five minutes, EventBridge invokes a Lambda health probe. The probe only allows HTTPS URLs on an allow-listed host, publishes custom metric `HealthCheckFailed` under namespace `H3/<id>`, and an alarm (>= 1) notifies SNS.

## Part A names
| Resource | Name |
|---|---|
| Lambda / ECR / role | `h3-<id>-health` (+ `-role`) |
| Rule | `h3-<id>-health`, `rate(5 minutes)` |
| Metric | namespace `H3/<id>`, name `HealthCheckFailed` |
| Alarm | `h3-<id>-health-failed` (>= 1) → SNS `h3-<id>-health-alerts` |
| Env | `TARGET_URL` (https + allow-listed), `ALLOWED_HOSTS`, `METRIC_NAMESPACE` |

**Live:** invoke the function; metric datapoint exists; alarm and rule target exist.

Same packaging / IMMUTABLE ECR / OIDC CI rules as other sets.

## Part B / C / Submit
Six `crack-files/` fixes + `FINDINGS.md` + submit. No destroy.
