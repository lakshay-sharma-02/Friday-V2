"""HTTP request primitive: preconditions, mocked responses, error handling.
Every test is self-contained — no real network requests."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from friday.errors import PreconditionError, PrimitiveError
from friday.l1 import http as http_mod
from tests.helpers import EnvTestCase


class TestHttpRequestPreconditions(EnvTestCase):
    def test_empty_url(self):
        with self.assertRaises(PreconditionError):
            http_mod.request("")

    def test_whitespace_url(self):
        with self.assertRaises(PreconditionError):
            http_mod.request("   ")

    def test_no_http_prefix(self):
        with self.assertRaises(PreconditionError):
            http_mod.request("ftp://example.com")

    def test_just_domain(self):
        with self.assertRaises(PreconditionError):
            http_mod.request("example.com")

    def test_invalid_method(self):
        with self.assertRaises(PreconditionError):
            http_mod.request("https://example.com", method="INVALID")

    def test_valid_methods(self):
        """GET, POST, PUT, DELETE, PATCH should all be accepted."""
        for method in ("GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"):
            with mock.patch("friday.l1.http.requests.request") as m:
                resp = mock.Mock()
                resp.status_code = 200
                resp.headers = {"Content-Type": "text/plain"}
                resp.text = "ok"
                resp.url = "https://example.com"
                m.return_value = resp
                result = http_mod.request("https://example.com", method=method)
                self.assertEqual(result["method"], method)
                m.assert_called_once()

    def test_method_case_insensitive(self):
        with mock.patch("friday.l1.http.requests.request") as m:
            resp = mock.Mock()
            resp.status_code = 200
            resp.headers = {}
            resp.text = ""
            resp.url = "https://example.com"
            m.return_value = resp
            result = http_mod.request("https://example.com", method="get")
            self.assertEqual(result["method"], "GET")


class TestHttpRequestMocked(EnvTestCase):
    def test_get_returns_structured_response(self):
        with mock.patch("friday.l1.http.requests.request") as m:
            resp = mock.Mock()
            resp.status_code = 200
            resp.headers = {"Content-Type": "application/json", "X-Custom": "yes"}
            resp.text = '{"key": "value"}'
            resp.json.return_value = {"key": "value"}
            resp.url = "https://api.example.com/data"
            m.return_value = resp

            result = http_mod.request("https://api.example.com/data")
            self.assertEqual(result["status_code"], 200)
            self.assertEqual(result["body"], {"key": "value"})
            self.assertEqual(result["url"], "https://api.example.com/data")
            self.assertEqual(result["method"], "GET")
            self.assertEqual(result["headers"]["X-Custom"], "yes")

    def test_get_non_json_returns_text(self):
        with mock.patch("friday.l1.http.requests.request") as m:
            resp = mock.Mock()
            resp.status_code = 200
            resp.headers = {"Content-Type": "text/html"}
            resp.text = "<html>Hello</html>"
            resp.url = "https://example.com"
            m.return_value = resp

            result = http_mod.request("https://example.com")
            self.assertEqual(result["body"], "<html>Hello</html>")

    def test_post_with_json_body(self):
        with mock.patch("friday.l1.http.requests.request") as m:
            resp = mock.Mock()
            resp.status_code = 201
            resp.headers = {"Content-Type": "application/json"}
            resp.text = '{"id": 123}'
            resp.url = "https://api.example.com/items"
            m.return_value = resp

            result = http_mod.request(
                "https://api.example.com/items",
                method="POST",
                body={"name": "test"},
            )
            self.assertEqual(result["status_code"], 201)
            # Verify json= was passed
            call_kwargs = m.call_args[1]
            self.assertEqual(call_kwargs["json"], {"name": "test"})

    def test_post_with_string_body(self):
        with mock.patch("friday.l1.http.requests.request") as m:
            resp = mock.Mock()
            resp.status_code = 200
            resp.headers = {}
            resp.text = "ok"
            resp.url = "https://example.com"
            m.return_value = resp

            http_mod.request(
                "https://example.com",
                method="POST",
                body="raw text",
            )
            call_kwargs = m.call_args[1]
            self.assertEqual(call_kwargs["data"], "raw text")

    def test_custom_headers_passed(self):
        with mock.patch("friday.l1.http.requests.request") as m:
            resp = mock.Mock()
            resp.status_code = 200
            resp.headers = {}
            resp.text = ""
            resp.url = "https://example.com"
            m.return_value = resp

            http_mod.request(
                "https://example.com",
                headers={"Authorization": "Bearer token123", "X-Custom": "val"},
            )
            call_kwargs = m.call_args[1]
            self.assertEqual(call_kwargs["headers"]["Authorization"], "Bearer token123")

    def test_timeout_passed(self):
        with mock.patch("friday.l1.http.requests.request") as m:
            resp = mock.Mock()
            resp.status_code = 200
            resp.headers = {}
            resp.text = ""
            resp.url = "https://example.com"
            m.return_value = resp

            http_mod.request("https://example.com", timeout_s=60)
            call_kwargs = m.call_args[1]
            self.assertEqual(call_kwargs["timeout"], 60)


class TestHttpRequestErrors(EnvTestCase):
    def test_timeout_raises_primitive_error(self):
        import requests as _requests

        with mock.patch("friday.l1.http.requests.request") as m:
            m.side_effect = _requests.Timeout("timed out")
            with self.assertRaises(PrimitiveError) as ctx:
                http_mod.request("https://example.com")
            self.assertIn("timed out", str(ctx.exception))

    def test_connection_error_raises_primitive_error(self):
        import requests as _requests

        with mock.patch("friday.l1.http.requests.request") as m:
            m.side_effect = _requests.ConnectionError("refused")
            with self.assertRaises(PrimitiveError) as ctx:
                http_mod.request("https://example.com")
            self.assertIn("connection failed", str(ctx.exception))

    def test_non_json_response_returns_text(self):
        with mock.patch("friday.l1.http.requests.request") as m:
            resp = mock.Mock()
            resp.status_code = 200
            resp.headers = {"Content-Type": "text/plain"}
            resp.text = "plain text response"
            resp.url = "https://example.com"
            m.return_value = resp

            result = http_mod.request("https://example.com")
            self.assertEqual(result["body"], "plain text response")


if __name__ == "__main__":
    unittest.main()
