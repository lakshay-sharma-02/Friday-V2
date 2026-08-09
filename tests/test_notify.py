"""notify_send: exercised through a mocked subprocess - no real desktop
notification is fired during tests."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from friday.errors import PreconditionError, PrimitiveError
from friday.l1 import notify
from tests.helpers import EnvTestCase


class TestNotifySend(EnvTestCase):
    def test_success(self):
        proc = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(notify.subprocess, "run", return_value=proc) as run:
            out = notify.notify_send("Friday test", "body")
        self.assertEqual(out, {"title": "Friday test", "body": "body", "sent": True})
        cmd = run.call_args.args[0]
        # exact command shape: notify-send -t <ms> <title> [body]
        self.assertEqual(cmd[0], "notify-send")
        self.assertEqual(cmd[1], "-t")
        self.assertEqual(cmd[2], str(notify.DEFAULT_TIMEOUT_MS))
        self.assertEqual(cmd[3], "Friday test")
        self.assertEqual(cmd[4], "body")

    def test_timeout_flag_respects_custom_value(self):
        proc = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(notify.subprocess, "run", return_value=proc) as run:
            notify.notify_send("t", timeout_ms=2500)
        cmd = run.call_args.args[0]
        self.assertEqual(cmd[2], "2500")

    def test_no_body_omits_body_arg(self):
        proc = mock.Mock(returncode=0, stdout="", stderr="")
        with mock.patch.object(notify.subprocess, "run", return_value=proc) as run:
            notify.notify_send("t")
        cmd = run.call_args.args[0]
        self.assertEqual(len(cmd), 4)  # no body appended

    def test_empty_title_precondition(self):
        with self.assertRaises(PreconditionError):
            notify.notify_send("   ")

    def test_missing_binary(self):
        with mock.patch.object(notify.subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(PrimitiveError):
                notify.notify_send("t")

    def test_nonzero_exit(self):
        proc = mock.Mock(returncode=1, stdout="", stderr="no notification daemon")
        with mock.patch.object(notify.subprocess, "run", return_value=proc):
            with self.assertRaises(PrimitiveError):
                notify.notify_send("t")

    def test_timeout(self):
        with mock.patch.object(notify.subprocess, "run", side_effect=subprocess.TimeoutExpired("notify-send", 15)):
            with self.assertRaises(PrimitiveError):
                notify.notify_send("t")


if __name__ == "__main__":
    unittest.main()
