"""secrets: pass-backed credential retrieval, exercised with a mocked
subprocess - no real pass/GPG interaction during tests."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from friday.errors import PrimitiveError
from friday.secrets import get_credentials


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestSecrets(unittest.TestCase):
    def test_json_entry(self):
        with mock.patch.object(
            subprocess, "run", return_value=_Proc(stdout='{"username": "u", "password": "p"}')
        ):
            self.assertEqual(get_credentials("github"), {"username": "u", "password": "p"})

    def test_two_line_entry(self):
        with mock.patch.object(subprocess, "run", return_value=_Proc(stdout="myuser\nmypass\n")):
            self.assertEqual(
                get_credentials("github"), {"username": "myuser", "password": "mypass"}
            )

    def test_missing_binary(self):
        with mock.patch.object(subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(PrimitiveError):
                get_credentials("github")

    def test_nonzero_exit(self):
        with mock.patch.object(
            subprocess,
            "run",
            return_value=_Proc(returncode=1, stderr="entry not in password store"),
        ):
            with self.assertRaises(PrimitiveError):
                get_credentials("github")

    def test_unsupported_entry_shape(self):
        with mock.patch.object(subprocess, "run", return_value=_Proc(stdout="only-one-line")):
            with self.assertRaises(PrimitiveError):
                get_credentials("github")


if __name__ == "__main__":
    unittest.main()
