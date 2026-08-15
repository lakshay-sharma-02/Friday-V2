import unittest
import tempfile
import os
from pathlib import Path

from friday.l1.files import find_newest
from friday.errors import PreconditionError


class TestFindNewest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        # create two pdfs with DIFFERENT mtimes: report.pdf is newer
        old = self.dir / "alpha.pdf"
        new = self.dir / "report.pdf"
        old.write_bytes(b"old")
        new.write_bytes(b"new")
        os.utime(old, (1000000000, 1000000000))          # 2001
        os.utime(new, (1700000000, 1700000000))          # 2023
        (self.dir / "notes.txt").write_text("not a pdf")

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_returns_newest_match_by_mtime(self):
        # report.pdf (2023) is newer than alpha.pdf (2001) - mtime wins,
        # not lexicographic order (alpha would win find_file's sort)
        self.assertEqual(find_newest("pdf", str(self.dir)), str(self.dir / "report.pdf"))

    def test_case_insensitive_pattern(self):
        self.assertEqual(find_newest("PDF", str(self.dir)), str(self.dir / "report.pdf"))

    def test_absent_match_returns_empty_str(self):
        self.assertEqual(find_newest("no-such-file", str(self.dir)), "")

    def test_directories_never_matched(self):
        (self.dir / "pdf").mkdir()  # a DIRECTORY named 'pdf' must not win
        self.assertEqual(find_newest("pdf", str(self.dir)), str(self.dir / "report.pdf"))

    def test_empty_name_raises(self):
        with self.assertRaises(PreconditionError):
            find_newest("", str(self.dir))

    def test_empty_directory_raises(self):
        with self.assertRaises(PreconditionError):
            find_newest("pdf", "")

    def test_missing_directory_raises(self):
        with self.assertRaises(PreconditionError):
            find_newest("pdf", str(self.dir / "no-such-dir"))


if __name__ == "__main__":
    unittest.main()
