"""dev primitives: the FRIDAY_ALLOW_DANGEROUS gate fires BEFORE claude is
invoked, plain run is unaffected, and run_shell parses the claude JSON
envelope. claude is always faked - nothing is ever really executed."""

from __future__ import annotations

import unittest
from unittest import mock

from friday.errors import PreconditionError, PrimitiveError
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
        (args, kwargs) = self.calls[0]
        self.assertTrue(args[-1])  # bypass arg True

    def test_run_shell_rejects_empty_command(self):
        self.set_env(FRIDAY_ALLOW_DANGEROUS="1")
        with self.assertRaises(PrimitiveError):
            dev.run_shell(".", "   ")

    def test_run_shell_bad_envelope_raises(self):
        self.set_env(FRIDAY_ALLOW_DANGEROUS="1")
        with mock.patch.object(dev, "_run_claude", return_value={"result": "not json", "is_error": False}):
            with self.assertRaises(PrimitiveError):
                dev.run_shell(".", "echo hi")


if __name__ == "__main__":
    unittest.main()
