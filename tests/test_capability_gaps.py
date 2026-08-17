"""Capability-gap records: an unknown/disallowed primitive produces exactly
one structured record; a successful step produces none; watcher allowlist
refusals record too; processed-tracking is idempotent; and arg shapes never
leak values. All gap files are redirected to temp paths (FRIDAY_GAPS_FILE)."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

from friday.capability_gaps import (
    all_gaps,
    group_by_primitive,
    mark_processed,
    record_gap,
    unprocessed_gaps,
)
from friday.errors import FridayError
from friday.l3.executor import run_plan
from friday.watcher import _run_trigger
from tests.helpers import EnvTestCase


def _plan_file(directory: Path, name: str) -> dict:
    """A hermetic find_file plan with fast failure timing."""
    return {
        "goal": "locate " + name,
        "steps": [
            {
                "primitive": "files.find_file",
                "args": {"name": name, "directory": str(directory)},
                "verify": {
                    "check": "checks.file_exists",
                    "args": {"path": "$steps.1.result.path"},
                    "expect": True,
                },
                "verify_wait_s": 0.1,
                "backoff_s": 0.05,
            }
        ],
    }


class TestExecutorGaps(EnvTestCase):
    def _gaps(self) -> list[dict]:
        return all_gaps()

    def test_unknown_primitive_produces_one_gap_record(self):
        """(a) An unknown/unregistered primitive -> exactly ONE gap record
        with the specified fields, then the plan ABORTs as before."""
        gaps = self.mktmp() / "gaps.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        plan = {
            "goal": "locate the missing artifact",
            "steps": [
                {
                    "primitive": "files.do_thing",
                    "args": {"name": "x", "recursive": False},
                    "verify": {"check": "checks.file_exists", "args": {}, "expect": True},
                    "verify_wait_s": 0.1,
                    "backoff_s": 0.05,
                }
            ],
        }
        with self.assertRaises(FridayError) as ctx:
            run_plan(plan)
        self.assertIn("plan aborted", str(ctx.exception))
        recs = self._gaps()
        self.assertEqual(len(recs), 1)
        g = recs[0]
        self.assertEqual(g["source"], "executor")
        self.assertEqual(g["goal_id"], "locate the missing artifact")
        self.assertEqual(g["attempted_primitive"], "files.do_thing")
        self.assertEqual(g["attempted_args_shape"], {"name": "str:1", "recursive": "bool"})
        self.assertEqual(g["goal_context"], "locate the missing artifact")
        self.assertIn("no registered contract", g["refusal_reason"])
        for key in ("gap_id", "timestamp"):
            self.assertTrue(g.get(key))

    def test_unknown_module_primitive_also_records(self):
        """A primitive whose MODULE does not exist is the same class of gap."""
        gaps = self.mktmp() / "gaps.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        plan = {
            "goal": "g",
            "steps": [
                {
                    "primitive": "bogus.do_thing",
                    "args": {},
                    "verify": {"check": "checks.file_exists", "args": {}, "expect": True},
                    "verify_wait_s": 0.1,
                    "backoff_s": 0.05,
                }
            ],
        }
        with self.assertRaises(FridayError):
            run_plan(plan)
        self.assertEqual(len(self._gaps()), 1)
        self.assertIn("cannot be imported", self._gaps()[0]["refusal_reason"])

    def test_blocked_by_design_primitive_records_gap(self):
        """EXECUTOR_BLOCKED (window.shutdown) is also recorded - honestly
        traceable; the triage human decides whether to dismiss it."""
        gaps = self.mktmp() / "gaps.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        plan = {
            "goal": "shut down",
            "steps": [
                {
                    "primitive": "window.shutdown",
                    "args": {},
                    "verify": {
                        "check": "checks.window_has_class",
                        "args": {"cls": "x"},
                        "expect": True,
                    },
                    "verify_wait_s": 0.1,
                    "backoff_s": 0.05,
                }
            ],
        }
        with self.assertRaises(FridayError):
            run_plan(plan)
        self.assertEqual(len(self._gaps()), 1)
        self.assertIn("EXECUTOR_BLOCKED", self._gaps()[0]["refusal_reason"])

    def test_successful_step_produces_no_gap(self):
        """(c) A normal successful run records nothing."""
        gaps = self.mktmp() / "gaps.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        d = self.mktmp()
        (d / "alpha.txt").write_text("x", encoding="utf-8")
        result = run_plan(_plan_file(d, "alpha"))
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(self._gaps(), [])

    def test_args_shape_never_leaks_values(self):
        """The recorded shape is type tags only - secrets never ride a gap."""
        gaps = self.mktmp() / "gaps.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        record_gap(
            source="executor",
            goal_id="g",
            attempted_primitive="x.send",
            attempted_args={
                "secret": "hunter2",
                "n": 5,
                "lst": [1, 2, 3],
                "flag": True,
                "none": None,
            },
            goal_context="send it",
            refusal_reason="r",
        )
        raw = gaps.read_text(encoding="utf-8")
        self.assertNotIn("hunter2", raw)
        g = all_gaps()[0]
        self.assertEqual(
            g["attempted_args_shape"],
            {
                "secret": "str:7",
                "n": "int",
                "lst": "list:3",
                "flag": "bool",
                "none": "none",
            },
        )


class TestWatcherGaps(EnvTestCase):
    def test_allowlist_refusal_produces_gap_record(self):
        """(b) A watcher allowlist refusal records a gap per forbidden
        primitive (source=watcher, trigger_id present)."""
        gaps = self.mktmp() / "gaps.jsonl"
        tasks = self.mktmp() / "tasks.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps), FRIDAY_TASKS_FILE=str(tasks))
        plan = {
            "goal": "send something",
            "steps": [
                {
                    "primitive": "whatsapp.send_text",
                    "args": {"text": "hi", "to": "1"},
                    "verify": {
                        "check": "checks.message_sent",
                        "args": {"platform": "whatsapp", "message_id": "wamid.x"},
                        "expect": True,
                    },
                },
            ],
        }
        t = {
            "id": "allow-x",
            "goal": "send something",
            "schedule": {"type": "time", "at": "00:00"},
            "notify": False,
            "allow": ["gmail.*"],
        }
        with mock.patch("friday.l4.planner.plan", return_value=plan):
            ok, detail = _run_trigger(t, {})
        self.assertFalse(ok)
        self.assertEqual(detail["status"], "REFUSED")
        recs = all_gaps()
        self.assertEqual(len(recs), 1)
        g = recs[0]
        self.assertEqual(g["source"], "watcher")
        self.assertEqual(g["trigger_id"], "allow-x")
        self.assertEqual(g["attempted_primitive"], "whatsapp.send_text")
        self.assertIn("allowlist", g["refusal_reason"])
        self.assertEqual(g["goal_context"], "send something")

    def test_allowlist_refusal_records_per_forbidden_primitive(self):
        gaps = self.mktmp() / "gaps.jsonl"
        tasks = self.mktmp() / "tasks.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps), FRIDAY_TASKS_FILE=str(tasks))
        plan = {
            "goal": "g",
            "steps": [
                {
                    "primitive": "whatsapp.send_text",
                    "args": {},
                    "verify": {"check": "checks.message_sent", "args": {}, "expect": True},
                },
                {
                    "primitive": "notify.notify_send",
                    "args": {},
                    "verify": {"check": "checks.message_sent", "args": {}, "expect": True},
                },
            ],
        }
        t = {
            "id": "a",
            "goal": "g",
            "schedule": {"type": "time", "at": "00:00"},
            "notify": False,
            "allow": ["gmail.*"],
        }
        with mock.patch("friday.l4.planner.plan", return_value=plan):
            _run_trigger(t, {})
        prims = sorted(g["attempted_primitive"] for g in all_gaps())
        self.assertEqual(prims, ["notify.notify_send", "whatsapp.send_text"])

    def test_passing_trigger_produces_no_gap(self):
        gaps = self.mktmp() / "gaps.jsonl"
        tasks = self.mktmp() / "tasks.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps), FRIDAY_TASKS_FILE=str(tasks))
        d = self.mktmp()
        (d / "alpha.txt").write_text("x", encoding="utf-8")
        t = {
            "id": "ok",
            "plan": _plan_file(d, "alpha"),
            "schedule": {"type": "time", "at": "00:00"},
            "notify": False,
        }
        ok, _ = _run_trigger(t, {})
        self.assertTrue(ok)
        self.assertEqual(all_gaps(), [])


class TestProcessing(EnvTestCase):
    def test_mark_processed_is_idempotent(self):
        gaps = self.mktmp() / "gaps.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        id1 = record_gap(
            source="executor",
            goal_id="g",
            attempted_primitive="a.b",
            goal_context="g",
            refusal_reason="r",
        )
        id2 = record_gap(
            source="watcher",
            trigger_id="t",
            attempted_primitive="c.d",
            goal_context="g",
            refusal_reason="r",
        )
        self.assertEqual(len(unprocessed_gaps()), 2)
        mark_processed([id1])
        mark_processed([id1])  # idempotent
        remaining = [g["gap_id"] for g in unprocessed_gaps()]
        self.assertEqual(remaining, [id2])

    def test_group_by_primitive_dedupes_preserving_order(self):
        a = {"gap_id": "1", "attempted_primitive": "x.y", "goal_context": "one"}
        b = {"gap_id": "2", "attempted_primitive": "x.y", "goal_context": "two"}
        c = {"gap_id": "3", "attempted_primitive": "p.q", "goal_context": "three"}
        groups = group_by_primitive([a, b, c])
        self.assertEqual(list(groups), ["x.y", "p.q"])
        self.assertEqual([g["goal_context"] for g in groups["x.y"]], ["one", "two"])

    def test_record_never_raises_on_unwritable_file(self):
        d = self.mktmp()
        self.set_env(FRIDAY_GAPS_FILE=str(d))  # a DIRECTORY - writes must fail silently
        record_gap(
            source="executor",
            goal_id="g",
            attempted_primitive="a.b",
            goal_context="g",
            refusal_reason="r",
        )
        self.assertEqual(all_gaps(), [])
