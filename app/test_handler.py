import os
import unittest
from unittest import mock

os.environ["TARGET_URL"] = "https://example.com/health"
os.environ["ALLOWED_HOSTS"] = "example.com"
os.environ["METRIC_NAMESPACE"] = "H3/p01"
os.environ["APP_VERSION"] = "v1"

import handler  # noqa: E402


class HealthTests(unittest.TestCase):
    def test_rejects_http(self):
        old = handler.TARGET_URL
        handler.TARGET_URL = "http://example.com/x"
        try:
            with self.assertRaises(ValueError):
                handler.lambda_handler({}, None)
        finally:
            handler.TARGET_URL = old

    def test_rejects_other_host(self):
        old = handler.TARGET_URL
        handler.TARGET_URL = "https://evil.example/x"
        try:
            with self.assertRaises(ValueError):
                handler.lambda_handler({}, None)
        finally:
            handler.TARGET_URL = old

    def test_emits_metric(self):
        with mock.patch.object(handler, "probe", return_value=True), \
             mock.patch.object(handler, "cloudwatch") as cw:
            res = handler.lambda_handler({}, None)
        self.assertTrue(res["ok"])
        kwargs = cw.return_value.put_metric_data.call_args.kwargs
        self.assertEqual(kwargs["Namespace"], "H3/p01")
        self.assertEqual(kwargs["MetricData"][0]["MetricName"], "HealthCheckFailed")
        self.assertEqual(kwargs["MetricData"][0]["Value"], 0.0)


if __name__ == "__main__":
    unittest.main()
