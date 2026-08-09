"""Test suite runner - the gate-proof for the automated tests.

Runs every test in tests/ (stdlib unittest, zero extra dependencies),
captures the raw output, and writes gates/TESTS_PROOF.md in the
gate-proof tradition: raw evidence + honest verdict.

Run:  ./.venv/bin/python gates/test_suite.py
"""

from __future__ import annotations

import io
import sys
import unittest
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import friday  # noqa: F401  (ensure the package is importable)

PROOF = ROOT / "gates" / "TESTS_PROOF.md"


def main() -> int:
    stream = io.StringIO()
    runner = unittest.TextTestRunner(stream=stream, verbosity=2)
    suite = unittest.defaultTestLoader.discover(str(ROOT / "tests"), pattern="test_*.py")
    result = runner.run(suite)
    output = stream.getvalue()

    summary = (
        f"Ran {result.testsRun} tests: "
        f"{result.testsRun - len(result.failures) - len(result.errors)} passed, "
        f"{len(result.failures)} failed, {len(result.errors)} errors."
    )
    md = "\n".join(
        [
            "# TESTS_PROOF — automated test suite for Friday",
            "",
            f"Status date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
            "",
            "The full unittest suite over every layer and feature: registry,",
            "observability (redaction / rotation / log_transform), the executor",
            "(ref resolver, retry policy, blocked primitives), the planner",
            "(validate_plan / catalog / facts), L2 checks, window protected-",
            "classes, the dev dangerous-gate, gmail/notify/secrets, and the",
            "watch loop. All side-effect boundaries are mocked - the suite",
            "never sends, launches, clicks or touches the compositor.",
            "",
            f"## Verdict: {'PASS' if result.wasSuccessful() else 'FAIL'}",
            "",
            f"{summary}",
            "",
            "## Raw output",
            "",
            "```",
            output.rstrip(),
            "```",
            "",
        ]
    )
    PROOF.write_text(md + "\n", encoding="utf-8")
    print(output)
    print("=" * 72)
    print(summary)
    print(f"proof written to {PROOF.relative_to(ROOT)}")
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    sys.exit(main())
