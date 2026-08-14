"""Unit tests for files.find_file_exact - the primitive registered through
the capability-gap approval gate (2026-08-10). These are the generated
proposal tests (gates/proposed_primitives/files.do_thing/test.py) promoted
into the real suite, plus registry coverage proving the registration is
real: EXACT (case-insensitive) filename match, '' when absent (never an
exception), PreconditionError on a bad name/directory, and the contrast
with find_file's substring semantics. Plus files.read_text - the bounded
read-only text reader added for Phase C v1."""

from __future__ import annotations

from pathlib import Path

from friday.contracts import Idempotency, REGISTRY
from friday.errors import PreconditionError
from friday.l1.files import find_file_exact, find_recent_doc, read_text
from tests.helpers import EnvTestCase


class TestFindFileExact(EnvTestCase):
    def _dir(self) -> Path:
        d = self.mktmp(prefix="friday_ffe_")
        (d / "report.pdf").write_text("x", encoding="utf-8")
        (d / "report2.pdf").write_text("x", encoding="utf-8")
        return d

    def test_exact_name_match_case_insensitive(self):
        d = self._dir()
        self.assertEqual(find_file_exact("REPORT.PDF", str(d)), str(d / "report.pdf"))

    def test_substring_is_not_a_match(self):
        d = self._dir()
        # find_file would match these as substrings; find_file_exact must
        # NOT - the WHOLE filename must match exactly (case-insensitive).
        self.assertEqual(find_file_exact("report", str(d)), "")
        self.assertEqual(find_file_exact("report2", str(d)), "")
        self.assertEqual(find_file_exact("REPORT2.PDF", str(d)), str(d / "report2.pdf"))

    def test_no_exact_match_returns_empty_not_exception(self):
        d = self._dir()
        # an absent file is a RESULT ('') per contract, never an exception
        self.assertEqual(find_file_exact("missing.pdf", str(d)), "")

    def test_empty_or_blank_name_raises(self):
        with self.assertRaises(PreconditionError):
            find_file_exact("", str(self._dir()))
        with self.assertRaises(PreconditionError):
            find_file_exact("   ", str(self._dir()))

    def test_missing_directory_raises(self):
        with self.assertRaises(PreconditionError):
            find_file_exact("report.pdf", str(self._dir() / "does-not-exist"))


class TestReadText(EnvTestCase):
    def test_reads_text_and_reports_chars(self):
        d = self.mktmp()
        p = d / "notes.md"
        p.write_text("line one\nline two", encoding="utf-8")
        out = read_text(str(p))
        self.assertEqual(out["text"], "line one\nline two")
        self.assertEqual(out["chars"], 17)
        self.assertFalse(out["truncated"])
        self.assertEqual(out["path"], str(p))

    def test_truncates_at_max_chars(self):
        d = self.mktmp()
        p = d / "big.txt"
        p.write_text("a" * 1000, encoding="utf-8")
        out = read_text(str(p), max_chars=100)
        self.assertEqual(len(out["text"]), 100)
        self.assertEqual(out["chars"], 1000)
        self.assertTrue(out["truncated"])

    def test_no_truncation_when_within_limit(self):
        d = self.mktmp()
        p = d / "small.txt"
        p.write_text("hello", encoding="utf-8")
        out = read_text(str(p), max_chars=8000)
        self.assertEqual(out["text"], "hello")
        self.assertFalse(out["truncated"])

    def test_missing_file_raises(self):
        with self.assertRaises(PreconditionError):
            read_text(str(self.mktmp() / "missing.txt"))

    def test_directory_is_not_a_file_raises(self):
        d = self.mktmp()
        with self.assertRaises(PreconditionError):
            read_text(str(d))  # a directory, not a file

    def test_empty_path_or_bad_max_chars_raises(self):
        with self.assertRaises(PreconditionError):
            read_text("")
        with self.assertRaises(PreconditionError):
            read_text(str(self.mktmp() / "x"), max_chars=0)

    def test_contract_registered_idempotent(self):
        c = REGISTRY.get("files.read_text")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)
        self.assertTrue(hasattr(read_text, "__contract__"))


class TestFindRecentDoc(EnvTestCase):
    """files.find_recent_doc - Phase C v2.2's recency-based status-doc
    discovery: the most recently modified status/planning-shaped *.md
    (PLAN_STATUS/ROADMAP/DEVLOG/docs/*roadmap* ...), falling back to the
    repo-root README only when nothing status-shaped exists."""

    @staticmethod
    def _touch(p: Path, mtime: float) -> None:
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x", encoding="utf-8")
        import os

        os.utime(p, (mtime, mtime))

    def test_most_recent_status_doc_wins(self):
        d = self.mktmp(prefix="friday_frd_")
        self._touch(d / "docs" / "01-old-roadmap.md", 1000.0)
        self._touch(d / "docs" / "27-future-roadmap.md", 2000.0)
        self.assertEqual(find_recent_doc(str(d)), str(d / "docs" / "27-future-roadmap.md"))

    def test_status_doc_wins_over_newer_readme(self):
        d = self.mktmp(prefix="friday_frd_")
        self._touch(d / "README.md", 3000.0)  # newer
        self._touch(d / "PLAN_STATUS.md", 2000.0)  # older but status-shaped
        self.assertEqual(find_recent_doc(str(d)), str(d / "PLAN_STATUS.md"))

    def test_devlog_and_nested_docs_matched(self):
        d = self.mktmp(prefix="friday_frd_")
        self._touch(d / "docs" / "27-future-roadmap.md", 1000.0)
        self._touch(d / "DEVLOG.md", 2500.0)
        self.assertEqual(find_recent_doc(str(d)), str(d / "DEVLOG.md"))

    def test_falls_back_to_readme(self):
        d = self.mktmp(prefix="friday_frd_")
        self._touch(d / "README.md", 1000.0)
        self._touch(d / "src" / "notes.md", 2000.0)  # not status-shaped
        self.assertEqual(find_recent_doc(str(d)), str(d / "README.md"))

    def test_plan_word_alone_is_not_a_status_match(self):
        """Regression: '*plan*' would match TASK7_LOGIN_PLAN.md (a recipe,
        not a status doc). The default patterns must NOT pick it up."""
        d = self.mktmp(prefix="friday_frd_")
        self._touch(d / "TASK7_LOGIN_PLAN.md", 3000.0)
        self._touch(d / "README.md", 1000.0)
        self.assertEqual(find_recent_doc(str(d)), str(d / "README.md"))

    def test_no_docs_at_all_returns_empty(self):
        d = self.mktmp(prefix="friday_frd_")
        (d / "main.py").write_text("x", encoding="utf-8")
        self.assertEqual(find_recent_doc(str(d)), "")

    def test_missing_repo_raises(self):
        with self.assertRaises(PreconditionError):
            find_recent_doc(str(self.mktmp() / "no-such-repo"))

    def test_empty_repo_path_raises(self):
        with self.assertRaises(PreconditionError):
            find_recent_doc("")

    def test_custom_patterns_respected(self):
        d = self.mktmp(prefix="friday_frd_")
        self._touch(d / "PLAN_STATUS.md", 3000.0)
        self._touch(d / "WEEKLY.md", 2000.0)
        self.assertEqual(find_recent_doc(str(d), ["*WEEKLY*"]), str(d / "WEEKLY.md"))

    def test_registered_idempotent(self):
        c = REGISTRY.get("files.find_recent_doc")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)
        self.assertTrue(hasattr(find_recent_doc, "__contract__"))


class TestFindFileExactRegistration(EnvTestCase):
    def test_registered_in_contract_registry(self):
        """The approval gate's registration is real: REGISTRY holds the
        qualified name with idempotent read semantics and the callable
        carries a __contract__ (the executor's resolution requirement)."""
        c = REGISTRY.get("files.find_file_exact")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)
        self.assertTrue(hasattr(find_file_exact, "__contract__"))


if __name__ == "__main__":
    import unittest

    unittest.main()
