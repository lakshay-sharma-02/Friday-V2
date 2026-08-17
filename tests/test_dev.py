"""dev primitives: the FRIDAY_ALLOW_DANGEROUS gate fires BEFORE claude is
invoked, plain run is unaffected, and run_shell parses the claude JSON
envelope. claude is always faked - nothing is ever really executed."""

from __future__ import annotations

import json
import subprocess
import unittest
from unittest import mock

from friday.errors import PreconditionError, PrimitiveError, PrimitiveTimeout
from friday.l1 import dev
from tests.helpers import EnvTestCase

ENVELOPE = {"result": '{"exit_code": 0, "stdout": "hi", "stderr": ""}', "is_error": False}


class TestDevGate(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.calls = []
        fake = mock.Mock(side_effect=lambda *a, **k: self.calls.append((a, k)) or ENVELOPE)
        self.p = mock.patch.object(dev, "_run_claude", fake)
        self.p.start()
        self.addCleanup(self.p.stop)

    def test_run_shell_refuses_without_flag(self):
        with self.assertRaises(PreconditionError):
            dev.run_shell(".", "echo hi")
        self.assertEqual(self.calls, [])  # claude never invoked

    def test_run_bypass_refuses_without_flag(self):
        with self.assertRaises(PreconditionError):
            dev.run("task", allow_bypass_permissions=True)
        self.assertEqual(self.calls, [])

    def test_plain_run_ungated(self):
        dev.run("task")
        self.assertEqual(len(self.calls), 1)

    def test_run_shell_allowed_with_flag(self):
        self.set_env(FRIDAY_ALLOW_DANGEROUS="1")
        out = dev.run_shell(".", "echo hi")
        self.assertEqual(out["exit_code"], 0)
        self.assertEqual(out["stdout"], "hi")

    def test_run_shell_bypass_flag_reaches_claude(self):
        self.set_env(FRIDAY_ALLOW_DANGEROUS="1")
        dev.run_shell(".", "echo hi", allow_bypass_permissions=True)
        (args, _) = self.calls[0]
        self.assertTrue(args[-1])  # bypass arg True

    def test_run_shell_rejects_empty_command(self):
        self.set_env(FRIDAY_ALLOW_DANGEROUS="1")
        with self.assertRaises(PrimitiveError):
            dev.run_shell(".", "   ")

    def test_run_shell_bad_envelope_raises(self):
        self.set_env(FRIDAY_ALLOW_DANGEROUS="1")
        with mock.patch.object(
            dev, "_run_claude", return_value={"result": "not json", "is_error": False}
        ):
            with self.assertRaises(PrimitiveError):
                dev.run_shell(".", "echo hi")


class TestClaudeTimeout(EnvTestCase):
    """Standalone (no _run_claude fake - TestDevGate's setUp patches it)."""

    def test_claude_timeout_raises_primitive_timeout_with_state(self):
        """REGRESSION (2026-08-13, found LIVE by the triage repair loop):
        when claude -p times out, _run_claude must raise PrimitiveTimeout
        (with its state), NOT crash with 'PrimitiveTimeout() takes no
        keyword arguments' - the exception class previously inherited
        FridayError's bare init while the raise sites passed state=."""
        with mock.patch(
            "friday.l1.dev.subprocess.run", side_effect=subprocess.TimeoutExpired("claude", 180)
        ):
            with self.assertRaises(PrimitiveTimeout) as ctx:
                dev._run_claude("task", None, 180, "opus", False)
        self.assertIsNotNone(ctx.exception.state)
        self.assertIn("did not finish within", str(ctx.exception))


class TestDigest(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.calls = []
        fake = mock.Mock(
            side_effect=lambda *a, **k: self.calls.append((a, k)) or {"result": "digest text"}
        )
        self.p = mock.patch.object(dev, "_run_claude", fake)
        self.p.start()
        self.addCleanup(self.p.stop)

    def test_digest_returns_llm_text(self):
        out = dev.digest({"friday": "commit one", "agent-reach": ["a", "b"]})
        self.assertEqual(out, "digest text")

    def test_digest_builds_labeled_context_prompt(self):
        dev.digest({"friday git log": ["2026-08-01 feat: x"], "changelog": "notes"})
        (args, _) = self.calls[0]
        task = args[0]
        self.assertIn("[friday git log]", task)
        self.assertIn("2026-08-01 feat: x", task)
        self.assertIn("[changelog]", task)
        self.assertIn("notes", task)
        self.assertIn("CONCRETE", task)  # default instruction asks for specifics
        # bypass always False: digest never runs with permission bypass
        self.assertFalse(args[-1])

    def test_digest_empty_context_raises(self):
        with self.assertRaises(PreconditionError):
            dev.digest({})
        with self.assertRaises(PreconditionError):
            dev.digest(None)

    def test_digest_empty_instruction_raises(self):
        with self.assertRaises(PreconditionError):
            dev.digest({"a": "b"}, instruction="   ")

    def test_digest_llm_empty_result_raises(self):
        with mock.patch.object(dev, "_run_claude", return_value={"result": "   "}):
            with self.assertRaises(PrimitiveError):
                dev.digest({"a": "b"})

    def test_digest_accepts_custom_instruction(self):
        dev.digest({"a": "b"}, instruction="custom prompt")
        (args, _) = self.calls[0]
        self.assertIn("custom prompt", args[0])


class TestFridayModelOverride(EnvTestCase):
    """FRIDAY_MODEL: the whole-agent emergency escape hatch at the
    _run_claude choke point (2026-08-13). When the default alias' provider
    is DEGRADED, one env var repoints EVERY LLM consumer (planner,
    triage, digest, summarize) at a working model. The override wins over
    the passed model arg; absent, the passed model (MODEL_ALIAS default)
    is used."""

    def _capture_cmd(self, **env) -> list[str]:
        self.set_env(**env)
        captured: dict = {}

        def fake_run(cmd, **kwargs):
            captured["cmd"] = list(cmd)
            return mock.Mock(
                returncode=0,
                stdout=json.dumps({"result": "ok", "is_error": False}),
                stderr="",
            )

        with mock.patch("subprocess.run", side_effect=fake_run):
            dev._run_claude("task", None, 30, "opus", False)
        return captured["cmd"]

    def test_override_replaces_the_model_flag(self):
        cmd = self._capture_cmd(FRIDAY_MODEL="oc/laguna-s-2.1-free")
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "oc/laguna-s-2.1-free")

    def test_default_model_used_without_override(self):
        cmd = self._capture_cmd()
        self.assertIn("--model", cmd)
        self.assertEqual(cmd[cmd.index("--model") + 1], "opus")


if __name__ == "__main__":
    unittest.main()
