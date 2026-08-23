"""git.log - the read-only repo-history primitive, exercised against a
hermetic temp git repository (real `git` CLI, temp dir, no network).
Requires the `git` binary on the machine (Friday itself depends on it -
the suite's 'zero external dependencies' claim excludes the machine's
own git)."""

from __future__ import annotations

import os
import subprocess
from unittest import mock
import unittest
from datetime import UTC, datetime, timedelta
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
            check=True,
            env=env,
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
        now = datetime.now(UTC)
        self.repo = _make_repo(
            self.mktmp(),
            [
                ("oldest work", (now - timedelta(days=40)).isoformat()),
                ("middle fix", (now - timedelta(days=20)).isoformat()),
                ("newest feature", (now - timedelta(days=5)).isoformat()),
            ],
        )

    def test_log_returns_entries_newest_first(self):
        rows = git_log(str(self.repo), count=10)
        self.assertEqual(
            [r["subject"] for r in rows], ["newest feature", "middle fix", "oldest work"]
        )
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


class TestGitStatus(EnvTestCase):
    """Tests for the git.status primitive."""

    def setUp(self):
        """Create a temp git repo for testing."""
        super().setUp()
        self.temp_dir = self.mktmp()
        subprocess.run(
            ["git", "init", "-q", str(self.temp_dir)],
            shell=False,
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "config", "user.name", "Tester"],
            shell=False,
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "config", "user.email", "t@t"],
            shell=False,
            capture_output=True,
            timeout=10,
        )

    def test_returns_dict_with_expected_keys(self):
        """git.status should return a dict with expected keys."""
        from friday.l1.git import status

        result = status(str(self.temp_dir))

        self.assertIn("branch", result)
        self.assertIn("staged", result)
        self.assertIn("conflicts", result)
        self.assertIn("uncommitted", result)
        self.assertIn("is_clean", result)

    def test_clean_repo_is_clean(self):
        """A fresh repo should be clean after initial commit."""
        from friday.l1.git import status

        # Add and commit a file to make it clean
        test_file = self.temp_dir / "test.txt"
        test_file.write_text("hello")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "test.txt"],
            shell=False,
            capture_output=True,
            timeout=10,
        )
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "commit", "-q", "-m", "initial"],
            shell=False,
            capture_output=True,
            timeout=10,
        )

        result = status(str(self.temp_dir))
        self.assertTrue(result["is_clean"])
        self.assertEqual(result["staged"], [])
        self.assertEqual(result["uncommitted"], [])

    def test_detects_staged_changes(self):
        """Should detect staged files."""
        from friday.l1.git import status

        test_file = self.temp_dir / "staged.txt"
        test_file.write_text("staged content")
        subprocess.run(
            ["git", "-C", str(self.temp_dir), "add", "staged.txt"],
            shell=False,
            capture_output=True,
            timeout=10,
        )

        result = status(str(self.temp_dir))
        self.assertFalse(result["is_clean"])
        self.assertIn("staged.txt", result["staged"])

    def test_detects_untracked_files(self):
        """Should detect untracked files."""
        from friday.l1.git import status

        test_file = self.temp_dir / "untracked.txt"
        test_file.write_text("untracked content")

        result = status(str(self.temp_dir))
        self.assertFalse(result["is_clean"])
        self.assertIn("untracked.txt", result["uncommitted"])

    def test_raises_for_non_git_directory(self):
        """Should raise PreconditionError for non-git directory."""
        from friday.errors import PreconditionError
        from friday.l1.git import status

        non_git_dir = self.mktmp() / "plain"
        non_git_dir.mkdir()
        with self.assertRaises(PreconditionError):
            status(str(non_git_dir))

    def test_contract_registered_idempotent(self):
        """git.status should be in REGISTRY with correct contract."""
        from friday.l1.git import status as git_status

        c = REGISTRY.get("git.status")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)
        self.assertTrue(hasattr(git_status, "__contract__"))


if __name__ == "__main__":
    unittest.main()


class TestGitDiff(EnvTestCase):
    """Tests for git.diff primitive."""

    def test_diff_empty_repo(self):
        from friday.l1.git import diff
        with mock.patch("friday.l1.git._run_git", return_value=""):
            result = diff(".")
            self.assertTrue(result["is_clean"])

    def test_diff_with_staged_changes(self):
        from friday.l1.git import diff
        with mock.patch("friday.l1.git._run_git") as m:
            m.side_effect = ["diff --cached\n+new line\n", "diff\n"]
            result = diff(".")
            self.assertFalse(result["is_clean"])
            self.assertIn("new line", result["staged"])

    def test_diff_with_unstaged_changes(self):
        from friday.l1.git import diff
        with mock.patch("friday.l1.git._run_git") as m:
            m.side_effect = ["diff --cached\n", "diff\n-old line\n+new line\n"]
            result = diff(".")
            self.assertFalse(result["is_clean"])
            self.assertIn("new line", result["unstaged"])

    def test_diff_empty_path(self):
        from friday.l1.git import diff
        with self.assertRaises(PreconditionError):
            diff("")

    def test_diff_missing_repo(self):
        from friday.l1.git import diff
        with self.assertRaises(PreconditionError):
            diff("/no/such/dir")

    def test_diff_contract_registered(self):
        from friday.contracts import REGISTRY, Idempotency
        c = REGISTRY.get("git.diff")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)


class TestGitBranch(EnvTestCase):
    """Tests for git.branch primitive."""

    def test_branch_returns_current(self):
        from friday.l1.git import branch
        with mock.patch("friday.l1.git._run_git") as m:
            m.side_effect = ["main\n", "* main\n  dev\n  feature\n"]
            result = branch(".")
            self.assertEqual(result["current"], "main")
            self.assertIn("main", result["branches"])

    def test_branch_detached_head(self):
        from friday.l1.git import branch
        with mock.patch("friday.l1.git._run_git") as m:
            m.side_effect = ["\n", "* (HEAD detached at abc123)\n  main\n"]
            result = branch(".")
            self.assertEqual(result["current"], "HEAD")

    def test_branch_empty_path(self):
        from friday.l1.git import branch
        with self.assertRaises(PreconditionError):
            branch("")

    def test_branch_contract_registered(self):
        from friday.contracts import REGISTRY, Idempotency
        c = REGISTRY.get("git.branch")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)


class TestGitCommit(EnvTestCase):
    """Tests for git.commit primitive."""

    def test_commit_with_files(self):
        from friday.l1.git import commit
        with mock.patch("friday.l1.git._run_git") as m:
            m.side_effect = [None, None, "abc123def\n"]
            result = commit(".", "test commit", files=["file.txt"])
            self.assertEqual(result["commit_hash"], "abc123def")
            self.assertEqual(result["message"], "test commit")

    def test_commit_all_staged(self):
        from friday.l1.git import commit
        with mock.patch("friday.l1.git._run_git") as m:
            m.side_effect = [None, None, "abc123def\n"]
            result = commit(".", "test commit")
            self.assertEqual(result["commit_hash"], "abc123def")

    def test_commit_empty_message(self):
        from friday.l1.git import commit
        with self.assertRaises(PreconditionError):
            commit(".", "")

    def test_commit_empty_path(self):
        from friday.l1.git import commit
        with self.assertRaises(PreconditionError):
            commit("", "message")

    def test_commit_contract_registered(self):
        from friday.contracts import REGISTRY, Idempotency
        c = REGISTRY.get("git.commit")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.AT_MOST_ONCE)
