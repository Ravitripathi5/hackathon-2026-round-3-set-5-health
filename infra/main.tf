# Set 5 - Service Health Monitor.
#
# TODO EventBridge rule ${local.prefix}-health schedule rate(5 minutes) -> Lambda
#      Permission scoped by rule source ARN and source account
# TODO Lambda/ECR/role ${local.prefix}-health; env TARGET_URL=https://example.com/health,
#      ALLOWED_HOSTS=example.com, METRIC_NAMESPACE=H3/<id>, APP_VERSION
# TODO CloudWatch alarm ${local.prefix}-health-failed on metric HealthCheckFailed >= 1
# TODO SNS ${local.prefix}-health-alerts as alarm action
# TODO Log retention 14
