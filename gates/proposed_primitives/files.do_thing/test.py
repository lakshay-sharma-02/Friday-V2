"""Unit tests for the gate-registered files.find_file_exact primitive.
Hermetic: pure filesystem operations on temp dirs, no network/compositor."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from friday.errors import PreconditionError
from friday.l1.files import find_file_exact


class TestFindFileExact(unittest.TestCase):
    def _dir(self) -> Path:
        d = Path(tempfile.mkdtemp(prefix="friday_ffe_"))
        (d / "report.pdf").write_text("x", encoding="utf-8")
        (d / "report2.pdf").write_text("x", encoding="utf-8")
        return d

    def test_exact_name_match_case_insensitive(self):
        d = self._dir()
        self.assertEqual(find_file_exact("REPORT.PDF", str(d)), str(d / "report.pdf"))

    def test_substring_is_not_a_match(self):
        d = self._dir()
        # find_file would match this; find_file_exact must NOT
        self.assertEqual(find_file_exact("report", str(d)), "")

    def test_no_exact_match_returns_empty(self):
        d = self._dir()
        self.assertEqual(find_file_exact("missing.pdf", str(d)), "")

    def test_empty_name_raises(self):
        with self.assertRaises(PreconditionError):
            find_file_exact("", str(self._dir()))


if __name__ == "__main__":
    unittest.main()
