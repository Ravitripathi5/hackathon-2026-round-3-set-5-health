# Set 5 - Service Health Monitor

**Scenario.** Every five minutes, EventBridge invokes a Lambda health probe. The probe only allows HTTPS URLs on an allow-listed host, publishes custom metric `HealthCheckFailed` under namespace `H3/<id>`, and an alarm (>= 1) notifies SNS.

## Part A - Build and deploy (50 points)

| What | Exact name or setting |
|---|---|
| ECR | `h3-<id>-health`, scan on push **on**, **IMMUTABLE**; image `:v1` |
| Role | `h3-<id>-health-role` with the supplied permissions boundary |
| Lambda | `h3-<id>-health`, Image `:v1`, arm64 |
| Env | `TARGET_URL=https://example.com/health`, `ALLOWED_HOSTS=example.com`, `METRIC_NAMESPACE=H3/<id>`, `APP_VERSION=v1` |
| Rule | `h3-<id>-health`, exact schedule `rate(5 minutes)`, targets Lambda |
| Permission | EventBridge permission scoped to the rule source ARN and source account |
| Metric | Namespace `H3/<id>`, name `HealthCheckFailed` |
| Alarm | `h3-<id>-health-failed`, threshold >= 1, action SNS `h3-<id>-health-alerts` |
| Logs | `/aws/lambda/h3-<id>-health`, retention 14 |

**Live:** invoke the function; metric datapoint exists; alarm and rule target exist.

Root Dockerfile: Lambda Python 3.12, `handler.lambda_handler`, and `APP_VERSION`. Root `deploy.yml`: tests, OIDC, ECR build/push, Terraform fmt/validate/plan, and no static AWS keys. Terraform must pass fmt/validate and contain no hardcoded account ID or credentials.

Run `python3 tools/check_build.py --id <id>` after deployment.

## Part B / C / Submit
Six `crack-files/` fixes + `FINDINGS.md` + submit. No destroy.
