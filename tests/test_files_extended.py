"""Tests for extended file primitives (copy, move, delete, list_dir, file_size).

These tests verify the gate-registered file operations work correctly
and are properly registered in the contract registry.
"""

from __future__ import annotations

from friday.contracts import Idempotency, REGISTRY
from friday.errors import PreconditionError, PrimitiveError
from friday.l1.files import copy, delete, file_size, list_dir, move
from tests.helpers import EnvTestCase


class TestFileCopy(EnvTestCase):
    """Tests for files.copy - copies a file to a destination directory."""

    def setUp(self):
        super().setUp()
        self.src_dir = self.mktmp(prefix="copy_src_")
        self.dst_dir = self.mktmp(prefix="copy_dst_")
        self.src_file = self.src_dir / "document.txt"
        self.src_file.write_text("Hello, World!", encoding="utf-8")

    def test_copy_creates_file_in_dest(self):
        result = copy(str(self.src_file), str(self.dst_dir))
        self.assertEqual(result, str(self.dst_dir / "document.txt"))
        self.assertTrue((self.dst_dir / "document.txt").exists())
        self.assertEqual((self.dst_dir / "document.txt").read_text(), "Hello, World!")

    def test_copy_overwrites_existing_file(self):
        existing = self.dst_dir / "document.txt"
        existing.write_text("old content", encoding="utf-8")
        result = copy(str(self.src_file), str(self.dst_dir))
        self.assertEqual(result, str(existing))
        self.assertEqual(existing.read_text(), "Hello, World!")

    def test_copy_preserves_subdirectories(self):
        result = copy(str(self.src_file), str(self.dst_dir))
        self.assertTrue((self.dst_dir / "document.txt").exists())

    def test_missing_source_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            copy(str(self.src_dir / "missing.txt"), str(self.dst_dir))

    def test_missing_dest_dir_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            copy(str(self.src_file), str(self.dst_dir / "does_not_exist"))

    def test_empty_source_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            copy("", str(self.dst_dir))

    def test_empty_dest_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            copy(str(self.src_file), "")

    def test_contract_registered_commutative_safe(self):
        c = REGISTRY.get("files.copy")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.COMMUTATIVE_SAFE)
        self.assertTrue(hasattr(copy, "__contract__"))


class TestFileMove(EnvTestCase):
    """Tests for files.move - moves a file to a destination directory."""

    def setUp(self):
        super().setUp()
        self.src_dir = self.mktmp(prefix="move_src_")
        self.dst_dir = self.mktmp(prefix="move_dst_")
        self.src_file = self.src_dir / "document.txt"
        self.src_file.write_text("Hello, World!", encoding="utf-8")

    def test_move_creates_file_in_dest(self):
        result = move(str(self.src_file), str(self.dst_dir))
        self.assertEqual(result, str(self.dst_dir / "document.txt"))
        self.assertTrue((self.dst_dir / "document.txt").exists())
        self.assertEqual((self.dst_dir / "document.txt").read_text(), "Hello, World!")

    def test_move_removes_from_source(self):
        move(str(self.src_file), str(self.dst_dir))
        self.assertFalse(self.src_file.exists())

    def test_missing_source_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            move(str(self.src_dir / "missing.txt"), str(self.dst_dir))

    def test_missing_dest_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            move(str(self.src_file), str(self.dst_dir / "does_not_exist"))

    def test_empty_source_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            move("", str(self.dst_dir))

    def test_empty_dest_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            move(str(self.src_file), "")

    def test_contract_registered_at_most_once(self):
        c = REGISTRY.get("files.move")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.AT_MOST_ONCE)
        self.assertTrue(hasattr(move, "__contract__"))


class TestFileDelete(EnvTestCase):
    """Tests for files.delete - deletes a file."""

    def setUp(self):
        super().setUp()
        self.test_dir = self.mktmp(prefix="delete_test_")
        self.test_file = self.test_dir / "to_delete.txt"
        self.test_file.write_text("delete me", encoding="utf-8")

    def test_delete_removes_file(self):
        self.assertTrue(self.test_file.exists())
        result = delete(str(self.test_file))
        self.assertEqual(result, str(self.test_file))
        self.assertFalse(self.test_file.exists())

    def test_missing_file_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            delete(str(self.test_dir / "missing.txt"))

    def test_empty_path_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            delete("")

    def test_whitespace_path_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            delete("   ")

    def test_contract_registered_at_most_once(self):
        c = REGISTRY.get("files.delete")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.AT_MOST_ONCE)
        self.assertTrue(hasattr(delete, "__contract__"))


class TestListDir(EnvTestCase):
    """Tests for files.list_dir - lists directory contents."""

    def setUp(self):
        super().setUp()
        self.test_dir = self.mktmp(prefix="listdir_test_")
        (self.test_dir / "file1.txt").write_text("a", encoding="utf-8")
        (self.test_dir / "file2.txt").write_text("b", encoding="utf-8")
        (self.test_dir / "subdir").mkdir()

    def test_lists_files_and_dirs(self):
        result = list_dir(str(self.test_dir))
        self.assertIn("path", result)
        self.assertEqual(sorted(result["files"]), ["file1.txt", "file2.txt"])
        self.assertEqual(result["dirs"], ["subdir"])
        self.assertEqual(result["count"], 3)

    def test_missing_directory_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            list_dir(str(self.test_dir / "does_not_exist"))

    def test_directory_only_lists_immediate_contents(self):
        nested = self.test_dir / "nested" / "deep.txt"
        nested.parent.mkdir(parents=True)
        nested.write_text("deep", encoding="utf-8")
        result = list_dir(str(self.test_dir))
        # Only immediate contents are listed - 'nested' IS a subdirectory
        self.assertIn("subdir", result["dirs"])
        self.assertIn("nested", result["dirs"])
        self.assertNotIn("deep.txt", result["files"])
        self.assertNotIn("nested", result["files"])

    def test_default_path_is_current_directory(self):
        # list_dir() with no args should work on current directory
        result = list_dir()
        self.assertIn("path", result)
        self.assertIn("files", result)
        self.assertIn("dirs", result)

    def test_contract_registered_idempotent(self):
        c = REGISTRY.get("files.list_dir")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)
        self.assertTrue(hasattr(list_dir, "__contract__"))


class TestFileSize(EnvTestCase):
    """Tests for files.file_size - gets file size."""

    def setUp(self):
        super().setUp()
        self.test_dir = self.mktmp(prefix="filesize_test_")

    def test_returns_size_in_bytes_and_human(self):
        test_file = self.test_dir / "test.txt"
        content = "Hello, World!"
        test_file.write_text(content, encoding="utf-8")
        result = file_size(str(test_file))
        self.assertEqual(result["path"], str(test_file))
        self.assertEqual(result["size_bytes"], len(content))
        self.assertEqual(result["size_human"], f"{len(content)} B")

    def test_bytes_to_kb(self):
        test_file = self.test_dir / "test.txt"
        content = "x" * 1500
        test_file.write_text(content, encoding="utf-8")
        result = file_size(str(test_file))
        self.assertEqual(result["size_bytes"], 1500)
        self.assertIn("KB", result["size_human"])

    def test_bytes_to_mb(self):
        test_file = self.test_dir / "test.txt"
        content = "x" * 2_000_000
        test_file.write_text(content, encoding="utf-8")
        result = file_size(str(test_file))
        self.assertEqual(result["size_bytes"], 2_000_000)
        self.assertIn("MB", result["size_human"])

    def test_missing_file_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            file_size(str(self.test_dir / "missing.txt"))

    def test_empty_path_raises_precondition(self):
        with self.assertRaises(PreconditionError):
            file_size("")

    def test_contract_registered_idempotent(self):
        c = REGISTRY.get("files.file_size")
        self.assertIsNotNone(c)
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)
        self.assertTrue(hasattr(file_size, "__contract__"))