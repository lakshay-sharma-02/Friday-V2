"""secrets: credential retrieval - the pass backend exercised with a
mocked subprocess (no real pass/GPG interaction), and the portable
env-var override that the Windows port runs on."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from friday.errors import PrimitiveError
from friday.secrets import get_credentials
from tests.helpers import EnvTestCase


class _Proc:
    def __init__(self, returncode=0, stdout="", stderr=""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class TestSecrets(EnvTestCase):
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

    # --- portable env-var override (the Windows-port path; pass is
    # POSIX-only, so on Windows services configure via env instead) ---

    def test_env_json_override_wins_over_pass(self):
        self.set_env(GITHUB_CREDENTIALS='{"username": "env-u", "password": "env-p"}')
        with mock.patch.object(
            subprocess,
            "run",
            return_value=_Proc(stdout='{"username": "pass-u", "password": "pass-p"}'),
        ) as run:
            self.assertEqual(get_credentials("github"), {"username": "env-u", "password": "env-p"})
        run.assert_not_called()  # pass never consulted when env is set

    def test_env_username_password_pair(self):
        self.set_env(GITHUB_USERNAME="env-u", GITHUB_PASSWORD="env-p")
        self.assertEqual(get_credentials("github"), {"username": "env-u", "password": "env-p"})

    def test_env_partial_pair_falls_back_to_pass(self):
        """Only one of USERNAME/PASSWORD set is a misconfiguration - must
        NOT silently return an empty password; the pass path stays."""
        self.set_env(GITHUB_USERNAME="env-u")
        with mock.patch.object(subprocess, "run", return_value=_Proc(stdout="myuser\nmypass\n")):
            self.assertEqual(
                get_credentials("github"), {"username": "myuser", "password": "mypass"}
            )

    def test_env_malformed_json_falls_back_to_pass(self):
        self.set_env(GITHUB_CREDENTIALS="{not json")
        with mock.patch.object(subprocess, "run", return_value=_Proc(stdout="myuser\nmypass\n")):
            self.assertEqual(
                get_credentials("github"), {"username": "myuser", "password": "mypass"}
            )

    def test_no_env_no_pass_error_names_the_override(self):
        with mock.patch.object(subprocess, "run", side_effect=FileNotFoundError):
            with self.assertRaises(PrimitiveError) as ctx:
                get_credentials("github")
        self.assertIn("GITHUB_CREDENTIALS", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
