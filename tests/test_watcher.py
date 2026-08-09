"""Watch loop: config validation (incl. the invalid-days fix), time and
file trigger semantics, run_watcher end-to-end with a temp tasks file,
honest failure recording, and notification resilience."""

from __future__ import annotations

import json
import os
import unittest
from datetime import datetime
from pathlib import Path
from unittest import mock

from friday.errors import FridayError, PrimitiveError
from friday.watcher import _make_plan, _new_files, _run_trigger, _time_due, load_config, run_watcher
from tests.helpers import EnvTestCase


def _plan(directory, name):
    """A deterministic find_file plan with fast failure timing."""
    return {
        "goal": "locate " + name,
        "steps": [{"primitive": "files.find_file", "args": {"name": name, "directory": str(directory)},
                   "verify": {"check": "checks.file_exists", "args": {"path": "$steps.1.result.path"}, "expect": True},
                   # fast timing: failure paths must not poll for 8s
                   "verify_wait_s": 0.1, "backoff_s": 0.05}],
    }


class TestConfigValidation(EnvTestCase):
    def _write(self, payload) -> Path:
        f = self.mktmp() / "watcher.json"
        f.write_text(json.dumps(payload), encoding="utf-8")
        return f

    def test_valid_config(self):
        f = self._write({"triggers": [
            {"id": "a", "goal": "g", "schedule": {"type": "time", "at": "09:00", "days": ["mon", "Tue"]}},
            {"id": "b", "plan": {"goal": "p", "steps": []}, "schedule": {"type": "file", "directory": "/tmp", "name": ".pdf"}},
        ]})
        triggers = load_config(f)
        self.assertEqual([t["id"] for t in triggers], ["a", "b"])

    def test_missing_id(self):
        with self.assertRaises(FridayError):
            load_config(self._write({"triggers": [{"goal": "g", "schedule": {"type": "time", "at": "09:00"}}]}))

    def test_duplicate_id(self):
        with self.assertRaises(FridayError):
            load_config(self._write({"triggers": [
                {"id": "a", "goal": "g", "schedule": {"type": "time", "at": "09:00"}},
                {"id": "a", "goal": "g2", "schedule": {"type": "time", "at": "10:00"}},
            ]}))

    def test_missing_goal_and_plan(self):
        with self.assertRaises(FridayError):
            load_config(self._write({"triggers": [{"id": "a", "schedule": {"type": "time", "at": "09:00"}}]}))

    def test_bad_schedule_type(self):
        with self.assertRaises(FridayError):
            load_config(self._write({"triggers": [{"id": "a", "goal": "g", "schedule": {"type": "cron"}}]}))

    def test_bad_at(self):
        with self.assertRaises(FridayError):
            load_config(self._write({"triggers": [{"id": "a", "goal": "g", "schedule": {"type": "time", "at": "25:00"}}]}))

    def test_invalid_days_rejected_at_load(self):
        """Regression: an unknown day name must fail at load, not crash the
        daemon loop with an unhandled KeyError at fire time."""
        with self.assertRaises(FridayError) as ctx:
            load_config(self._write({"triggers": [
                {"id": "a", "goal": "g", "schedule": {"type": "time", "at": "09:00", "days": ["funday"]}}
            ]}))
        self.assertIn("unknown day", str(ctx.exception))

    def test_days_must_be_list(self):
        with self.assertRaises(FridayError):
            load_config(self._write({"triggers": [
                {"id": "a", "goal": "g", "schedule": {"type": "time", "at": "09:00", "days": "mon"}}
            ]}))

    def test_file_schedule_needs_directory(self):
        with self.assertRaises(FridayError):
            load_config(self._write({"triggers": [
                {"id": "a", "goal": "g", "schedule": {"type": "file"}}
            ]}))

    def test_bad_json(self):
        f = self.mktmp() / "w.json"
        f.write_text("{nope", encoding="utf-8")
        with self.assertRaises(FridayError):
            load_config(f)


class TestTimeDue(EnvTestCase):
    T = {"id": "t1", "schedule": {"type": "time", "at": "09:00", "days": ["mon"]}}

    def test_due_on_enabled_day_after_time(self):
        fired = {}
        self.assertTrue(_time_due(self.T, datetime(2026, 8, 10, 9, 30), fired))
        self.assertEqual(fired, {"t1": "2026-08-10"})

    def test_fires_once_per_day(self):
        fired = {"t1": "2026-08-10"}
        self.assertFalse(_time_due(self.T, datetime(2026, 8, 10, 23, 59), fired))
        self.assertTrue(_time_due(self.T, datetime(2026, 8, 17, 9, 1), fired))  # next monday

    def test_not_enabled_day(self):
        fired = {}
        self.assertFalse(_time_due(self.T, datetime(2026, 8, 11, 9, 30), fired))  # Tuesday
        self.assertEqual(fired, {})

    def test_before_time(self):
        fired = {}
        self.assertFalse(_time_due(self.T, datetime(2026, 8, 10, 8, 59), fired))
        self.assertEqual(fired, {})

    def test_no_days_means_every_day(self):
        fired = {}
        t = {"id": "x", "schedule": {"type": "time", "at": "00:00"}}
        self.assertTrue(_time_due(t, datetime(2026, 8, 10, 0, 1), fired))


class TestFileDue(EnvTestCase):
    def test_detects_new_files_once(self):
        base = self.mktmp()
        seen = set()
        t = {"id": "f", "schedule": {"type": "file", "directory": str(base), "name": ".txt"}}
        (base / "a.txt").write_text("x", encoding="utf-8")
        self.assertEqual(_new_files(t, seen), [str(base / "a.txt")])
        self.assertEqual(_new_files(t, seen), [])
        (base / "b.log").write_text("x", encoding="utf-8")
        self.assertEqual(_new_files(t, seen), [])  # name filter
        (base / "b.txt").write_text("x", encoding="utf-8")
        self.assertEqual(_new_files(t, seen), [str(base / "b.txt")])

    def test_missing_directory_is_not_due(self):
        self.assertEqual(_new_files({"id": "f", "schedule": {"type": "file", "directory": "/nonexistent", "name": "x"}}, set()), [])


class TestRunWatcher(EnvTestCase):
    def test_once_runs_due_triggers_and_records(self):
        d = self.mktmp()
        (time_dir := d / "time").mkdir()
        (file_dir := d / "file").mkdir()
        (time_dir / "alpha.txt").write_text("x", encoding="utf-8")
        (file_dir / "beta.txt").write_text("x", encoding="utf-8")
        cfg = d / "w.json"
        cfg.write_text(json.dumps({"triggers": [
            {"id": "run-time", "plan": _plan(time_dir, "alpha"), "schedule": {"type": "time", "at": "00:00"}, "notify": False},
            {"id": "run-file", "plan": _plan(file_dir, "beta"), "schedule": {"type": "file", "directory": str(file_dir), "name": "beta"}, "notify": False},
        ]}), encoding="utf-8")
        tasks = d / "tasks.jsonl"
        self.set_env(FRIDAY_TASKS_FILE=str(tasks))
        run_watcher(str(cfg), once=True)
        recs = [json.loads(l) for l in open(tasks, encoding="utf-8") if l.strip()]
        self.assertEqual(sorted(r["task_id"] for r in recs), ["watch:run-file", "watch:run-time"])
        for r in recs:
            self.assertTrue(r["gate6_passed"])
            proof = json.loads(r["proof"])
            self.assertEqual(proof["status"], "COMPLETED")
            self.assertEqual(proof["steps"][0]["status"], "VERIFIED")

    def test_failed_trigger_recorded_honestly(self):
        d = self.mktmp()
        (time_dir := d / "time").mkdir()
        cfg = d / "w.json"
        # find_file for a name that does not exist -> step ABORTs
        cfg.write_text(json.dumps({"triggers": [
            {"id": "fail-time", "plan": _plan(time_dir, "no-such-file"), "schedule": {"type": "time", "at": "00:00"}, "notify": False},
        ]}), encoding="utf-8")
        tasks = d / "tasks.jsonl"
        self.set_env(FRIDAY_TASKS_FILE=str(tasks))
        run_watcher(str(cfg), once=True)
        recs = [json.loads(l) for l in open(tasks, encoding="utf-8") if l.strip()]
        self.assertEqual(len(recs), 1)
        self.assertFalse(recs[0]["gate6_passed"])  # failures are data, never deleted
        self.assertEqual(json.loads(recs[0]["proof"])["status"], "ABORT")

    def test_notify_failure_does_not_break_run(self):
        d = self.mktmp()
        (time_dir := d / "time").mkdir()
        (time_dir / "alpha.txt").write_text("x", encoding="utf-8")
        cfg = d / "w.json"
        cfg.write_text(json.dumps({"triggers": [
            {"id": "notify-time", "plan": _plan(time_dir, "alpha"), "schedule": {"type": "time", "at": "00:00"}, "notify": True},
        ]}), encoding="utf-8")
        tasks = d / "tasks.jsonl"
        self.set_env(FRIDAY_TASKS_FILE=str(tasks))
        with mock.patch("friday.watcher.notify_send", side_effect=PrimitiveError("no daemon", state="x")):
            run_watcher(str(cfg), once=True)
        recs = [json.loads(l) for l in open(tasks, encoding="utf-8") if l.strip()]
        self.assertTrue(recs[0]["gate6_passed"])

    def test_poll_s_must_be_positive(self):
        with self.assertRaises(FridayError):
            run_watcher("/nonexistent.json", once=True, poll_s=0)

    def test_unknown_config_raises(self):
        with self.assertRaises(FridayError):
            run_watcher("/nonexistent/watcher.json", once=True)


class TestPlanCaching(EnvTestCase):
    """The 'one LLM call per distinct goal' claim: goal plans are cached
    for the daemon's lifetime; inline deterministic plans never touch the
    LLM; and a failed goal is popped from the cache so the next firing
    replans it."""

    def test_make_plan_caches_goal_across_firings(self):
        cache = {}
        t = {"id": "x", "goal": "g", "schedule": {"type": "time", "at": "09:00"}}
        plan = {"goal": "g", "steps": []}
        with mock.patch("friday.l4.planner.plan", return_value=plan) as m:
            p1 = _make_plan(t, cache, "r1")
            p2 = _make_plan(t, cache, "r2")  # same goal, second firing
        self.assertIs(p1, p2)
        self.assertEqual(m.call_count, 1)  # cached after the first call

    def test_inline_plan_never_calls_llm(self):
        cache = {}
        t = {"id": "x", "plan": {"goal": "p", "steps": []}, "schedule": {"type": "time", "at": "09:00"}}
        with mock.patch("friday.l4.planner.plan") as m:
            p = _make_plan(t, cache, "r1")
        m.assert_not_called()
        self.assertEqual(p["goal"], "p")

    def test_failed_goal_is_replanned_next_firing(self):
        d = self.mktmp()
        (time_dir := d / "time").mkdir()
        tasks = d / "tasks.jsonl"
        self.set_env(FRIDAY_TASKS_FILE=str(tasks))
        failing = _plan(time_dir, "no-such-file")  # step ABORTs -> run_plan raises
        cache = {}
        t = {"id": "nc", "goal": "locate no-such-file",
             "schedule": {"type": "time", "at": "00:00"}, "notify": False}
        with mock.patch("friday.l4.planner.plan", return_value=failing) as m:
            _run_trigger(t, cache)
            _run_trigger(t, cache)
        self.assertEqual(cache, {})  # failed plan popped, not cached
        self.assertEqual(m.call_count, 2)  # replanned on the next firing


if __name__ == "__main__":
    unittest.main()
