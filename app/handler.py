"""Service Health Monitor - probe an allow-listed HTTPS URL and emit a metric."""
import json
import os
import urllib.error
import urllib.request
from urllib.parse import urlparse

APP_VERSION = os.environ.get("APP_VERSION", "dev")
TARGET_URL = os.environ.get("TARGET_URL", "https://example.com/health")
ALLOWED_HOSTS = set(
    h.strip().lower()
    for h in os.environ.get("ALLOWED_HOSTS", "example.com").split(",")
    if h.strip()
)
METRIC_NAMESPACE = os.environ.get("METRIC_NAMESPACE", "H3/unknown")
METRIC_NAME = "HealthCheckFailed"

_cw = None


def cloudwatch():
    global _cw
    if _cw is None:
        import boto3
        _cw = boto3.client("cloudwatch")
    return _cw


def validate_target(url):
    parsed = urlparse(url)
    if parsed.scheme != "https":
        raise ValueError("TARGET_URL must use https")
    host = (parsed.hostname or "").lower()
    if host not in ALLOWED_HOSTS:
        raise ValueError("host not allow-listed")
    return url


def probe(url):
    req = urllib.request.Request(url, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=5) as resp:
            return 200 <= resp.status < 400
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return False


def put_metric(failed):
    cloudwatch().put_metric_data(
        Namespace=METRIC_NAMESPACE,
        MetricData=[{
            "MetricName": METRIC_NAME,
            "Value": 1.0 if failed else 0.0,
            "Unit": "Count",
        }],
    )


def lambda_handler(event, context):
    url = validate_target(TARGET_URL)
    ok = probe(url)
    put_metric(failed=not ok)
    return {
        "ok": ok,
        "target": url,
        "failed": 0 if ok else 1,
        "version": APP_VERSION,
    }
