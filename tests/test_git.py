"""git.log - the read-only repo-history primitive, exercised against a
hermetic temp git repository (real `git` CLI, temp dir, no network).
Requires the `git` binary on the machine (Friday itself depends on it -
the suite's 'zero external dependencies' claim excludes the machine's
own git)."""

from __future__ import annotations

import os
import subprocess
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from friday.contracts import REGISTRY, Idempotency
from friday.errors import PreconditionError, PrimitiveError
from friday.l1.git import log as git_log
from tests.helpers import EnvTestCase


def _make_repo(base: Path, commits: list[tuple[str, str]]) -> Path:
    """Create a git repo in `base/repo` with the given (subject, iso-date)
    commits, oldest first."""
    repo = base / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.name", "Tester"], check=True)
    subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
    for i, (subject, iso_date) in enumerate(commits):
        (repo / f"f{i}.txt").write_text(subject, encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "."], check=True)
        env = dict(os.environ)
        env["GIT_AUTHOR_DATE"] = iso_date
        env["GIT_COMMITTER_DATE"] = iso_date
        subprocess.run(
            ["git", "-C", str(repo), "commit", "-q", "-m", subject],
            check=True, env=env,
        )
    return repo


class TestGitLog(EnvTestCase):
    def setUp(self):
        super().setUp()
        # Commit dates are RELATIVE to now so `days=` filtering is
        # deterministic on any calendar day: a fixed date would straddle
        # the `--since N days ago` boundary as real time moves past it
        # (observed flake: 'middle fix' at 2026-07-20 flips in/out of a
        # 25-day window on 2026-08-14, the exact 25-day anniversary).
        now = datetime.now(timezone.utc)
        self.repo = _make_repo(self.mktmp(), [
            ("oldest work", (now - timedelta(days=40)).isoformat()),
            ("middle fix", (now - timedelta(days=20)).isoformat()),
            ("newest feature", (now - timedelta(days=5)).isoformat()),
        ])

    def test_log_returns_entries_newest_first(self):
        rows = git_log(str(self.repo), count=10)
        self.assertEqual([r["subject"] for r in rows],
                         ["newest feature", "middle fix", "oldest work"])
        first = rows[0]
        self.assertEqual(first["author"], "Tester")
        self.assertTrue(len(first["commit"]) >= 7)  # short hash

    def test_log_count_limits_entries(self):
        rows = git_log(str(self.repo), count=2)
        self.assertEqual([r["subject"] for r in rows], ["newest feature", "middle fix"])

    def test_log_days_filters(self):
        rows = git_log(str(self.repo), count=10, days=25)  # 25d window: newest + middle
        self.assertEqual([r["subject"] for r in rows], ["newest feature", "middle fix"])
        all_rows = git_log(str(self.repo), count=10, days=100)  # 100d: all three
        self.assertEqual(len(all_rows), 3)
        old_rows = git_log(str(self.repo), count=10, days=7)  # 7d: only newest
        self.assertEqual([r["subject"] for r in old_rows], ["newest feature"])

    def test_log_empty_repo_returns_empty_list(self):
        empty = self.mktmp() / "empty"
        empty.mkdir()
        subprocess.run(["git", "init", "-q", str(empty)], check=True)
        self.assertEqual(git_log(str(empty), count=10), [])

    def test_log_missing_dir_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            git_log(str(self.mktmp() / "nope"), count=10)

    def test_log_not_a_repo_raises_primitive(self):
        plain = self.mktmp() / "plain"
        plain.mkdir()
        (plain / "x.txt").write_text("x", encoding="utf-8")
        with self.assertRaises(PrimitiveError):
            git_log(str(plain), count=10)

    def test_log_bad_count_days_raise_precondition(self):
        with self.assertRaises(PreconditionError):
            git_log(str(self.repo), count=0)
        with self.assertRaises(PreconditionError):
            git_log(str(self.repo), count=10, days=0)
        with self.assertRaises(PreconditionError):
            git_log("", count=10)

    def test_contract_registered_idempotent(self):
        c = REGISTRY.get("git.log")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)
        self.assertTrue(hasattr(git_log, "__contract__"))


if __name__ == "__main__":
    unittest.main()
