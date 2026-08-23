"""Unit tests for git.status primitive.

Tests run in isolation with real git operations on temp repos - no mocking.
"""

import subprocess
import tempfile
import unittest
from pathlib import Path


class TestGitStatus(unittest.TestCase):
    """Tests for the git.status primitive."""

    def setUp(self):
        """Create a temp git repo for testing."""
        self.temp_dir = tempfile.mkdtemp()
        subprocess.run(
            ["git", "init", "-q", self.temp_dir],
            cwd=self.temp_dir,
            capture_output=True,
            timeout=10,
            text=True,
        )
        subprocess.run(
            ["git", "-C", self.temp_dir, "config", "user.name", "Tester"],
            capture_output=True,
            timeout=10,
            text=True,
        )
        subprocess.run(
            ["git", "-C", self.temp_dir, "config", "user.email", "t@t"],
            capture_output=True,
            timeout=10,
            text=True,
        )

    def tearDown(self):
        """Clean up temp repo."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_returns_dict_with_expected_keys(self):
        """git.status should return a dict with expected keys."""
        from friday.l1.git import status

        result = status(self.temp_dir)

        self.assertIn("branch", result)
        self.assertIn("staged", result)
        self.assertIn("conflicts", result)
        self.assertIn("uncommitted", result)
        self.assertIn("is_clean", result)

    def test_clean_repo_is_clean(self):
        """A fresh repo should be clean after initial commit."""
        from friday.l1.git import status

        # Add and commit a file to make it clean
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("hello")
        subprocess.run(
            ["git", "-C", self.temp_dir, "add", "test.txt"],
            capture_output=True,
            timeout=10,
            text=True,
        )
        subprocess.run(
            ["git", "-C", self.temp_dir, "commit", "-q", "-m", "initial"],
            capture_output=True,
            timeout=10,
            text=True,
        )

        result = status(self.temp_dir)
        self.assertTrue(result["is_clean"])
        self.assertEqual(result["staged"], [])
        self.assertEqual(result["uncommitted"], [])

    def test_detects_staged_changes(self):
        """Should detect staged files."""
        from friday.l1.git import status

        test_file = Path(self.temp_dir) / "staged.txt"
        test_file.write_text("staged content")
        subprocess.run(
            ["git", "-C", self.temp_dir, "add", "staged.txt"],
            capture_output=True,
            timeout=10,
            text=True,
        )

        result = status(self.temp_dir)
        self.assertFalse(result["is_clean"])
        self.assertIn("staged.txt", result["staged"])

    def test_detects_untracked_files(self):
        """Should detect untracked files."""
        from friday.l1.git import status

        test_file = Path(self.temp_dir) / "untracked.txt"
        test_file.write_text("untracked content")

        result = status(self.temp_dir)
        self.assertFalse(result["is_clean"])
        self.assertIn("untracked.txt", result["uncommitted"])

    def test_raises_for_non_git_directory(self):
        """Should raise PreconditionError for non-git directory."""
        import shutil
        from friday.errors import PreconditionError

        non_git_dir = tempfile.mkdtemp()
        try:
            from friday.l1.git import status

            with self.assertRaises(PreconditionError):
                status(non_git_dir)
        finally:
            shutil.rmtree(non_git_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()