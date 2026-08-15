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
# FRIDAY_GAPS_FILE / FRIDAY_PROPOSALS_DIR / FRIDAY_L1_DIR were added after
# a real leak: a watcher allowlist-refusal test (TestAllowList) recorded
# allow-x gaps into the REAL var/logs/capability_gaps.jsonl because the
# gap file was not isolated by default - 5 leaked records with timestamps
# matching that test's runs (WATCHER_DEPLOY_PROOF.md documents the
# incident). Default isolation below makes that class of leak impossible.
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
    "FRIDAY_GAPS_FILE",
    "FRIDAY_PROPOSALS_DIR",
    "FRIDAY_L1_DIR",
    "FRIDAY_FIRED_FILE",
    "FRIDAY_LESSONS_FILE",
    "FRIDAY_APPROVED_LESSONS",
    "FRIDAY_PROPOSED_LESSONS_DIR",
    "FRIDAY_WATCHER_CONFIG",
    "FRIDAY_PROPOSED_TRIGGERS_DIR",
    "FRIDAY_TRIAGE_MODEL",
    "FRIDAY_TRIAGE_FALLBACK_MODELS",
    "FRIDAY_MODEL",
    # Calendar API credential overrides - a test that set_env's them must
    # not leak into the next (the gmail test suite has the same discipline
    # via GMAIL_* below; found live when calendar's token-cache test
    # leaked CALENDAR_CLIENT_ID into the missing-creds test, 2026-08-14)
    "CALENDAR_CLIENT_ID",
    "CALENDAR_CLIENT_SECRET",
    "CALENDAR_REFRESH_TOKEN",
    "GMAIL_CLIENT_ID",
    "GMAIL_CLIENT_SECRET",
    "GMAIL_REFRESH_TOKEN",
    "GMAIL_DEFAULT_TO",
    "GOOGLE_CALENDAR_TOKEN",
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
        # Same hermetic-by-default rule for the capability-gap file: a test
        # that exercises an allowlist/unknown-primitive refusal without
        # explicitly pointing FRIDAY_GAPS_FILE at a temp file must NOT write
        # into the real var/logs/capability_gaps.jsonl.
        if "FRIDAY_GAPS_FILE" not in os.environ:
            os.environ["FRIDAY_GAPS_FILE"] = str(self.mktmp() / "gaps_test.jsonl")
        # And for the watcher's persisted fired-state: a run_watcher test
        # that fires a time trigger must never touch the real
        # var/state/watcher_fired.json.
        if "FRIDAY_FIRED_FILE" not in os.environ:
            os.environ["FRIDAY_FIRED_FILE"] = str(self.mktmp() / "fired_test.json")
        # Same hermetic-by-default rule for the lessons loop: a test that
        # records a lesson event (the gate, the planner, the digest
        # attribution check all record) must not write into the real
        # var/logs/lessons.jsonl, and a test that renders/injects must not
        # pick up the real approved store (config/lessons.json) - both are
        # pointed at temp files unless a test sets them explicitly.
        if "FRIDAY_LESSONS_FILE" not in os.environ:
            os.environ["FRIDAY_LESSONS_FILE"] = str(self.mktmp() / "lessons_test.jsonl")
        if "FRIDAY_APPROVED_LESSONS" not in os.environ:
            os.environ["FRIDAY_APPROVED_LESSONS"] = str(self.mktmp() / "lessons_approved_test.json")

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
