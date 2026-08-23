"""L5 MCP server: the stdio JSON-RPC protocol (initialize / ping /
tools/list / tools/call), tool-schema derivation from real primitive
signatures, and the executor-boundary routing (registered+unblocked only,
refusals surface as isError, never a protocol crash). All hermetic: the
only primitives exercised are files.* against a temp dir."""

from __future__ import annotations

import json
import unittest

from friday.mcp_server import handle_message, list_tools
from tests.helpers import EnvTestCase


def _send(line: str) -> dict:
    """Send one JSON line, parse the JSON-RPC response dict."""
    resp = handle_message(line)
    assert resp is not None, f"no response for {line!r}"
    return json.loads(resp)


class TestProtocol(EnvTestCase):
    def test_initialize_handshake(self):
        r = _send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}))
        self.assertEqual(r["id"], 1)
        res = r["result"]
        self.assertEqual(res["protocolVersion"], "2024-11-05")
        self.assertEqual(res["serverInfo"]["name"], "friday")
        self.assertTrue(res["capabilities"]["tools"])

    def test_ping(self):
        r = _send(json.dumps({"jsonrpc": "2.0", "id": 2, "method": "ping"}))
        self.assertEqual(r["result"], {})

    def test_notification_gets_no_response(self):
        # initialized notification has no id -> no response line at all
        resp = handle_message(json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}))
        self.assertIsNone(resp)

    def test_unknown_method(self):
        r = _send(json.dumps({"jsonrpc": "2.0", "id": 3, "method": "nope"}))
        self.assertEqual(r["error"]["code"], -32601)

    def test_parse_error(self):
        r = _send("this is not json")
        self.assertEqual(r["error"]["code"], -32700)

    def test_non_dict_message(self):
        r = _send("[1, 2, 3]")
        self.assertEqual(r["error"]["code"], -32600)


class TestToolsList(EnvTestCase):
    def test_exposes_registered_primitives(self):
        names = {t["name"] for t in list_tools()}
        # a hermetic primitive is advertised under its MCP-safe name
        self.assertIn("files__read_text", names)
        self.assertIn("window__list_clients", names)
        # the destructive blocked primitive is NEVER advertised
        self.assertNotIn("window__shutdown", names)
        for n in names:
            # MCP spec: tool names match ^[a-zA-Z0-9_-]{1,64}$
            self.assertRegex(n, r"^[a-zA-Z0-9_-]{1,64}$")

    def test_schema_derived_from_signature(self):
        by_name = {t["name"]: t for t in list_tools()}
        schema = by_name["files__read_text"]["inputSchema"]
        self.assertEqual(schema["type"], "object")
        self.assertIn("path", schema["properties"])
        self.assertIn("path", schema["required"])
        self.assertEqual(schema["properties"]["path"]["type"], "string")
        # max_chars has a default -> optional, typed integer
        self.assertEqual(schema["properties"]["max_chars"]["type"], "integer")
        self.assertNotIn("max_chars", schema["required"])

    def test_description_carries_contract(self):
        by_name = {t["name"]: t for t in list_tools()}
        desc = by_name["files__read_text"]["description"]
        self.assertIn("files.read_text", desc)  # qualified name preserved
        self.assertIn("idempotency=", desc)


class TestToolsCall(EnvTestCase):
    def test_hermetic_primitive_call(self):
        d = self.mktmp()
        (d / "hello.txt").write_text("hi there", encoding="utf-8")
        r = _send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 10,
                    "method": "tools/call",
                    "params": {
                        "name": "files__read_text",
                        "arguments": {"path": str(d / "hello.txt")},
                    },
                }
            )
        )
        self.assertFalse(r["result"]["isError"])
        body = json.loads(r["result"]["content"][0]["text"])
        self.assertIn("hi there", body["text"])

    def test_unknown_tool_is_error_not_crash(self):
        r = _send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {"name": "no__such_primitive", "arguments": {}},
                }
            )
        )
        self.assertTrue(r["result"]["isError"])
        # the resolve boundary refuses it (module cannot be imported / no
        # registered contract) - the point is a clean isError, not a crash
        self.assertIn("ERROR: KeyError", r["result"]["content"][0]["text"])

    def test_blocked_primitive_refused(self):
        # window.shutdown is registered but EXECUTOR_BLOCKED - the MCP
        # boundary must refuse it exactly like a plan step would
        r = _send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 12,
                    "method": "tools/call",
                    "params": {"name": "window__shutdown", "arguments": {}},
                }
            )
        )
        self.assertTrue(r["result"]["isError"])
        self.assertIn("EXECUTOR_BLOCKED", r["result"]["content"][0]["text"])

    def test_missing_name_is_invalid_params(self):
        r = _send(json.dumps({"jsonrpc": "2.0", "id": 13, "method": "tools/call", "params": {}}))
        self.assertEqual(r["error"]["code"], -32602)

    def test_non_object_arguments_rejected(self):
        r = _send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 14,
                    "method": "tools/call",
                    "params": {"name": "files__read_text", "arguments": ["not", "a", "dict"]},
                }
            )
        )
        self.assertEqual(r["error"]["code"], -32602)

    def test_bad_kwarg_is_error_result(self):
        # files.read_text has no 'nope' parameter -> TypeError inside the
        # primitive -> isError result, never a protocol crash
        r = _send(
            json.dumps(
                {
                    "jsonrpc": "2.0",
                    "id": 15,
                    "method": "tools/call",
                    "params": {
                        "name": "files__read_text",
                        "arguments": {"path": "/nope", "nope": 1},
                    },
                }
            )
        )
        self.assertTrue(r["result"]["isError"])


if __name__ == "__main__":
    unittest.main()
