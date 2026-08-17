"""L0 observability: redaction, clipping, per-primitive log_transform,
size-based rotation, and the observe wrapper."""

from __future__ import annotations

import itertools
import json
import os
import unittest

from friday import observability as obs
from tests.helpers import EnvTestCase


class TestRedaction(EnvTestCase):
    def test_sensitive_keys_redacted(self):
        self.assertEqual(obs._redact("password", "x"), "<redacted>")
        self.assertEqual(obs._redact("access_token", "x"), "<redacted>")
        self.assertEqual(obs._redact("title", "x"), "x")  # benign key untouched

    def test_clip_redacts_nested_and_bounds(self):
        clipped = obs._clip(
            {"password": "s3cret", "ok": {"token": "t", "v": 1}, "list": list(range(30))}
        )
        self.assertEqual(clipped["password"], "<redacted>")
        self.assertEqual(clipped["ok"]["token"], "<redacted>")
        self.assertEqual(len(clipped["list"]), 20)

    def test_clip_truncates_long_strings_and_deep(self):
        s = obs._clip("x" * 600)
        self.assertTrue(s.endswith("...<+100 chars>"))
        deep = obs._clip({"a": {"b": {"c": {"d": "deep"}}}})
        self.assertEqual(deep["a"]["b"]["c"]["d"], "<too deep>")

    def test_bind_args_redacts_argument_named_password(self):
        def fn(a, password):
            pass

        bound = obs._bind_args(fn, (1,), {"password": "p"})
        self.assertEqual(bound["password"], "<redacted>")
        self.assertEqual(bound["a"], 1)


class TestRunIdLifecycle(EnvTestCase):
    """run_id scoping: a logical run owns its id, and reset_run_id()
    restores the process default so ambient lines (daemon.alive
    heartbeats) never inherit a finished run's id - the run_id leak."""

    def test_reset_restores_process_default(self):
        default_before = obs._run_id()
        obs.set_run_id("watch-morning-gmail-summary-20260814T090705")
        self.assertEqual(obs._run_id(), "watch-morning-gmail-summary-20260814T090705")
        obs.reset_run_id()
        self.assertEqual(obs._run_id(), default_before)

    def test_set_run_id_none_generates_fresh(self):
        before = obs._run_id()
        obs.set_run_id(None)
        self.assertNotEqual(obs._run_id(), before)
        self.assertEqual(len(obs._run_id()), 12)  # uuid4().hex[:12]

    def test_emitted_lines_use_reset_run_id(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))

        obs.set_run_id("watch-some-trigger-20260814T000000")
        obs.emit_event(layer="WATCH", primitive="trigger", result="DONE")
        obs.reset_run_id()
        obs.emit_event(layer="WATCH", primitive="daemon.alive", result="ALIVE")

        lines = [json.loads(l) for l in open(log, encoding="utf-8") if l.strip()]
        self.assertEqual(lines[0]["run_id"], "watch-some-trigger-20260814T000000")
        # The heartbeat line must NOT inherit the trigger's run_id.
        self.assertNotEqual(lines[1]["run_id"], "watch-some-trigger-20260814T000000")
        self.assertEqual(lines[1]["run_id"], obs._run_id())


class TestObserveWrapper(EnvTestCase):
    def _last_line(self, path) -> dict:
        lines = [l for l in open(path, encoding="utf-8") if l.strip()]
        return json.loads(lines[-1])

    def test_success_line_shape(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))

        @obs.observe()
        def fn(a, b=2):
            return {"r": a + b}

        fn(1)
        rec = self._last_line(log)
        self.assertEqual(rec["layer"], "L1")
        self.assertEqual(rec["primitive"], "test_observability.fn")
        # _bind_args logs only what was EXPLICITLY passed (defaults are not
        # bound into the record): b=2 is a default, so it does not appear.
        self.assertEqual(rec["args"], {"a": 1})
        self.assertEqual(rec["result"], {"r": 3})
        self.assertIsNone(rec["exception"])
        self.assertIn("run_id", rec)
        self.assertIn("duration_ms", rec)
        self.assertIn("timestamp", rec)

    def test_exception_line_and_reraises(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))

        @obs.observe()
        def boom():
            raise ValueError("kaboom")

        with self.assertRaises(ValueError):
            boom()
        rec = self._last_line(log)
        self.assertIsNone(rec["result"])
        self.assertIn("ValueError: kaboom", rec["exception"])

    def test_redact_result(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))

        @obs.observe(redact_result=True)
        def creds():
            return {"password": "p"}

        self.assertEqual(creds()["password"], "p")  # real return untouched
        self.assertEqual(self._last_line(log)["result"], "<redacted>")

    def test_log_transform_applied_to_log_only(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))

        @obs.observe(log_transform=lambda v: {"shrunk": len(v)})
        def fn(v):
            return v

        self.assertEqual(fn({"a": 1, "b": 2}), {"a": 1, "b": 2})
        self.assertEqual(self._last_line(log)["result"], {"shrunk": 2})

    def test_broken_log_transform_cannot_break_primitive(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))

        @obs.observe(log_transform=lambda v: 1 / 0)
        def fn(v):
            return v

        self.assertEqual(fn(42), 42)
        self.assertEqual(self._last_line(log)["result"], "<log_transform error>")

    def test_observability_disabled_writes_nothing(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log), FRIDAY_OBSERVABILITY="0")

        @obs.observe()
        def fn():
            return 1

        self.assertEqual(fn(), 1)
        self.assertFalse(log.exists())


class TestRotation(EnvTestCase):
    def _emit(self, path, n):
        self.set_env(FRIDAY_LOG_FILE=str(path))
        for i in range(n):
            obs.emit_event(layer="T", primitive="rot", args={"i": i}, result=i)

    def _vals(self, path):
        if not os.path.exists(path):
            return []
        return [json.loads(l)["args"]["i"] for l in open(path, encoding="utf-8") if l.strip()]

    def test_rotation_preserves_order_and_drops_oldest(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_MAX_BYTES="300", FRIDAY_LOG_BACKUPS="2")
        self._emit(log, 15)
        gens = [self._vals(f"{log}.2"), self._vals(f"{log}.1"), self._vals(log)]
        gens = [g for g in gens if g]
        # within a generation: sorted, unique; across generations: strictly newer
        for g in gens:
            self.assertEqual(g, sorted(g))
            self.assertEqual(len(g), len(set(g)))
        # each generation is entirely older than the next (works for
        # single-line generations too)
        for older, newer in itertools.pairwise(gens):
            self.assertLess(older[-1], newer[0])
        self.assertEqual(gens[-1][-1], 14)  # newest line present

    def test_rotation_config_clamps(self):
        self.set_env(FRIDAY_LOG_MAX_BYTES="0", FRIDAY_LOG_BACKUPS="-3")
        self.assertEqual(obs._log_rotation_config(), (1, 0))
        self.set_env(FRIDAY_LOG_MAX_BYTES="garbage", FRIDAY_LOG_BACKUPS="garbage")
        self.assertEqual(
            obs._log_rotation_config(), (obs.DEFAULT_LOG_MAX_BYTES, obs.DEFAULT_LOG_BACKUPS)
        )

    def test_backups_zero_disables_rotation(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_MAX_BYTES="100", FRIDAY_LOG_BACKUPS="0")
        self._emit(log, 5)
        self.assertFalse(os.path.exists(f"{log}.1"))
        self.assertEqual(len(self._vals(log)), 5)

    def test_rotation_output_valid_jsonl(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_MAX_BYTES="200", FRIDAY_LOG_BACKUPS="2")
        self._emit(log, 10)
        for p in (log, f"{log}.1", f"{log}.2"):
            if os.path.exists(p):
                for line in open(p, encoding="utf-8"):
                    if line.strip():
                        json.loads(line)


if __name__ == "__main__":
    unittest.main()
