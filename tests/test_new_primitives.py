"""Tests for newly added primitives: git, files, gmail, calendar, system.
All tests are mocked — no real API calls, no real file modifications."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock

from friday.errors import PreconditionError, PrimitiveError
from tests.helpers import EnvTestCase


# ---- git.diff / git.branch / git.commit ----

class TestGitDiff(EnvTestCase):
    def test_diff_empty_repo(self):
        from friday.l1.git import diff
        with mock.patch("friday.l1.git._run_git", return_value=""):
            result = diff(".")
            self.assertTrue(result["is_clean"])

    def test_diff_with_changes(self):
        from friday.l1.git import diff
        with mock.patch("friday.l1.git._run_git") as m:
            m.side_effect = ["+new line\n", "-old line\n"]
            result = diff(".")
            self.assertFalse(result["is_clean"])
            self.assertIn("old line", result["unstaged"])
            self.assertIn("new line", result["staged"])

    def test_diff_missing_repo(self):
        from friday.l1.git import diff
        with self.assertRaises(PreconditionError):
            diff("/no/such/dir")

    def test_diff_empty_path(self):
        from friday.l1.git import diff
        with self.assertRaises(PreconditionError):
            diff("")


class TestGitBranch(EnvTestCase):
    def test_branch_returns_current(self):
        from friday.l1.git import branch
        with mock.patch("friday.l1.git._run_git") as m:
            m.side_effect = ["main\n", "* main\n  dev\n  feature\n"]
            result = branch(".")
            self.assertEqual(result["current"], "main")
            self.assertIn("main", result["branches"])

    def test_branch_detached(self):
        from friday.l1.git import branch
        with mock.patch("friday.l1.git._run_git") as m:
            m.side_effect = ["\n", "* (HEAD detached at abc123)\n  main\n"]
            result = branch(".")
            self.assertEqual(result["current"], "HEAD")


class TestGitCommit(EnvTestCase):
    def test_commit_with_files(self):
        from friday.l1.git import commit
        with mock.patch("friday.l1.git._run_git") as m:
            m.side_effect = [None, None, "abc123def\n"]
            result = commit(".", "test commit", files=["file.txt"])
            self.assertEqual(result["commit_hash"], "abc123def")
            self.assertEqual(result["message"], "test commit")

    def test_commit_empty_message(self):
        from friday.l1.git import commit
        with self.assertRaises(PreconditionError):
            commit(".", "")


# ---- files.copy / move / delete / list_dir / file_size ----

class TestFilesCopy(EnvTestCase):
    def test_copy_file(self):
        from friday.l1.files import copy
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir) / "test.txt"
            src.write_text("hello")
            result = copy(str(src), dst_dir)
            self.assertTrue(Path(result).exists())
            self.assertEqual(Path(result).read_text(), "hello")

    def test_copy_missing_source(self):
        from friday.l1.files import copy
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PreconditionError):
                copy("/no/such/file.txt", d)

    def test_copy_missing_dest(self):
        from friday.l1.files import copy
        with tempfile.TemporaryDirectory() as src_dir:
            src = Path(src_dir) / "test.txt"
            src.write_text("hello")
            with self.assertRaises(PreconditionError):
                copy(str(src), "/no/such/dir")


class TestFilesMove(EnvTestCase):
    def test_move_file(self):
        from friday.l1.files import move
        with tempfile.TemporaryDirectory() as src_dir, \
             tempfile.TemporaryDirectory() as dst_dir:
            src = Path(src_dir) / "test.txt"
            src.write_text("hello")
            result = move(str(src), dst_dir)
            self.assertTrue(Path(result).exists())
            self.assertFalse(src.exists())


class TestFilesDelete(EnvTestCase):
    def test_delete_file(self):
        from friday.l1.files import delete
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "test.txt"
            f.write_text("hello")
            result = delete(str(f))
            self.assertFalse(Path(result).exists())

    def test_delete_missing_file(self):
        from friday.l1.files import delete
        with self.assertRaises(PreconditionError):
            delete("/no/such/file.txt")


class TestFilesListDir(EnvTestCase):
    def test_list_dir(self):
        from friday.l1.files import list_dir
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.txt").write_text("x")
            (Path(d) / "b.txt").write_text("y")
            (Path(d) / "subdir").mkdir()
            result = list_dir(d)
            self.assertEqual(result["count"], 3)
            self.assertIn("a.txt", result["files"])
            self.assertIn("subdir", result["dirs"])

    def test_list_dir_missing(self):
        from friday.l1.files import list_dir
        with self.assertRaises(PreconditionError):
            list_dir("/no/such/dir")


class TestFilesFileSize(EnvTestCase):
    def test_file_size(self):
        from friday.l1.files import file_size
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "test.txt"
            f.write_text("hello world")
            result = file_size(str(f))
            self.assertEqual(result["size_bytes"], 11)
            self.assertIn("B", result["size_human"])

    def test_file_size_missing(self):
        from friday.l1.files import file_size
        with self.assertRaises(PreconditionError):
            file_size("/no/such/file.txt")


# ---- gmail.send_text / search / mark_read (mocked) ----

class TestGmailSendText(EnvTestCase):
    def test_send_text_empty(self):
        from friday.l1.gmail import send_text
        with self.assertRaises(PreconditionError):
            send_text("")

    def test_send_text_no_recipient(self):
        from friday.l1.gmail import send_text
        with mock.patch.dict("os.environ", {"GMAIL_DEFAULT_TO": ""}):
            with mock.patch("friday.l1.gmail._default_to", return_value=""):
                with self.assertRaises(PreconditionError):
                    send_text("hello")


class TestGmailSearch(EnvTestCase):
    def test_search_empty_query(self):
        from friday.l1.gmail import search
        with self.assertRaises(PreconditionError):
            search("")


class TestGmailMarkRead(EnvTestCase):
    def test_mark_read_empty(self):
        from friday.l1.gmail import mark_read
        with self.assertRaises(PreconditionError):
            mark_read("")


# ---- calendar.delete_event / update_event (mocked) ----

class TestCalendarDeleteEvent(EnvTestCase):
    def test_delete_event_empty(self):
        from friday.l1.calendar import delete_event
        with self.assertRaises(PreconditionError):
            delete_event("")


class TestCalendarUpdateEvent(EnvTestCase):
    def test_update_event_empty(self):
        from friday.l1.calendar import update_event
        with self.assertRaises(PreconditionError):
            update_event("")


# ---- system info (mocked) ----

class TestSystemInfo(EnvTestCase):
    def test_cpu_info(self):
        from friday.l1.system import cpu_info
        mock_data = [{"type": "CPU", "result": {
            "cpu": "Test CPU", "cores": {"physical": 4, "logical": 8},
            "frequency": {"base": 3000}, "temperature": None
        }}]
        with mock.patch("friday.l1.system._run_fastfetch", return_value=mock_data):
            result = cpu_info()
            self.assertEqual(result["model"], "Test CPU")
            self.assertEqual(result["cores_physical"], 4)

    def test_memory_info(self):
        from friday.l1.system import memory_info
        mock_data = [{"type": "Memory", "result": {"total": 8_000_000_000, "used": 4_000_000_000}}]
        with mock.patch("friday.l1.system._run_fastfetch", return_value=mock_data):
            result = memory_info()
            self.assertEqual(result["usage_percent"], 50.0)

    def test_disk_info(self):
        from friday.l1.system import disk_info
        mock_data = [{"type": "Disk", "result": [{
            "mountpoint": "C:\\", "filesystem": "NTFS",
            "bytes": {"total": 100_000_000_000, "used": 50_000_000_000, "free": 50_000_000_000}
        }]}]
        with mock.patch("friday.l1.system._run_fastfetch", return_value=mock_data):
            result = disk_info()
            self.assertEqual(len(result), 1)
            self.assertEqual(result[0]["usage_percent"], 50.0)

    def test_battery_no_battery(self):
        from friday.l1.system import battery_info
        mock_data = [{"type": "Battery", "result": {"status": "No battery"}}]
        with mock.patch("friday.l1.system._run_fastfetch", return_value=mock_data):
            result = battery_info()
            self.assertIsNone(result)

    def test_uptime_info(self):
        from friday.l1.system import uptime_info
        mock_data = [{"type": "Uptime", "result": {"uptime": 90000, "bootTime": "2026-08-19T10:00:00"}}]
        with mock.patch("friday.l1.system._run_fastfetch", return_value=mock_data):
            result = uptime_info()
            self.assertEqual(result["uptime_seconds"], 90000)
            self.assertIn("d", result["uptime_human"])

    def test_system_summary(self):
        from friday.l1.system import system_summary
        mock_data = [
            {"type": "OS", "result": {"prettyName": "Windows 11"}},
            {"type": "CPU", "result": {"cpu": "Test", "cores": {"physical": 2, "logical": 2}, "frequency": {"base": 2000}, "temperature": None}},
            {"type": "Memory", "result": {"total": 4_000_000_000, "used": 2_000_000_000}},
            {"type": "Disk", "result": [{"mountpoint": "C:\\", "filesystem": "NTFS", "bytes": {"total": 100_000_000_000, "used": 50_000_000_000, "free": 50_000_000_000}}]},
            {"type": "Battery", "result": {"status": "No battery"}},
            {"type": "Uptime", "result": {"uptime": 3600, "bootTime": "2026-08-19T10:00:00"}},
        ]
        with mock.patch("friday.l1.system._run_fastfetch", return_value=mock_data):
            result = system_summary()
            self.assertEqual(result["os"], "Windows 11")
            self.assertIn("memory", result)
            self.assertIn("disks", result)


if __name__ == "__main__":
    unittest.main()
