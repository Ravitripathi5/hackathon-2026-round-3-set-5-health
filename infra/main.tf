# Set 5 - Service Health Monitor.
#
# TODO EventBridge rule ${local.prefix}-health schedule rate(5 minutes) -> Lambda
# TODO Lambda/ECR/role ${local.prefix}-health; env TARGET_URL, ALLOWED_HOSTS, METRIC_NAMESPACE=H3/<id>
# TODO CloudWatch alarm ${local.prefix}-health-failed on metric HealthCheckFailed >= 1
# TODO SNS ${local.prefix}-health-alerts as alarm action
# TODO Log retention 14
