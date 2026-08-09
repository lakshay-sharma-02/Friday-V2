"""Shared helpers for the Friday test suite: env isolation and temp dirs.

Every test that touches the L0 log or an env-gated behaviour must isolate
the relevant env vars so the suite never writes into the real
var/logs/friday.jsonl or trips a global switch.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Every env var the suite cares about, so a test can restore the world.
ENV_KEYS = (
    "FRIDAY_LOG_FILE",
    "FRIDAY_LOG_MAX_BYTES",
    "FRIDAY_LOG_BACKUPS",
    "FRIDAY_OBSERVABILITY",
    "FRIDAY_RUN_ID",
    "FRIDAY_TASKS_FILE",
    "FRIDAY_FACTS_FILE",
    "FRIDAY_ALLOW_DANGEROUS",
    "FRIDAY_PROTECTED_CLASSES",
)


class EnvTestCase(unittest.TestCase):
    """Snapshot + restore the Friday env vars around each test."""

    def setUp(self) -> None:
        self._env_saved = {k: os.environ.get(k) for k in ENV_KEYS}
        self._tmpdirs: list[Path] = []
        # Hermetic by default: any primitive/check call a test makes - even
        # a PreconditionError path, which @observe still writes an exception
        # line for - must land in a temp file, never the real
        # var/logs/friday.jsonl. Tests that care set their own
        # FRIDAY_LOG_FILE explicitly, which overrides this.
        if "FRIDAY_LOG_FILE" not in os.environ:
            os.environ["FRIDAY_LOG_FILE"] = str(self.mktmp() / "friday_test.jsonl")

    def tearDown(self) -> None:
        for k, v in self._env_saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        for d in self._tmpdirs:
            shutil.rmtree(d, ignore_errors=True)

    def mktmp(self, prefix: str = "friday_test_") -> Path:
        d = Path(tempfile.mkdtemp(prefix=prefix))
        self._tmpdirs.append(d)
        return d

    def set_env(self, **kw: str) -> None:
        for k, v in kw.items():
            os.environ[k] = v
