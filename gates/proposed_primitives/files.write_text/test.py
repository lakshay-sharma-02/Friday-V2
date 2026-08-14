import os
import tempfile
import unittest
from pathlib import Path

from friday.contracts import REGISTRY, Idempotency
from friday.errors import PreconditionError
from friday.l1 import files


class WriteTextSelfCheck(unittest.TestCase):
    def test_registered_in_registry(self):
        self.assertIn("files.write_text", REGISTRY)

    def test_contract_idempotency_is_commutative_safe(self):
        c = REGISTRY["files.write_text"]
        self.assertEqual(c.idempotency, Idempotency.COMMUTATIVE_SAFE)

    def test_contract_name_has_exactly_one_dot(self):
        c = REGISTRY["files.write_text"]
        parts = c.name.split(".")
        self.assertEqual(len(parts), 2)


class WriteTextBehavior(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        for root, _dirs, fnames in os.walk(self.tmp, topdown=False):
            for fn in fnames:
                (Path(root) / fn).unlink()
        Path(self.tmp).rmdir()

    def test_writes_new_file(self):
        target = Path(self.tmp) / "notes.md"
        result = files.write_text(str(target), "hello world")
        self.assertEqual(result, str(target.resolve()))
        self.assertTrue(target.exists())
        self.assertEqual(target.read_text(), "hello world")

    def test_overwrites_existing_file(self):
        target = Path(self.tmp) / "notes.md"
        target.write_text("old content")
        files.write_text(str(target), "new content")
        self.assertEqual(target.read_text(), "new content")

    def test_append_mode(self):
        target = Path(self.tmp) / "log.txt"
        files.write_text(str(target), "line1\n", append=True)
        files.write_text(str(target), "line2\n", append=True)
        self.assertEqual(target.read_text(), "line1\nline2\n")

    def test_anchor_at_project_root(self):
        rel = "test_write_text_relative.md"
        try:
            files.write_text(rel, "x")
            p = files.PROJECT_ROOT / rel
            self.assertTrue(p.exists())
            self.assertEqual(p.read_text(), "x")
        finally:
            p = files.PROJECT_ROOT / rel
            if p.exists():
                p.unlink()

    def test_empty_path_raises(self):
        with self.assertRaises(PreconditionError):
            files.write_text("", "content")

    def test_nonexistent_parent_raises(self):
        target = Path(self.tmp) / "nonexistent_dir" / "file.md"
        with self.assertRaises(PreconditionError):
            files.write_text(str(target), "content")


if __name__ == "__main__":
    unittest.main()