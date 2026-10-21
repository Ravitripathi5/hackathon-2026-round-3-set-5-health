#!/usr/bin/env python3
"""Secure Event Delivery - Part A build verifier.

Participants:  python3 tools/check_build.py --id p07
Organizers:    imported by organizer/grade.py (same checks, organizer credentials).

Checks the local work folder and the live resources in the AWS sandbox (read-only,
except for the functional test that sends one test request, message, or file).
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from urllib.parse import urlparse

REGION = "ap-south-1"
SETS = {1: "upload", 2: "payments", 3: "fanout", 4: "archive", 5: "health"}
POLL_SECONDS = 120
HACKATHON_TAG = "secure-event-delivery"


class Report:
    def __init__(self):
        self.items = []

    def add(self, section, cid, label, pts, ok, detail=""):
        self.items.append(
            {"section": section, "id": cid, "label": label, "max": pts,
             "points": pts if ok else 0, "ok": bool(ok), "detail": str(detail)[:300]}
        )

    def total(self, section=None):
        rows = [i for i in self.items if section is None or i["section"] == section]
        return sum(i["points"] for i in rows), sum(i["max"] for i in rows)


def run(cmd, cwd=None, timeout=600, env=None):
    try:
        p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, env=env)
        return p.returncode, p.stdout, p.stderr
    except FileNotFoundError:
        return 127, "", f"{cmd[0]} not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"


def aws(*args, timeout=60):
    rc, out, err = run(["aws", *args, "--region", REGION, "--output", "json"], timeout=timeout)
    data = None
    if rc == 0 and out.strip():
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = out
    return rc == 0, data, err.strip()


def invoke(function, payload, qualifier=None):
    fd, out = tempfile.mkstemp(suffix=".json")
    os.close(fd)
    args = ["lambda", "invoke", "--function-name", function, "--cli-binary-format",
            "raw-in-base64-out", "--payload", json.dumps(payload)]
    if qualifier:
        args += ["--qualifier", qualifier]
    ok, meta, err = aws(*args, out)
    try:
        body = open(out).read()
    finally:
        os.remove(out)
    if not ok:
        return None, err
    if isinstance(meta, dict) and meta.get("FunctionError"):
        return None, body
    try:
        return json.loads(body), ""
    except json.JSONDecodeError:
        return None, body


def unwrap_proxy_response(value):
    """Return the JSON body from an API Gateway/Lambda URL response envelope."""
    if not isinstance(value, dict) or "body" not in value:
        return value
    body = value.get("body")
    if not isinstance(body, str):
        return value
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return value
    return parsed if isinstance(parsed, dict) else value


def read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def check_package(rep, work):
    rc, out, err = run([sys.executable, "-m", "unittest", "discover", "-s", "app"], cwd=work, timeout=120)
    rep.add("A", "A1.tests", "Unit tests pass", 3, rc == 0, (err or out).strip().splitlines()[-1:] if rc else "ok")
    df = read(os.path.join(work, "Dockerfile"))
    base = re.search(r"(?im)^FROM\s+public\.ecr\.aws/lambda/python:3\.12", df)
    cmd = "handler.lambda_handler" in df
    ver = re.search(r"APP_VERSION", df)
    rep.add("A", "A1.dockerfile", "Dockerfile: Lambda Python 3.12 base, handler CMD, APP_VERSION", 2,
            bool(base and cmd and ver), f"base={bool(base)} cmd={cmd} version={bool(ver)}")


def check_iac_static(rep, work):
    infra = os.path.join(work, "infra")
    rc, out, err = run(["terraform", "fmt", "-check", "-recursive"], cwd=infra, timeout=60)
    rep.add("A", "A3.fmt", "terraform fmt -check", 2, rc == 0, out.strip() or err.strip() or "ok")

    tmp = tempfile.mkdtemp(prefix="h3-validate-")
    try:
        for name in os.listdir(infra):
            if name.endswith(".tf"):
                shutil.copy(os.path.join(infra, name), tmp)
        env = dict(os.environ)
        cache = os.path.expanduser("~/.terraform.d/plugin-cache")
        os.makedirs(cache, exist_ok=True)
        env["TF_PLUGIN_CACHE_DIR"] = cache
        rc, out, err = run(["terraform", "init", "-backend=false", "-input=false", "-no-color"], cwd=tmp, env=env)
        if rc == 0:
            rc, out, err = run(["terraform", "validate", "-no-color"], cwd=tmp, env=env)
        rep.add("A", "A3.validate", "terraform validate", 2, rc == 0, (err or out).strip()[-300:] or "ok")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    tf = "\n".join(read(os.path.join(infra, n)) for n in os.listdir(infra) if n.endswith(".tf"))
    bad = []
    if re.search(r"\b\d{12}\b", tf):
        bad.append("12-digit account id")
    if re.search(r"AKIA[0-9A-Z]{16}", tf):
        bad.append("access key id")
    if re.search(r"(?m)^\s*(access_key|secret_key|token)\s*=", tf):
        bad.append("provider credentials")
    rep.add("A", "A3.nohardcode", "No hardcoded account ID or credentials in infra/", 2, not bad, ", ".join(bad) or "ok")


def check_ci(rep, work):
    wf = ""
    for n in ("deploy.yml", "deploy.yaml"):
        wf = wf or read(os.path.join(work, ".github", "workflows", n))
    present = bool(wf.strip())
    rep.add("A", "A6.tests", "CI runs unit tests", 1, present and re.search(r"unittest|pytest", wf), "" if present else "missing .github/workflows/deploy.yml")
    oidc = present and "configure-aws-credentials" in wf and "role-to-assume" in wf and re.search(r"id-token:\s*write", wf)
    rep.add("A", "A6.oidc", "CI uses OIDC (role-to-assume + id-token: write)", 1, oidc)
    static = re.search(r"aws-access-key-id|aws-secret-access-key|AWS_SECRET_ACCESS_KEY|AWS_ACCESS_KEY_ID", wf)
    rep.add("A", "A6.nokeys", "CI has no stored AWS access keys", 1, bool(oidc) and not static)
    build = present and re.search(r"docker (buildx )?build|build-push-action", wf) and re.search(r"amazon-ecr-login|ecr get-login-password", wf)
    rep.add("A", "A6.image", "CI builds image and logs in / pushes to ECR", 1, build)
    tfc = present and re.search(r"terraform\s+fmt\s+-check", wf) and "terraform validate" in wf and "terraform plan" in wf
    rep.add("A", "A6.terraform", "CI runs terraform fmt -check, validate, plan", 1, tfc)


def check_registry(rep, prefix, app):
    repo = f"{prefix}-{app}"
    ok, data, err = aws("ecr", "describe-repositories", "--repository-names", repo)
    r = data["repositories"][0] if ok else {}
    rep.add("A", "A2.repo", f"ECR repository {repo} exists", 2, ok, err or "ok")
    rep.add("A", "A2.scan", "Scan on push enabled", 2, r.get("imageScanningConfiguration", {}).get("scanOnPush") is True)
    rep.add("A", "A2.immutable", "Tag mutability IMMUTABLE", 2, r.get("imageTagMutability") == "IMMUTABLE")
    ok, _, err = aws("ecr", "describe-images", "--repository-name", repo, "--image-ids", "imageTag=v1")
    rep.add("A", "A1.image", f"Image {repo}:v1 pushed", 3, ok, err or "ok")


def check_boundary(rep, prefix, app, pid):
    ok, data, err = aws("iam", "get-role", "--role-name", f"{prefix}-{app}-role")
    arn = (data or {}).get("Role", {}).get("PermissionsBoundary", {}).get("PermissionsBoundaryArn", "") if ok else ""
    rep.add("A", "A3.boundary", f"Role {prefix}-{app}-role uses the permissions boundary", 2,
            arn.endswith(f":policy/h3-{pid}-boundary"), arn or err)


def check_function(rep, fn):
    ok, data, err = aws("lambda", "get-function", "--function-name", fn)
    cfg = (data or {}).get("Configuration", {}) if ok else {}
    image_uri = ((data or {}).get("Code") or {}).get("ImageUri", "") if ok else ""
    good = (
        cfg.get("PackageType") == "Image"
        and cfg.get("State") == "Active"
        and cfg.get("LastUpdateStatus") == "Successful"
        and cfg.get("Architectures") == ["arm64"]
        and image_uri.endswith(":v1")
    )
    rep.add("A", "A4.function", f"Lambda {fn} is Active on arm64 and uses image :v1", 3, good,
            err or f"package={cfg.get('PackageType')} state={cfg.get('State')} "
                   f"architectures={cfg.get('Architectures')} image={image_uri}")
    return cfg


def check_retention(rep, fn, pts=2):
    ok, data, err = aws("logs", "describe-log-groups", "--log-group-name-prefix", f"/aws/lambda/{fn}")
    groups = [g for g in (data or {}).get("logGroups", []) if g["logGroupName"] == f"/aws/lambda/{fn}"] if ok else []
    days = groups[0].get("retentionInDays") if groups else None
    rep.add("A", "A5.retention", "Log group retention is 14 days", pts, days == 14, f"retention={days}")


def check_public_block(rep, bucket, pts, cid="A5.publicblock"):
    ok, data, err = aws("s3api", "get-public-access-block", "--bucket", bucket)
    cfg = (data or {}).get("PublicAccessBlockConfiguration", {}) if ok else {}
    keys = ["BlockPublicAcls", "IgnorePublicAcls", "BlockPublicPolicy", "RestrictPublicBuckets"]
    rep.add("A", cid, "All four S3 Block Public Access settings on", pts, all(cfg.get(k) for k in keys), err or cfg)


def check_tags(rep, pid, fn, repo):
    ok, data, err = aws("resourcegroupstaggingapi", "get-resources", "--tag-filters",
                        f"Key=Participant,Values={pid}", f"Key=Hackathon,Values={HACKATHON_TAG}")
    arns = [r["ResourceARN"] for r in (data or {}).get("ResourceTagMappingList", [])] if ok else []
    good = any(a.endswith(f":function:{fn}") for a in arns) and any(a.endswith(f":repository/{repo}") for a in arns)
    rep.add("C", "C.tags", "Resources carry Hackathon/Participant tags", 2, good, err or f"{len(arns)} tagged resources")


def live_set1(rep, prefix, stamp, account_id):
    fn, bucket = f"{prefix}-upload", f"{prefix}-uploads-{account_id}"
    check_function(rep, fn)
    key = f"verify/{stamp}.txt"
    res, err = invoke(fn, {"key": key, "content_type": "text/plain"})
    res = unwrap_proxy_response(res)
    url = (res or {}).get("upload_url") if isinstance(res, dict) else None
    expires = (res or {}).get("expires_in") if isinstance(res, dict) else None
    url_ok, url_data, url_err = aws("lambda", "get-function-url-config", "--function-name", fn)
    auth = (url_data or {}).get("AuthType") if url_ok else None
    rep.add("A", "A4.presign", "Invoke returns a short-lived PUT URL and Function URL uses AWS_IAM", 5,
            bool(url) and isinstance(expires, int) and 0 < expires <= 300 and auth == "AWS_IAM",
            err or url_err or {"response": res, "function_url_auth": auth})

    put_ok = False
    if url:
        try:
            req = urllib.request.Request(url, data=b"h3-verify", method="PUT")
            req.add_header("Content-Type", "text/plain")
            with urllib.request.urlopen(req, timeout=30) as resp:
                put_ok = 200 <= resp.status < 300
        except Exception as exc:  # noqa: BLE001
            err = str(exc)
    rep.add("A", "A4.put", "Presigned URL accepts a small PUT", 5, put_ok, err or "ok")

    ok, _, err2 = aws("s3api", "head-object", "--bucket", bucket, "--key", key)
    rep.add("A", "A4.exists", f"Object s3://{bucket}/{key} exists", 3, ok, err2 or "ok")

    ok, data, err = aws("s3api", "get-bucket-policy", "--bucket", bucket)
    policy_txt = (data or {}).get("Policy", "") if ok else ""
    denies_insecure = "aws:SecureTransport" in policy_txt and "false" in policy_txt.lower()
    rep.add("A", "A4.deny_http", "Bucket policy denies insecure transport", 2, denies_insecure, err or policy_txt[:200])

    ok, _, err = aws("s3api", "get-bucket-encryption", "--bucket", bucket)
    rep.add("A", "A5.encryption", "Default bucket encryption configured", 2, ok, err or "ok")
    check_public_block(rep, bucket, 2)
    check_retention(rep, fn, pts=1)
    return fn


def live_set2(rep, prefix, stamp):
    fn, qname, table = f"{prefix}-payments", f"{prefix}-payments.fifo", f"{prefix}-payments"
    check_function(rep, fn)
    ok, data, err = aws("lambda", "list-event-source-mappings", "--function-name", fn)
    esm = [m for m in (data or {}).get("EventSourceMappings", []) if m.get("EventSourceArn", "").endswith(f":{qname}")] if ok else []
    rep.add("A", "A4.esm", "Event source mapping from FIFO queue is Enabled", 3,
            any(m.get("State") == "Enabled" for m in esm), err or [m.get("State") for m in esm])

    ok, data, err = aws("sqs", "get-queue-url", "--queue-name", qname)
    qurl = (data or {}).get("QueueUrl")
    payment_id = f"pay-{stamp}"
    item = None
    if qurl:
        for amount, dedup in ((10.0, f"d1-{stamp}"), (99.0, f"d2-{stamp}")):
            body = json.dumps({"payment_id": payment_id, "amount": amount})
            aws("sqs", "send-message", "--queue-url", qurl, "--message-body", body,
                "--message-group-id", "verify", "--message-deduplication-id", dedup)
        deadline = time.time() + POLL_SECONDS
        while time.time() < deadline:
            time.sleep(5)
            _, got, _ = aws(
                "dynamodb", "get-item", "--table-name", table,
                "--key", json.dumps({"payment_id": {"S": payment_id}}), "--consistent-read",
            )
            item = (got or {}).get("Item")
            _, qdata, _ = aws(
                "sqs", "get-queue-attributes", "--queue-url", qurl,
                "--attribute-names", "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible", "ApproximateNumberOfMessagesDelayed",
            )
            qa = (qdata or {}).get("Attributes", {})
            pending = sum(int(qa.get(k, "0")) for k in (
                "ApproximateNumberOfMessages",
                "ApproximateNumberOfMessagesNotVisible",
                "ApproximateNumberOfMessagesDelayed",
            ))
            if item is not None and pending == 0:
                break
    amount_attr = (item or {}).get("amount", {})
    stored_amount = amount_attr.get("S", amount_attr.get("N"))
    try:
        first_write_preserved = float(stored_amount) == 10.0
    except (TypeError, ValueError):
        first_write_preserved = False
    rep.add("A", "A4.idempotent", "Duplicate payment_id preserves the first DynamoDB write", 8,
            first_write_preserved, err or f"stored amount={stored_amount}")

    attrs = {}
    if qurl:
        _, data, _ = aws("sqs", "get-queue-attributes", "--queue-url", qurl, "--attribute-names", "All")
        attrs = (data or {}).get("Attributes", {})
    fifo_ok = attrs.get("FifoQueue") == "true" and attrs.get("ContentBasedDeduplication") == "true"
    rep.add("A", "A4.fifo", "Queue is FIFO with content-based deduplication", 3, fifo_ok, attrs)

    try:
        redrive = json.loads(attrs.get("RedrivePolicy", "{}"))
    except json.JSONDecodeError:
        redrive = {}
    rep.add("A", "A5.redrive", "Redrive to -payments-dlq.fifo after 3 receives", 3,
            str(redrive.get("deadLetterTargetArn", "")).endswith(f":{prefix}-payments-dlq.fifo")
            and int(redrive.get("maxReceiveCount", 0)) == 3, redrive)
    _, data, _ = aws("sqs", "get-queue-url", "--queue-name", f"{prefix}-payments-dlq.fifo")
    dlq_attrs = {}
    if data:
        _, d2, _ = aws("sqs", "get-queue-attributes", "--queue-url", data["QueueUrl"], "--attribute-names", "All")
        dlq_attrs = (d2 or {}).get("Attributes", {})
    sse = lambda a: a.get("SqsManagedSseEnabled") == "true" or bool(a.get("KmsMasterKeyId"))
    rep.add("A", "A5.sse", "Server-side encryption on both queues", 2, sse(attrs) and sse(dlq_attrs))
    check_retention(rep, fn, pts=1)
    return fn


def live_set3(rep, prefix, stamp):
    fn, table = f"{prefix}-fanout", f"{prefix}-notifications"
    topic = f"{prefix}-notifications"
    check_function(rep, fn)

    ok, data, err = aws("sns", "list-topics")
    topic_arn = None
    for t in (data or {}).get("Topics", []) if ok else []:
        if t["TopicArn"].endswith(f":{topic}"):
            topic_arn = t["TopicArn"]
            break
    email_id = f"email-{stamp}"
    sms_id = f"sms-{stamp}"
    if topic_arn:
        aws("sns", "publish", "--topic-arn", topic_arn, "--message",
            json.dumps({"event_id": email_id, "body": "hello"}),
            "--message-attributes", json.dumps({"channel": {"DataType": "String", "StringValue": "email"}}))
        aws("sns", "publish", "--topic-arn", topic_arn, "--message",
            json.dumps({"event_id": sms_id, "body": "hello"}),
            "--message-attributes", json.dumps({"channel": {"DataType": "String", "StringValue": "sms"}}))

    email_item = None
    sms_item = None
    deadline = time.time() + POLL_SECONDS
    while time.time() < deadline:
        time.sleep(5)
        _, got, _ = aws("dynamodb", "get-item", "--table-name", table,
                        "--key", json.dumps({"event_id": {"S": email_id}}))
        email_item = (got or {}).get("Item")
        _, got2, _ = aws("dynamodb", "get-item", "--table-name", table,
                         "--key", json.dumps({"event_id": {"S": sms_id}}))
        sms_item = (got2 or {}).get("Item")
        if email_item is not None:
            time.sleep(5)
            _, got2, _ = aws("dynamodb", "get-item", "--table-name", table,
                             "--key", json.dumps({"event_id": {"S": sms_id}}))
            sms_item = (got2 or {}).get("Item")
            break
    rep.add("A", "A4.email", "Publish channel=email creates a DynamoDB item", 6, email_item is not None, err or email_item)
    rep.add("A", "A4.sms", "Publish channel=sms does not create a table item", 5, email_item is not None and sms_item is None, sms_item)

    # Both subscriptions must have the exact channel filter and raw delivery.
    filter_state = {"email": False, "sms": False}
    raw_state = {"email": False, "sms": False}
    if topic_arn:
        _, subs, _ = aws("sns", "list-subscriptions-by-topic", "--topic-arn", topic_arn)
        for sub in (subs or {}).get("Subscriptions", []):
            endpoint = sub.get("Endpoint", "")
            channel = next((c for c in filter_state if endpoint.endswith(f":{prefix}-notify-{c}")), None)
            if not channel:
                continue
            _, attrs, _ = aws("sns", "get-subscription-attributes", "--subscription-arn", sub["SubscriptionArn"])
            a = (attrs or {}).get("Attributes", {})
            try:
                fp = json.loads(a.get("FilterPolicy") or "{}")
            except json.JSONDecodeError:
                fp = {}
            filter_state[channel] = fp.get("channel") == [channel]
            raw_state[channel] = a.get("RawMessageDelivery") == "true"
    filter_ok = all(filter_state.values())
    raw_ok = all(raw_state.values())
    rep.add("A", "A4.filters", "SNS subscriptions use channel filter policies", 3, filter_ok)
    rep.add("A", "A5.raw", "Raw message delivery enabled on both subscriptions", 2, raw_ok)

    # Both queue policies must be scoped to the topic.
    queue_policy_state = []
    for qn in (f"{prefix}-notify-email", f"{prefix}-notify-sms"):
        _, data, _ = aws("sqs", "get-queue-url", "--queue-name", qn)
        if not data:
            queue_policy_state.append(False)
            continue
        _, attrs, _ = aws("sqs", "get-queue-attributes", "--queue-url", data["QueueUrl"], "--attribute-names", "Policy")
        pol = (attrs or {}).get("Attributes", {}).get("Policy", "")
        source_account = topic_arn.split(":")[4] if topic_arn else ""
        queue_policy_state.append(bool(
            topic_arn
            and topic_arn in pol
            and "sns.amazonaws.com" in pol
            and "aws:SourceAccount" in pol
            and source_account in pol
        ))
    q_ok = len(queue_policy_state) == 2 and all(queue_policy_state)
    rep.add("A", "A5.queue_policy", "Queue policies scoped to the SNS topic", 2, q_ok)
    check_retention(rep, fn, pts=2)
    return fn


def live_set4(rep, prefix, stamp, account_id):
    fn, bucket = f"{prefix}-archive", f"{prefix}-archive-{account_id}"
    app_lg = f"/{prefix}/app"
    check_function(rep, fn)

    # Put a log event into the app log group
    stream = f"verify-{stamp}"
    created, _, create_err = aws(
        "logs", "create-log-stream", "--log-group-name", app_lg, "--log-stream-name", stream
    )
    sent, _, send_err = aws(
        "logs", "put-log-events", "--log-group-name", app_lg, "--log-stream-name", stream,
        "--log-events", json.dumps([{"timestamp": int(time.time() * 1000), "message": f"archive-verify-{stamp}"}])
    ) if created else (False, None, create_err)

    found = None
    deadline = time.time() + POLL_SECONDS
    while time.time() < deadline:
        time.sleep(8)
        ok, data, err = aws("s3api", "list-objects-v2", "--bucket", bucket, "--prefix", "archive/")
        for obj in (data or {}).get("Contents", []) if ok else []:
            # download and look for stamp
            fd, path = tempfile.mkstemp()
            os.close(fd)
            aws("s3api", "get-object", "--bucket", bucket, "--key", obj["Key"], path)
            try:
                body = open(path, encoding="utf-8", errors="replace").read()
            finally:
                os.remove(path)
            if stamp in body:
                found = obj["Key"]
                break
        if found:
            break
    rep.add("A", "A4.archive", "Log event appears as NDJSON under s3 archive/ within ~2 minutes", 8,
            sent and found is not None, found or send_err or create_err or "no object")

    _, pol, _ = aws("lambda", "get-policy", "--function-name", fn)
    policy_text = json.dumps(pol or {})
    allowed = (
        "logs.amazonaws.com" in policy_text
        and app_lg in policy_text
        and account_id in policy_text
    )
    rep.add("A", "A4.permission", "Logs permission is scoped by source ARN and account", 3, allowed)

    ok, data, err = aws("s3api", "get-bucket-lifecycle-configuration", "--bucket", bucket)
    life_ok = False
    for rule in (data or {}).get("Rules", []) if ok else []:
        filt = rule.get("Filter") or {}
        prefix_f = filt.get("Prefix") or (filt.get("And") or {}).get("Prefix") or rule.get("Prefix") or ""
        exp = rule.get("Expiration") or {}
        days = exp.get("Days")
        if rule.get("Status") == "Enabled" and prefix_f == "archive/" and days == 30:
            life_ok = True
    rep.add("A", "A4.lifecycle", "Lifecycle expires archive/ objects after 30 days", 4, life_ok, err or data)

    check_public_block(rep, bucket, 3)
    check_retention(rep, fn, pts=2)
    return fn


def live_set5(rep, prefix, stamp, pid):
    fn = f"{prefix}-health"
    check_function(rep, fn)
    probe_started = time.time() - 5
    res, err = invoke(fn, {"probe": True})
    rep.add("A", "A4.invoke", "Health probe invoke succeeds", 0, res is not None, err or res)  # 0 pts helper

    ns = f"H3/{pid}"
    dps = []
    metric_err = ""
    deadline = time.time() + POLL_SECONDS
    while res is not None and time.time() < deadline:
        end = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() + 60))
        start = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(probe_started))
        ok, data, metric_err = aws(
            "cloudwatch", "get-metric-statistics",
            "--namespace", ns, "--metric-name", "HealthCheckFailed",
            "--start-time", start, "--end-time", end,
            "--period", "60", "--statistics", "Sum",
        )
        dps = (data or {}).get("Datapoints", []) if ok else []
        if dps:
            break
        time.sleep(5)
    rep.add("A", "A4.metric", f"Custom metric {ns}/HealthCheckFailed has a datapoint", 5,
            res is not None and bool(dps), err or metric_err or f"datapoints={len(dps)}")

    ok, data, err = aws("cloudwatch", "describe-alarms", "--alarm-names", f"{prefix}-health-failed")
    alarms = (data or {}).get("MetricAlarms", []) if ok else []
    a = alarms[0] if alarms else {}
    alarm_ok = (
        a.get("MetricName") == "HealthCheckFailed"
        and a.get("Namespace") == ns
        and a.get("Threshold") == 1.0
        and a.get("ComparisonOperator") == "GreaterThanOrEqualToThreshold"
        and any(x.endswith(f":{prefix}-health-alerts") for x in a.get("AlarmActions", []))
    )
    rep.add("A", "A4.alarm", "Alarm on HealthCheckFailed >= 1 notifies SNS", 4, alarm_ok, err or a)

    rule = f"{prefix}-health"
    ok, data, err = aws("events", "describe-rule", "--name", rule)
    enabled = ok and data.get("State") == "ENABLED" and data.get("ScheduleExpression") == "rate(5 minutes)"
    _, tgt, _ = aws("events", "list-targets-by-rule", "--rule", rule)
    targeted = any(fn in t.get("Arn", "") for t in (tgt or {}).get("Targets", []))
    rep.add("A", "A4.rule", "EventBridge rate(5 minutes) targets the function", 4,
            enabled and targeted, err or f"enabled={enabled} target={targeted}")

    # Allow-list: verify the configured target is an exact member.
    ok, data, err = aws("lambda", "get-function-configuration", "--function-name", fn)
    env = (data or {}).get("Environment", {}).get("Variables", {}) if ok else {}
    target = env.get("TARGET_URL", "")
    allowed_hosts = {h.strip().lower() for h in env.get("ALLOWED_HOSTS", "").split(",") if h.strip()}
    parsed = urlparse(target)
    allow_ok = parsed.scheme == "https" and bool(parsed.hostname) and parsed.hostname.lower() in allowed_hosts
    rep.add("A", "A4.allowlist", "TARGET_URL is https and allow-listed host", 3, allow_ok, target or err)

    ok, data, err = aws("sns", "list-topics")
    sns_ok = any(t["TopicArn"].endswith(f":{prefix}-health-alerts") for t in (data or {}).get("Topics", [])) if ok else False
    rep.add("A", "A5.sns", "SNS alert topic exists", 2, sns_ok, err or "ok")
    check_retention(rep, fn, pts=2)
    return fn


def verify(set_no, pid, work, live=True):
    rep = Report()
    app = SETS[set_no]
    prefix = f"h3-{pid}"
    check_package(rep, work)
    check_iac_static(rep, work)
    check_ci(rep, work)
    if not live:
        return rep
    ok, ident, err = aws("sts", "get-caller-identity")
    if not ok:
        rep.add("A", "A0.aws", "AWS credentials work", 0, False, err)
        return rep
    stamp = time.strftime("%Y%m%d%H%M%S")
    account_id = str((ident or {}).get("Account", ""))
    check_registry(rep, prefix, app)
    check_boundary(rep, prefix, app, pid)
    if set_no == 1:
        fn = live_set1(rep, prefix, stamp, account_id)
    elif set_no == 2:
        fn = live_set2(rep, prefix, stamp)
    elif set_no == 3:
        fn = live_set3(rep, prefix, stamp)
    elif set_no == 4:
        fn = live_set4(rep, prefix, stamp, account_id)
    else:
        fn = live_set5(rep, prefix, stamp, pid)
    check_tags(rep, pid, fn, f"{prefix}-{app}")
    return rep


def print_report(rep, title):
    print(f"\n{title}\n" + "-" * len(title))
    for i in rep.items:
        mark = "PASS" if i["ok"] else "FAIL"
        line = f"[{mark}] {i['id']:<16} {i['points']:>2}/{i['max']:<2} {i['label']}"
        print(line)
        if not i["ok"] and i["detail"]:
            print(f"        -> {i['detail']}")
    got, mx = rep.total("A")
    print(f"\nPart A build score: {got}/{mx}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--id", required=True, help="participant id, e.g. p07")
    ap.add_argument("--set", type=int, choices=sorted(SETS), help="set number (default: read from set.json)")
    ap.add_argument("--workdir", default=".", help="work folder (default: current folder)")
    ap.add_argument("--no-live", action="store_true", help="only run local checks")
    args = ap.parse_args()
    if not re.fullmatch(r"p\d{2}", args.id):
        sys.exit("--id must look like p07")
    set_no = args.set
    if set_no is None:
        try:
            set_no = json.load(open(os.path.join(args.workdir, "set.json")))["set"]
        except (OSError, KeyError, json.JSONDecodeError):
            sys.exit("cannot read set.json; pass --set")
    rep = verify(set_no, args.id, os.path.abspath(args.workdir), live=not args.no_live)
    print_report(rep, f"Set {set_no} ({SETS[set_no]}) build check for {args.id}")


if __name__ == "__main__":
    main()
