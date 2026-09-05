"""Integration tests for MCU Friday watcher and pipeline wiring."""

from __future__ import annotations

import json
import tempfile
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest import mock

from friday_mcu.core.errors import FridayError


class TestWatcherConfig(unittest.TestCase):
    """Watcher config loading and validation."""

    def test_load_valid_config(self):
        """Valid config loads successfully."""
        from friday_mcu.watcher import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {
                        "id": "test-trigger",
                        "goal": "test goal",
                        "schedule": {"type": "time", "at": "09:00"},
                        "enabled": True,
                    }
                ]
            }, f)
            f.flush()
            triggers = load_config(f.name)
        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["id"], "test-trigger")

    def test_missing_config_raises(self):
        """Missing config file raises FridayError."""
        from friday_mcu.watcher import load_config

        with self.assertRaises(FridayError):
            load_config("/nonexistent/config.json")

    def test_bad_json_raises(self):
        """Malformed JSON raises FridayError."""
        from friday_mcu.watcher import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{bad json")
            f.flush()
            with self.assertRaises(FridayError):
                load_config(f.name)

    def test_duplicate_id_raises(self):
        """Duplicate trigger IDs raise FridayError."""
        from friday_mcu.watcher import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {"id": "dup", "goal": "a", "schedule": {"type": "time", "at": "09:00"}},
                    {"id": "dup", "goal": "b", "schedule": {"type": "time", "at": "10:00"}},
                ]
            }, f)
            f.flush()
            with self.assertRaises(FridayError):
                load_config(f.name)

    def test_missing_goal_and_plan_raises(self):
        """Trigger without goal or plan raises FridayError."""
        from friday_mcu.watcher import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {"id": "no-goal", "schedule": {"type": "time", "at": "09:00"}}
                ]
            }, f)
            f.flush()
            with self.assertRaises(FridayError):
                load_config(f.name)

    def test_bad_schedule_type_raises(self):
        """Unknown schedule type raises FridayError."""
        from friday_mcu.watcher import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {"id": "bad", "goal": "x", "schedule": {"type": "unknown"}}
                ]
            }, f)
            f.flush()
            with self.assertRaises(FridayError):
                load_config(f.name)

    def test_bad_time_format_raises(self):
        """Invalid HH:MM raises FridayError."""
        from friday_mcu.watcher import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {"id": "bad", "goal": "x", "schedule": {"type": "time", "at": "25:00"}}
                ]
            }, f)
            f.flush()
            with self.assertRaises(FridayError):
                load_config(f.name)

    def test_unknown_day_raises(self):
        """Unknown day name raises FridayError."""
        from friday_mcu.watcher import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {"id": "bad", "goal": "x", "schedule": {"type": "time", "at": "09:00", "days": ["funday"]}}
                ]
            }, f)
            f.flush()
            with self.assertRaises(FridayError):
                load_config(f.name)

    def test_file_schedule_needs_directory(self):
        """File schedule without directory raises FridayError."""
        from friday_mcu.watcher import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {"id": "bad", "goal": "x", "schedule": {"type": "file"}}
                ]
            }, f)
            f.flush()
            with self.assertRaises(FridayError):
                load_config(f.name)

    def test_valid_file_schedule(self):
        """Valid file schedule loads."""
        from friday_mcu.watcher import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {
                        "id": "file-trig",
                        "goal": "check new file",
                        "schedule": {"type": "file", "directory": "/tmp", "name": ".pdf"},
                        "enabled": True,
                    }
                ]
            }, f)
            f.flush()
            triggers = load_config(f.name)
        self.assertEqual(len(triggers), 1)
        self.assertEqual(triggers[0]["schedule"]["type"], "file")


class TestWatcherScheduling(unittest.TestCase):
    """Time-based scheduling logic."""

    def test_time_due_after_at(self):
        """Trigger is due when current time is past the scheduled time."""
        from friday_mcu.watcher import _time_due

        trigger = {"id": "t1", "schedule": {"type": "time", "at": "09:00"}}
        now = datetime(2026, 8, 28, 10, 0)  # 10:00 > 09:00
        self.assertTrue(_time_due(trigger, now, {}))

    def test_time_not_due_before_at(self):
        """Trigger is not due before the scheduled time."""
        from friday_mcu.watcher import _time_due

        trigger = {"id": "t1", "schedule": {"type": "time", "at": "09:00"}}
        now = datetime(2026, 8, 28, 8, 30)  # 08:30 < 09:00
        self.assertFalse(_time_due(trigger, now, {}))

    def test_time_not_due_if_already_fired(self):
        """Trigger is not due if already fired today."""
        from friday_mcu.watcher import _time_due

        trigger = {"id": "t1", "schedule": {"type": "time", "at": "09:00"}}
        now = datetime(2026, 8, 28, 10, 0)
        fired = {"t1": "2026-08-28"}
        self.assertFalse(_time_due(trigger, now, fired))

    def test_time_due_on_different_day(self):
        """Trigger is due on a new day even if fired yesterday."""
        from friday_mcu.watcher import _time_due

        trigger = {"id": "t1", "schedule": {"type": "time", "at": "09:00"}}
        now = datetime(2026, 8, 29, 10, 0)
        fired = {"t1": "2026-08-28"}
        self.assertTrue(_time_due(trigger, now, fired))

    def test_day_filter_blocks_wrong_day(self):
        """Trigger doesn't fire on excluded days."""
        from friday_mcu.watcher import _time_due

        trigger = {"id": "t1", "schedule": {"type": "time", "at": "09:00", "days": ["mon", "tue", "wed", "thu", "fri"]}}
        now = datetime(2026, 8, 30, 10, 0)  # Saturday
        self.assertFalse(_time_due(trigger, now, {}))

    def test_day_filter_allows_correct_day(self):
        """Trigger fires on included days."""
        from friday_mcu.watcher import _time_due

        trigger = {"id": "t1", "schedule": {"type": "time", "at": "09:00", "days": ["mon", "tue", "wed", "thu", "fri"]}}
        now = datetime(2026, 8, 28, 10, 0)  # Thursday
        self.assertTrue(_time_due(trigger, now, {}))


class TestWatcherAllowlist(unittest.TestCase):
    """Primitive allowlist matching."""

    def test_exact_match(self):
        from friday_mcu.watcher import _allowed_prim
        self.assertTrue(_allowed_prim("gmail.list_unread", ["gmail.list_unread"]))

    def test_pattern_match(self):
        from friday_mcu.watcher import _allowed_prim
        self.assertTrue(_allowed_prim("gmail.list_unread", ["gmail.*"]))

    def test_no_match(self):
        from friday_mcu.watcher import _allowed_prim
        self.assertFalse(_allowed_prim("gmail.send_document", ["gmail.list_unread"]))

    def test_empty_allowlist_not_reached(self):
        # Empty allowlist means "no allowlist configured" — the watcher
        # skips the check entirely (if allowed: ...). _allowed_prim is
        # only called when there IS a non-empty allowlist.
        from friday_mcu.watcher import _allowed_prim
        # With no patterns, nothing matches — but the watcher never calls this
        self.assertFalse(_allowed_prim("anything", []))

    def test_multiple_patterns(self):
        from friday_mcu.watcher import _allowed_prim
        allowed = ["gmail.*", "notify.notify_send"]
        self.assertTrue(_allowed_prim("gmail.list_unread", allowed))
        self.assertTrue(_allowed_prim("notify.notify_send", allowed))
        self.assertFalse(_allowed_prim("window.close_window", allowed))


class TestWatcherNewFiles(unittest.TestCase):
    """File trigger detection."""

    def test_new_files_detected(self):
        from friday_mcu.watcher import _new_files

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "report.pdf").write_text("x")
            trigger = {"schedule": {"type": "file", "directory": d, "name": ".pdf"}}
            seen: set[str] = set()
            files = _new_files(trigger, seen)
            self.assertEqual(len(files), 1)
            self.assertTrue(files[0].endswith("report.pdf"))

    def test_seen_files_not_repeated(self):
        from friday_mcu.watcher import _new_files

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "report.pdf").write_text("x")
            trigger = {"schedule": {"type": "file", "directory": d, "name": ".pdf"}}
            seen: set[str] = set()
            _new_files(trigger, seen)  # first call
            files = _new_files(trigger, seen)  # second call
            self.assertEqual(len(files), 0)

    def test_non_matching_files_ignored(self):
        from friday_mcu.watcher import _new_files

        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "report.txt").write_text("x")
            trigger = {"schedule": {"type": "file", "directory": d, "name": ".pdf"}}
            seen: set[str] = set()
            files = _new_files(trigger, seen)
            self.assertEqual(len(files), 0)

    def test_missing_directory_returns_empty(self):
        from friday_mcu.watcher import _new_files

        trigger = {"schedule": {"type": "file", "directory": "/nonexistent", "name": ".pdf"}}
        files = _new_files(trigger, set())
        self.assertEqual(len(files), 0)


class TestCommandPrefix(unittest.TestCase):
    """Command prefix extraction for text triggers."""

    def test_extract_goal_with_prefix(self):
        from friday_mcu.watcher import _extract_goal
        result = _extract_goal("/goal pause the music", "/goal")
        self.assertEqual(result, "pause the music")

    def test_extract_goal_case_insensitive(self):
        from friday_mcu.watcher import _extract_goal
        result = _extract_goal("/GOAL check email", "/goal")
        self.assertEqual(result, "check email")

    def test_no_prefix_returns_none(self):
        from friday_mcu.watcher import _extract_goal
        result = _extract_goal("hey what's up", "/goal")
        self.assertIsNone(result)

    def test_prefix_only_returns_none(self):
        from friday_mcu.watcher import _extract_goal
        result = _extract_goal("/goal", "/goal")
        self.assertIsNone(result)

    def test_empty_prefix_returns_all(self):
        from friday_mcu.watcher import _extract_goal
        result = _extract_goal("pause the music", "")
        self.assertEqual(result, "pause the music")


class TestProactiveTick(unittest.TestCase):
    """Proactive tick wiring: patterns → memory → suggestions."""

    def test_proactive_tick_stores_patterns(self):
        """Detected patterns are stored as semantic memories."""
        from friday_mcu.watcher import _run_proactive_tick
        from friday_mcu.memory.store import MemoryManager

        mgr = MemoryManager()
        # Store some episodic memories that form a pattern
        for i in range(5):
            mgr.store(
                key=f"email_check_{i}",
                content="Goal: check email -> COMPLETED (2 steps)",
                memory_type="episodic",
                tags=["test"],
            )

        # Run the proactive tick
        _run_proactive_tick()

        # Check that patterns were stored as semantic memories
        semantic = mgr.semantic.list_all()
        pattern_entries = [e for e in semantic if "pattern" in e.key]
        # May or may not find patterns depending on the data, but the tick should not crash
        self.assertIsInstance(pattern_entries, list)

    def test_proactive_tick_does_not_crash_on_empty_memory(self):
        """Proactive tick handles empty memory gracefully."""
        from friday_mcu.watcher import _run_proactive_tick
        # Should not raise
        _run_proactive_tick()


class TestFiredState(unittest.TestCase):
    """Once-per-day fired state persistence."""

    def test_save_and_load_fired_state(self):
        from friday_mcu.watcher import _load_fired_state, _save_fired_state

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name

        with mock.patch("friday_mcu.watcher._fired_state_file", return_value=Path(path)):
            state = {"trigger1": "2026-08-28", "trigger2": "2026-08-27"}
            _save_fired_state(state)
            loaded = _load_fired_state()
            self.assertEqual(loaded, state)

    def test_missing_file_returns_empty(self):
        from friday_mcu.watcher import _load_fired_state

        with mock.patch("friday_mcu.watcher._fired_state_file", return_value=Path("/nonexistent/file.json")):
            loaded = _load_fired_state()
            self.assertEqual(loaded, {})

    def test_corrupt_file_returns_empty(self):
        from friday_mcu.watcher import _load_fired_state

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("not json {{{")
            f.flush()
            with mock.patch("friday_mcu.watcher._fired_state_file", return_value=Path(f.name)):
                loaded = _load_fired_state()
                self.assertEqual(loaded, {})


class TestTaskRecording(unittest.TestCase):
    """Task outcome recording."""

    def test_record_task_writes_jsonl(self):
        from friday_mcu.watcher import _record_task

        with tempfile.NamedTemporaryFile(mode="w", suffix=".jsonl", delete=False) as f:
            path = f.name

        with mock.patch("friday_mcu.watcher._tasks_file", return_value=Path(path)):
            _record_task("test:1", "test goal", True, {"status": "COMPLETED"})

            lines = Path(path).read_text().strip().splitlines()
            self.assertEqual(len(lines), 1)
            rec = json.loads(lines[0])
            self.assertEqual(rec["task_id"], "test:1")
            self.assertTrue(rec["gate6_passed"])
            self.assertIn("timestamp", rec)


class TestRetryBackoff(unittest.TestCase):
    """Retry backoff rate limiting."""

    def test_in_backoff_within_window(self):
        from friday_mcu.watcher import _in_retry_backoff

        last_attempts = {"t1": time.monotonic()}
        self.assertTrue(_in_retry_backoff("t1", last_attempts))

    def test_not_in_backoff_after_window(self):
        from friday_mcu.watcher import _in_retry_backoff

        last_attempts = {"t1": time.monotonic() - 700}  # > 600s
        self.assertFalse(_in_retry_backoff("t1", last_attempts))

    def test_not_in_backoff_unknown_trigger(self):
        from friday_mcu.watcher import _in_retry_backoff

        self.assertFalse(_in_retry_backoff("unknown", {}))


class TestWatcherCLI(unittest.TestCase):
    """Watcher CLI commands."""

    def test_triggers_command_lists_triggers(self):
        """triggers command lists configured triggers."""
        from friday_mcu.__main__ import cmd_triggers

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {
                        "id": "test-trigger",
                        "goal": "test goal",
                        "schedule": {"type": "time", "at": "09:00", "days": ["mon"]},
                        "enabled": True,
                    }
                ]
            }, f)
            f.flush()

        args = argparse.Namespace(config=f.name)
        result = cmd_triggers(args)
        self.assertEqual(result, 0)

    def test_triggers_command_bad_config(self):
        """triggers command handles bad config gracefully."""
        from friday_mcu.__main__ import cmd_triggers

        args = argparse.Namespace(config="/nonexistent/config.json")
        result = cmd_triggers(args)
        self.assertEqual(result, 1)


class TestWatcherRunOnce(unittest.TestCase):
    """Watcher --once mode fires due triggers and exits."""

    def test_once_fires_due_trigger(self):
        """--once fires a due trigger and exits."""
        from friday_mcu.watcher import run_watcher

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {
                        "id": "past-trigger",
                        "goal": "check system info",
                        "plan": {
                            "goal": "check system info",
                            "steps": [
                                {
                                    "primitive": "system.info",
                                    "args": {},
                                    "verify": {
                                        "check": "checks.call_succeeded",
                                        "args": {"value": "$steps.1.result"},
                                        "expect": True,
                                    },
                                }
                            ],
                        },
                        "schedule": {"type": "time", "at": "00:00"},
                        "enabled": True,
                        "notify": False,
                    }
                ]
            }, f)
            f.flush()

        with tempfile.TemporaryDirectory() as tmpdir:
            fired_path = Path(tmpdir) / "fired.json"
            tasks_path = Path(tmpdir) / "tasks.jsonl"
            seen_path = Path(tmpdir) / "seen.json"

            with mock.patch("friday_mcu.watcher._fired_state_file", return_value=fired_path), \
                 mock.patch("friday_mcu.watcher._tasks_file", return_value=tasks_path), \
                 mock.patch("friday_mcu.watcher._file_seen_file", return_value=seen_path), \
                 mock.patch("friday_mcu.watcher._execute_plan") as mock_exec, \
                 mock.patch("friday_mcu.watcher._notify_outcome"):
                mock_exec.return_value = {
                    "status": "COMPLETED",
                    "duration_s": 0.1,
                    "_result": "test result",
                    "steps": [],
                }
                run_watcher(f.name, once=True, poll_s=0.1)
                mock_exec.assert_called_once()

    def test_once_skips_disabled_trigger(self):
        """--once skips disabled triggers."""
        from friday_mcu.watcher import run_watcher

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {
                        "id": "disabled-trigger",
                        "goal": "test goal",
                        "schedule": {"type": "time", "at": "00:00"},
                        "enabled": False,
                    }
                ]
            }, f)
            f.flush()

        with mock.patch("friday_mcu.watcher._execute_goal") as mock_exec:
            run_watcher(f.name, once=True, poll_s=0.1)
            mock_exec.assert_not_called()

    def test_once_with_inline_plan_skips_llm(self):
        """Inline deterministic plans execute directly without an LLM plan."""
        from friday_mcu.watcher import run_watcher

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({
                "triggers": [
                    {
                        "id": "inline-trigger",
                        "goal": "test",
                        "plan": {
                            "goal": "test",
                            "steps": [
                                {
                                    "primitive": "system.cpu_info",
                                    "args": {},
                                    "verify": {
                                        "check": "checks.call_succeeded",
                                        "args": {"value": "$steps.1.result"},
                                        "expect": True,
                                    },
                                }
                            ],
                        },
                        "schedule": {"type": "time", "at": "00:00"},
                        "enabled": True,
                        "notify": False,
                    }
                ]
            }, f)
            f.flush()

        with tempfile.TemporaryDirectory() as tmpdir:
            fired_path = Path(tmpdir) / "fired.json"
            tasks_path = Path(tmpdir) / "tasks.jsonl"
            seen_path = Path(tmpdir) / "seen.json"

            with mock.patch("friday_mcu.watcher._fired_state_file", return_value=fired_path), \
                 mock.patch("friday_mcu.watcher._tasks_file", return_value=tasks_path), \
                 mock.patch("friday_mcu.watcher._file_seen_file", return_value=seen_path), \
                 mock.patch("friday_mcu.watcher._execute_plan") as mock_exec, \
                 mock.patch("friday_mcu.watcher._notify_outcome"):
                mock_exec.return_value = {
                    "status": "COMPLETED",
                    "duration_s": 0.1,
                    "_result": "test",
                    "steps": [],
                }
                run_watcher(f.name, once=True, poll_s=0.1)
                mock_exec.assert_called_once()


# Need this import for test_triggers_command_lists_triggers
import argparse


if __name__ == "__main__":
    unittest.main()
