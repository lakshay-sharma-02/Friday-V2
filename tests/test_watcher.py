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
from friday.watcher import _emit_heartbeat, _make_plan, _new_files, _run_trigger, _time_due, load_config, run_watcher
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

    def test_committed_digest_trigger_plan_validates(self):
        """The enabled weekly-cross-project-digest trigger (Phase C v2) is
        part of the committed config: it must load, and its deterministic
        plan must pass the REAL planner validate_plan (registered
        primitives, real checks, correct kwargs, no unresolved $facts). A
        primitive rename or schema drift fails here, not on Sunday."""
        from friday.l4.planner import validate_plan
        from friday.watcher import DEFAULT_CONFIG

        triggers = load_config(DEFAULT_CONFIG)
        digest = next((t for t in triggers if t["id"] == "weekly-cross-project-digest"), None)
        self.assertIsNotNone(digest, "committed config must carry the digest trigger")
        self.assertTrue(digest.get("enabled", True))
        ok, err = validate_plan(digest["plan"])
        self.assertTrue(ok, f"committed digest plan must validate: {err}")
        allowed = digest.get("allow")
        plan_prims = {s["primitive"] for s in digest["plan"]["steps"]}
        self.assertEqual(
            plan_prims, set(allowed or []),
            "every plan primitive must be on the trigger allowlist",
        )

    def test_committed_reminder_trigger_plan_validates(self):
        """The enabled sunday-digest-reminder trigger (the DIGEST_TRACKING.md
        nudge) is part of the committed config: it must load, its plan must
        pass the REAL planner validate_plan, and its one notify step must be
        allowlisted. It complements the digest trigger (fires 10:05 Sundays,
        5 minutes after the digest) and is a zero-LLM static notify."""
        from friday.l4.planner import validate_plan
        from friday.watcher import DEFAULT_CONFIG

        triggers = load_config(DEFAULT_CONFIG)
        reminder = next((t for t in triggers if t["id"] == "sunday-digest-reminder"), None)
        self.assertIsNotNone(reminder, "committed config must carry the reminder trigger")
        self.assertTrue(reminder.get("enabled", True))
        self.assertEqual(reminder.get("notify"), False, "must not double-ping (plan is itself a notify)")
        ok, err = validate_plan(reminder["plan"])
        self.assertTrue(ok, f"committed reminder plan must validate: {err}")
        self.assertEqual(
            {s["primitive"] for s in reminder["plan"]["steps"]},
            set(reminder.get("allow") or []),
            "every plan primitive must be on the trigger allowlist",
        )

    def test_committed_gap_probes_retired_after_registration(self):
        """The ambient-gap-probe triggers were the deliberate ambient
        volume source for the self-improvement loop. BOTH probes are now
        RETIRED per the documented lifecycle - a daily refusal of a solved
        primitive is noise: EMAIL-SEND (2026-08-11, gmail.send_document
        hand-built + registered) and CALENDAR (2026-08-13, the loop's
        SECOND complete cycle: calendar.list_upcoming was LLM-drafted,
        passed the self-check repair loop + the full automated gate with
        ZERO hand-correction, human-signed and registered). Each probe
        must be DISABLED in the committed config and its primitive
        REGISTERED."""
        import importlib.util

        from friday.capability_gaps import unprocessed_gaps
        from friday.l1 import calendar as calendar_mod, gmail as gmail_mod
        from friday.watcher import DEFAULT_CONFIG

        self.assertTrue(
            hasattr(gmail_mod, "send_document"),
            "gmail.send_document must be registered (email-send probe retired because its primitive was built)",
        )
        self.assertIsNotNone(
            importlib.util.find_spec("friday.l1.calendar"),
            "friday.l1.calendar must now exist (calendar probe retired because its primitive was built)",
        )
        self.assertTrue(
            hasattr(calendar_mod, "list_upcoming"),
            "calendar.list_upcoming must be registered (cycle 2, 2026-08-13)",
        )

        triggers = {t["id"]: t for t in load_config(DEFAULT_CONFIG)}

        for pid in ("ambient-gap-probe-email-send", "ambient-gap-probe-calendar"):
            t = triggers.get(pid)
            self.assertIsNotNone(t, f"committed config must carry {pid}")
            self.assertFalse(
                t.get("enabled", True),
                f"{pid} must be DISABLED after its primitive was registered",
            )

        # no unprocessed gaps may remain for either retired probe's primitive
        if unprocessed_gaps():
            self.assertTrue(
                all(g.get("attempted_primitive") not in ("calendar.list_upcoming", "gmail.send_document")
                    for g in unprocessed_gaps()),
                "no unprocessed gaps for retired-probe primitives",
            )

    def test_committed_file_write_probe_retired_after_registration(self):
        """ambient-gap-probe-file-write (added 2026-08-13) targeted
        files.write_text - a WRITE-capable files.* primitive, genuinely
        UNBUILT when the probe was added, chosen because files.* is the ONE
        primitive class where build-verify is real. Its one live firing
        produced a gap, triage drafted, the sandbox caught a real runtime
        bug (newline=mode), the human corrected it, Fix 2 added write-family
        build-verify, and the corrected draft passed the FULL gate and was
        REGISTERED 2026-08-13. The probe's job is done: it must now be
        DISABLED (email-send lifecycle precedent), files.write_text must be
        registered, and any straggler gaps for it must be consumed as SOLVED
        by triage - never re-drafted."""
        from friday.capability_gaps import all_gaps, unprocessed_gaps
        from friday.watcher import DEFAULT_CONFIG

        import importlib.util

        self.assertIsNotNone(
            importlib.util.find_spec("friday.l1.files"),
            "files module exists",
        )
        self.assertTrue(
            hasattr(__import__("friday.l1.files", fromlist=["x"]), "write_text"),
            "files.write_text must now be REGISTERED (the file-write probe was retired "
            "because its primitive was built through the full loop)",
        )

        triggers = {t["id"]: t for t in load_config(DEFAULT_CONFIG)}
        pid = "ambient-gap-probe-file-write"
        t = triggers.get(pid)
        self.assertIsNotNone(t, f"committed config must carry {pid}")
        self.assertFalse(
            t.get("enabled", True),
            f"{pid} must be DISABLED after files.write_text registered (2026-08-13 lifecycle)",
        )
        self.assertEqual(
            t["plan"]["steps"][0]["primitive"], "files.write_text",
            f"{pid} must still name the primitive it probed",
        )
        # a straggler gap for the now-registered primitive is consumed as
        # SOLVED by triage - never LLM-drafted again (test_registered_primitive_gaps_consumed_without_drafting
        # covers the mechanism; this pins the committed-config side)
        if unprocessed_gaps():
            self.assertTrue(
                all(g.get("attempted_primitive") != "files.write_text" for g in unprocessed_gaps()),
                "no unprocessed files.write_text gap may remain post-registration",
            )

    def test_committed_morning_allowlist_stays_read_only(self):
        """The enabled morning-gmail-summary trigger's allowlist must stay
        EXACTLY the three read-only primitives. It was tightened from
        'gmail.*' on 2026-08-11 (when gmail.send_document registered) so
        the LLM-planned unattended trigger can never reach a send-capable
        primitive - the registered send primitive is REFUSED by the
        committed list. Any future edit that broadens it (a wildcard, or
        any name containing 'send') fails here, on commit, not at 09:00
        on a weekday."""
        from friday.watcher import DEFAULT_CONFIG, _allowed_prim

        triggers = {t["id"]: t for t in load_config(DEFAULT_CONFIG)}
        morning = triggers.get("morning-gmail-summary")
        self.assertIsNotNone(morning, "committed config must carry the morning trigger")
        self.assertTrue(morning.get("enabled", True))
        allowed = morning.get("allow")
        # set equality (same convention as the digest-trigger guard) pins
        # exactly the three read-only primitives, order-independent
        self.assertEqual(
            set(allowed or []),
            {"gmail.list_unread", "gmail.get_message", "gmail.summarize"},
            "morning allowlist must be exactly the three read-only primitives "
            "(no wildcard, no additions)",
        )
        self.assertFalse(
            _allowed_prim("gmail.send_document", allowed),
            "the read-only guard must REFUSE the registered send primitive",
        )
        self.assertFalse(
            any("send" in name for name in (allowed or [])),
            "no send-capable primitive may ever appear on the morning allowlist",
        )


class TestTimeDue(EnvTestCase):
    T = {"id": "t1", "schedule": {"type": "time", "at": "09:00", "days": ["mon"]}}

    def test_due_on_enabled_day_after_time(self):
        fired = {}
        self.assertTrue(_time_due(self.T, datetime(2026, 8, 10, 9, 30), fired))
        # PURE check: _time_due never mutates - the caller marks fired
        # only after a COMPLETED run
        self.assertEqual(fired, {})

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


class TestFiredState(EnvTestCase):
    """Persisted once-per-day fired state (var/state/watcher_fired.json):
    a trigger that already ran today must NOT re-fire on restart; a new
    day rolls over and fires; missing or corrupt state fails safe to
    not-yet-fired, never a crash."""

    def _setup(self, d: Path) -> tuple[Path, Path, Path]:
        (d / "time").mkdir()
        (d / "time" / "alpha.txt").write_text("x", encoding="utf-8")
        cfg = d / "w.json"
        cfg.write_text(json.dumps({"triggers": [
            {"id": "daily", "plan": _plan(d / "time", "alpha"),
             "schedule": {"type": "time", "at": "00:00"}, "notify": False},
        ]}), encoding="utf-8")
        tasks = d / "tasks.jsonl"
        fired = d / "fired.json"
        self.set_env(FRIDAY_TASKS_FILE=str(tasks), FRIDAY_FIRED_FILE=str(fired))
        return cfg, tasks, fired

    @staticmethod
    def _records(tasks: Path) -> list[dict]:
        if not tasks.is_file():
            return []  # nothing fired -> no task file yet (expected in no-refire)
        return [json.loads(l) for l in open(tasks, encoding="utf-8") if l.strip()]

    def test_restart_same_day_does_not_refire(self):
        """The regression: a restart after today's firing must not produce
        a duplicate action (this was a real bug - the 23:32 service
        restart re-sent the morning digest that already went out at 23:29)."""
        cfg, tasks, fired = self._setup(self.mktmp())
        today = datetime.now().date().isoformat()
        fired.write_text(json.dumps({"daily": today}), encoding="utf-8")
        run_watcher(str(cfg), once=True)   # restart 1
        run_watcher(str(cfg), once=True)   # restart 2
        self.assertEqual(self._records(tasks), [])  # already fired today - never re-fires
        self.assertEqual(json.loads(fired.read_text())["daily"], today)

    def test_restart_new_day_fires(self):
        cfg, tasks, fired = self._setup(self.mktmp())
        fired.write_text(json.dumps({"daily": "1999-01-01"}), encoding="utf-8")
        run_watcher(str(cfg), once=True)
        recs = self._records(tasks)
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0]["gate6_passed"])
        self.assertEqual(json.loads(fired.read_text())["daily"], datetime.now().date().isoformat())

    def test_missing_state_fails_safe(self):
        cfg, tasks, fired = self._setup(self.mktmp())
        run_watcher(str(cfg), once=True)
        self.assertEqual(len(self._records(tasks)), 1)  # fires; state file created
        self.assertTrue(fired.is_file())

    def test_corrupt_state_fails_safe(self):
        for bad in ("{not json", "[]", '{"daily": 42}'):
            cfg, tasks, fired = self._setup(self.mktmp())
            fired.write_text(bad, encoding="utf-8")
            run_watcher(str(cfg), once=True)  # must not crash
            self.assertEqual(len(self._records(tasks)), 1, bad)

    def test_daemon_mode_persists_and_survives_restart(self):
        """Daemon mode: first run fires + persists; a restarted daemon on
        the same day does not re-fire."""
        cfg, tasks, fired = self._setup(self.mktmp())

        def _run_once() -> None:
            calls = {"n": 0}

            def fake_sleep(_s: float) -> None:
                calls["n"] += 1
                if calls["n"] >= 1:
                    raise KeyboardInterrupt

            with mock.patch("friday.watcher.time.monotonic", return_value=1000.0), \
                 mock.patch("friday.watcher.time.sleep", side_effect=fake_sleep):
                run_watcher(str(cfg), once=False, poll_s=0.01)

        _run_once()   # daemon start: fires + persists
        _run_once()   # restart same day: must NOT re-fire
        self.assertEqual(len(self._records(tasks)), 1)


class TestRetryOnFailure(EnvTestCase):
    """Fired-state is recorded only on genuine SUCCESS. A FAILED/ABORTed
    run stays eligible to retry later the same day, rate-limited by
    RETRY_BACKOFF_S so a persistent failure never hammers the LLM API - a
    transient failure must not silently consume the day's slot."""

    def test_failed_run_not_marked_fired_and_retried(self):
        d = self.mktmp()
        (d / "time").mkdir()  # alpha.txt absent -> find_file ABORTs -> FAILED
        cfg = d / "w.json"
        cfg.write_text(json.dumps({"triggers": [
            {"id": "daily", "plan": _plan(d / "time", "no-such-file"),
             "schedule": {"type": "time", "at": "00:00"}, "notify": False},
        ]}), encoding="utf-8")
        tasks = d / "tasks.jsonl"
        fired = d / "fired.json"
        self.set_env(FRIDAY_TASKS_FILE=str(tasks), FRIDAY_FIRED_FILE=str(fired))
        run_watcher(str(cfg), once=True)  # attempt 1: FAILS
        run_watcher(str(cfg), once=True)  # a later pass: eligible again
        recs = [json.loads(l) for l in open(tasks, encoding="utf-8") if l.strip()]
        self.assertEqual(len(recs), 2, "a FAILED run must not consume the day's slot")
        self.assertTrue(all(not r["gate6_passed"] for r in recs))
        saved = json.loads(fired.read_text()) if fired.is_file() else {}
        self.assertNotIn("daily", saved, "FAILED runs must not be marked fired")

    def test_completed_run_marks_fired_not_retried(self):
        d = self.mktmp()
        (d / "time").mkdir()
        (d / "time" / "alpha.txt").write_text("x", encoding="utf-8")
        cfg = d / "w.json"
        cfg.write_text(json.dumps({"triggers": [
            {"id": "daily", "plan": _plan(d / "time", "alpha"),
             "schedule": {"type": "time", "at": "00:00"}, "notify": False},
        ]}), encoding="utf-8")
        tasks = d / "tasks.jsonl"
        fired = d / "fired.json"
        self.set_env(FRIDAY_TASKS_FILE=str(tasks), FRIDAY_FIRED_FILE=str(fired))
        run_watcher(str(cfg), once=True)
        run_watcher(str(cfg), once=True)  # restart same day
        recs = [json.loads(l) for l in open(tasks, encoding="utf-8") if l.strip()]
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0]["gate6_passed"])
        self.assertEqual(json.loads(fired.read_text())["daily"], datetime.now().date().isoformat())

    def test_refused_run_marks_fired_not_retried(self):
        """An allowlist REFUSAL is the safe terminal outcome for the day:
        it marks fired. Retrying would replan (LLM call) and re-refuse
        every backoff, adding a gap record each time - the pre-change
        behavior was one refusal per daemon run, and that must survive."""
        d = self.mktmp()
        (d / "time").mkdir()
        tasks = d / "tasks.jsonl"
        fired = d / "fired.json"
        self.set_env(FRIDAY_TASKS_FILE=str(tasks), FRIDAY_FIRED_FILE=str(fired))
        cfg = d / "w.json"
        cfg.write_text(json.dumps({"triggers": [
            {"id": "daily",
             "plan": {"goal": "g", "steps": [
                 {"primitive": "whatsapp.send_text", "args": {},
                  "verify": {"check": "checks.message_sent", "args": {}, "expect": True}}]},
             "schedule": {"type": "time", "at": "00:00"}, "notify": False,
             "allow": ["gmail.*"]},
        ]}), encoding="utf-8")
        run_watcher(str(cfg), once=True)
        run_watcher(str(cfg), once=True)  # restart same day
        recs = [json.loads(l) for l in open(tasks, encoding="utf-8") if l.strip()]
        self.assertEqual(len(recs), 1, "a REFUSED run is terminal for the day - no retry storm")
        self.assertEqual(json.loads(recs[0]["proof"])["status"], "REFUSED")
        saved = json.loads(fired.read_text()) if fired.is_file() else {}
        self.assertEqual(saved.get("daily"), datetime.now().date().isoformat())

    def test_backoff_gates_retry_cadence(self):
        """A persistently-FAILED trigger retries, but attempts are spaced
        >= RETRY_BACKOFF_S apart - never every poll."""
        d = self.mktmp()
        (d / "time").mkdir()
        (d / "time" / "alpha.txt").write_text("x", encoding="utf-8")
        cfg = d / "w.json"
        cfg.write_text(json.dumps({"triggers": [
            {"id": "daily", "plan": _plan(d / "time", "alpha"),
             "schedule": {"type": "time", "at": "00:00"}, "notify": False},
        ]}), encoding="utf-8")
        self.set_env(FRIDAY_TASKS_FILE=str(d / "tasks.jsonl"), FRIDAY_FIRED_FILE=str(d / "fired.json"))
        clock = {"t": 1000.0}
        attempts: list[float] = []
        sleeps = {"n": 0}

        def fake_monotonic() -> float:
            return clock["t"]

        def fake_sleep(_s: float) -> None:
            sleeps["n"] += 1
            clock["t"] += 40.0
            if sleeps["n"] >= 40:
                raise KeyboardInterrupt

        def fake_run(_t, _cache):
            attempts.append(clock["t"])
            return False, {"trigger": "daily", "status": "FAILED"}

        with mock.patch("friday.watcher._run_trigger", side_effect=fake_run), \
             mock.patch("friday.watcher.RETRY_BACKOFF_S", 100.0), \
             mock.patch("friday.watcher.time.monotonic", side_effect=fake_monotonic), \
             mock.patch("friday.watcher.time.sleep", side_effect=fake_sleep):
            run_watcher(str(cfg), once=False, poll_s=0.01)
        self.assertGreater(len(attempts), 1, "a FAILED trigger must be retried")
        for a, b in zip(attempts, attempts[1:]):
            self.assertGreaterEqual(b - a, 100.0, "retries must respect RETRY_BACKOFF_S")
        self.assertLess(len(attempts), 20, "backoff must bound retries (not every poll)")


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


class TestHeartbeat(EnvTestCase):
    """The daemon.alive heartbeat: one structured L0 line on a fixed
    interval with uptime, the last trigger that fired, and the current
    capability-gap count - the ambient-volume signal the triage loop
    consumes. Best-effort: a broken gap file reports -1, never crashes."""

    def test_emit_heartbeat_reports_liveness(self):
        gaps = self.mktmp() / "gaps.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        from friday.capability_gaps import record_gap

        record_gap(source="executor", goal_id="g", attempted_primitive="a.b",
                   goal_context="g", refusal_reason="r")
        record_gap(source="watcher", trigger_id="t", attempted_primitive="c.d",
                   goal_context="g", refusal_reason="r")
        with mock.patch("friday.watcher.emit_event") as m:
            _emit_heartbeat(5.0, "morning-gmail-summary", "2026-08-10T09:00:00+00:00")
        call = m.call_args
        self.assertEqual(call.kwargs["layer"], "WATCH")
        self.assertEqual(call.kwargs["primitive"], "daemon.alive")
        self.assertEqual(call.kwargs["result"], "ALIVE")
        args = call.kwargs["args"]
        self.assertEqual(args["last_trigger"], "morning-gmail-summary")
        self.assertEqual(args["last_trigger_at"], "2026-08-10T09:00:00+00:00")
        self.assertEqual(args["capability_gaps"], 2)
        self.assertIsInstance(args["uptime_s"], int)

    def test_emit_heartbeat_never_fires_without_trigger(self):
        gaps = self.mktmp() / "gaps.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        with mock.patch("friday.watcher.emit_event") as m:
            _emit_heartbeat(0.0, None, None)
        args = m.call_args.kwargs["args"]
        self.assertEqual(args["last_trigger"], "none")
        self.assertEqual(args["capability_gaps"], 0)

    def _clock_loop(self, heartbeat_s: float, poll_step: float, stop_after: int):
        """Run run_watcher under a fake monotonic clock that advances
        poll_step per sleep, raising KeyboardInterrupt after stop_after
        sleeps. Returns the emit_event mock."""
        cfg = self.mktmp() / "w.json"
        cfg.write_text(json.dumps({"triggers": []}), encoding="utf-8")
        clock = {"t": 1000.0}
        calls = {"n": 0}

        def fake_monotonic() -> float:
            return clock["t"]

        def fake_sleep(_s: float) -> None:
            clock["t"] += poll_step
            calls["n"] += 1
            if calls["n"] >= stop_after:
                raise KeyboardInterrupt

        with mock.patch("friday.watcher.time.monotonic", side_effect=fake_monotonic), \
             mock.patch("friday.watcher.time.sleep", side_effect=fake_sleep), \
             mock.patch("friday.watcher.emit_event") as m:
            run_watcher(str(cfg), once=False, poll_s=0.01, heartbeat_s=heartbeat_s)
        return m

    def test_heartbeat_fires_inside_daemon_loop(self):
        """In daemon mode the loop emits daemon.alive on the interval; a
        KeyboardInterrupt (SIGINT) still stops it cleanly."""
        m = self._clock_loop(heartbeat_s=30, poll_step=40, stop_after=2)
        alive = [c for c in m.call_args_list if c.kwargs.get("primitive") == "daemon.alive"]
        self.assertTrue(alive, "no daemon.alive lines emitted in the loop")
        self.assertIn("STOP", [c.kwargs.get("result") for c in m.call_args_list])

    def test_heartbeat_respects_interval(self):
        """Regression: the first heartbeat must NOT fire immediately. The
        interval is measured from daemon start, not from boot - last_heartbeat
        was once initialized to 0.0 while time.monotonic() is boot-relative,
        which made the first check look overdue and fire an instant beat."""
        # checks at t=1000, 1020, 1040 - never 60s past start -> no beat
        m = self._clock_loop(heartbeat_s=60, poll_step=20, stop_after=3)
        alive = [c for c in m.call_args_list if c.kwargs.get("primitive") == "daemon.alive"]
        self.assertEqual(alive, [])

    def test_heartbeat_fires_once_interval_elapses(self):
        # started=1000; checks at 1000 (0), 1020 (20), 1040 (40 >= 30) -> one beat
        m = self._clock_loop(heartbeat_s=30, poll_step=20, stop_after=3)
        alive = [c for c in m.call_args_list if c.kwargs.get("primitive") == "daemon.alive"]
        self.assertEqual(len(alive), 1)
        self.assertEqual(alive[0].kwargs["args"]["uptime_s"], 40)

    def test_heartbeat_s_must_be_positive(self):
        with self.assertRaises(FridayError):
            run_watcher("/nonexistent.json", once=True, heartbeat_s=0)


class TestAllowList(EnvTestCase):
    """The optional per-trigger `allow` primitive allowlist: validated at
    load time, and a plan containing a disallowed primitive is REFUSED
    before execution - never acted on by an unattended trigger - recorded
    honestly, and popped from the plan cache."""

    def test_allow_must_be_a_list_of_strings(self):
        for bad in ("gmail.*", ["gmail.*", 3], [""], ["  "], 42, {"a": 1}):
            with self.assertRaises(FridayError, msg=f"allow={bad!r}"):
                f = self.mktmp() / "w.json"
                f.write_text(json.dumps({"triggers": [
                    {"id": "a", "goal": "g", "schedule": {"type": "time", "at": "09:00"}, "allow": bad}
                ]}), encoding="utf-8")
                load_config(f)

    def test_plan_with_disallowed_prim_is_refused_not_executed(self):
        d = self.mktmp()
        (d / "time").mkdir()
        tasks = d / "tasks.jsonl"
        gaps = d / "gaps.jsonl"
        self.set_env(FRIDAY_TASKS_FILE=str(tasks), FRIDAY_GAPS_FILE=str(gaps))
        # Regression (hermeticity leak fixed 2026-08-10): this refusal used to
        # write allow-x records into the REAL var/logs/capability_gaps.jsonl
        # (FRIDAY_GAPS_FILE was not isolated) - 5 leaked records, timestamps
        # matching this test's runs. Assert the temp file got them instead.
        # a plan that would SEND a message - must never run from this trigger
        plan = {"goal": "send something", "steps": [
            {"primitive": "whatsapp.send_text", "args": {"text": "hi", "to": "1"},
             "verify": {"check": "checks.message_sent",
                         "args": {"platform": "whatsapp", "message_id": "wamid.x"}, "expect": True}},
        ]}
        t = {"id": "allow-x", "goal": "send something",
             "schedule": {"type": "time", "at": "00:00"}, "notify": False,
             "allow": ["gmail.*"]}
        with mock.patch("friday.l4.planner.plan", return_value=plan) as m, \
             mock.patch("friday.watcher.run_plan") as run:
            cache: dict = {}
            ok, detail = _run_trigger(t, cache)
        self.assertFalse(ok)
        self.assertEqual(detail["status"], "REFUSED")
        self.assertEqual(detail["forbidden"], ["whatsapp.send_text"])
        run.assert_not_called()       # refused before any execution
        self.assertEqual(cache, {})   # refused plan popped, replanned next firing
        recs = [json.loads(l) for l in open(tasks, encoding="utf-8") if l.strip()]
        self.assertEqual(len(recs), 1)
        self.assertFalse(recs[0]["gate6_passed"])  # honest failure, never deleted
        self.assertEqual(json.loads(recs[0]["proof"])["status"], "REFUSED")
        # the refusal's gap record lands in the isolated temp file, never the real one
        from friday.capability_gaps import all_gaps

        leaked = [g for g in all_gaps() if g.get("trigger_id") == "allow-x"]
        self.assertEqual(len(leaked), 1)
        self.assertEqual(str(Path(os.environ["FRIDAY_GAPS_FILE"])), str(gaps))

    def test_allowed_exact_and_prefix_plan_executes(self):
        d = self.mktmp()
        (time_dir := d / "time").mkdir()
        (time_dir / "alpha.txt").write_text("x", encoding="utf-8")
        cfg = d / "w.json"
        cfg.write_text(json.dumps({"triggers": [
            {"id": "allow-ok", "plan": _plan(time_dir, "alpha"),
             "schedule": {"type": "time", "at": "00:00"}, "notify": False,
             "allow": ["files.*"]},
        ]}), encoding="utf-8")
        tasks = d / "tasks.jsonl"
        self.set_env(FRIDAY_TASKS_FILE=str(tasks))
        run_watcher(str(cfg), once=True)
        recs = [json.loads(l) for l in open(tasks, encoding="utf-8") if l.strip()]
        self.assertEqual(len(recs), 1)
        self.assertTrue(recs[0]["gate6_passed"])  # files.find_file matches files.*
        self.assertEqual(json.loads(recs[0]["proof"])["status"], "COMPLETED")


if __name__ == "__main__":
    unittest.main()
