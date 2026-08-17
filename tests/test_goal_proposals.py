"""goal_proposals: mining recurring FAILED goals from tasks.jsonl + L0 into
inert, watcher-validated trigger proposals. Everything is hermetic -
tasks/L0/config/proposal dirs are all temp (FRIDAY_TASKS_FILE /
FRIDAY_LOG_FILE / FRIDAY_WATCHER_CONFIG / FRIDAY_PROPOSED_TRIGGERS_DIR);
nothing ever touches the real config/watcher.json.
"""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest import mock

from friday.goal_proposals import (
    _draft_trigger,
    _goal_covered,
    _normalize_goal,
    l0_failure_summary,
    mine,
    propose,
    read_l0_failures,
    read_tasks,
)
from tests.helpers import EnvTestCase

GOAL_A = "find the most recent unread email from accounts.google.com and summarize it"
GOAL_B = "pause whatever's playing, then close every window except my terminal"


def _ts(days_ago: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days_ago)).isoformat()


class TestRead(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.set_env(
            FRIDAY_TASKS_FILE=str(self.mktmp() / "tasks.jsonl"),
            FRIDAY_LOG_FILE=str(self.mktmp() / "log.jsonl"),
            FRIDAY_WATCHER_CONFIG=str(self.mktmp() / "watcher.json"),
            FRIDAY_PROPOSED_TRIGGERS_DIR=str(self.mktmp() / "proposals"),
        )

    def test_malformed_lines_skipped(self):
        Path(os.environ["FRIDAY_TASKS_FILE"]).write_text(
            '{"task_id": "a", "goal": "g"}\nnot json\n{"task_id": "b"}\n', encoding="utf-8"
        )
        self.assertEqual([r["task_id"] for r in read_tasks()], ["a", "b"])

    def test_l0_only_failures(self):
        Path(os.environ["FRIDAY_LOG_FILE"]).write_text(
            '{"result": "FAILED", "layer": "L3", "primitive": "step.1", "exception": "x"}\n'
            '{"result": "ABORT", "layer": "L3", "primitive": "plan"}\n'
            '{"result": "VERIFIED", "layer": "L3", "primitive": "step.1"}\n',
            encoding="utf-8",
        )
        fails = read_l0_failures()
        self.assertEqual(len(fails), 2)
        self.assertEqual([f["result"] for f in fails], ["FAILED", "ABORT"])


class TestMine(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.set_env(
            FRIDAY_TASKS_FILE=str(self.mktmp() / "tasks.jsonl"),
            FRIDAY_LOG_FILE=str(self.mktmp() / "log.jsonl"),
            FRIDAY_WATCHER_CONFIG=str(self.mktmp() / "watcher.json"),
            FRIDAY_PROPOSED_TRIGGERS_DIR=str(self.mktmp() / "proposals"),
        )

    def _seed(self, records: list[dict]) -> None:
        path = Path(os.environ["FRIDAY_TASKS_FILE"])
        with open(path, "a", encoding="utf-8") as fh:
            for r in records:
                fh.write(json.dumps(r) + "\n")

    def _rec(
        self,
        goal: str,
        *,
        days_ago: int = 1,
        passed: bool = False,
        task_id: str = "proof-run",
        refused: bool = False,
    ) -> dict:
        return {
            "task_id": task_id,
            "goal": goal,
            "gate6_passed": passed,
            "timestamp": _ts(days_ago),
            "proof": json.dumps({"status": "REFUSED"})
            if refused
            else json.dumps({"status": "ABORT"}),
        }

    def test_clusters_recurring_failed_goals(self):
        self._seed(
            [
                self._rec(GOAL_A),
                self._rec(GOAL_A, days_ago=2),
                self._rec(GOAL_A, days_ago=3),
                self._rec(GOAL_B),  # only 1 -> below threshold
                self._rec(GOAL_A, passed=True),  # success is not a failure
            ]
        )
        clusters = mine()
        self.assertEqual(len(clusters), 1)
        c = clusters[0]
        self.assertEqual(c["goal"], GOAL_A)
        self.assertEqual(c["occurrences"], 3)
        self.assertEqual(len(c["task_ids"]), 3)

    def test_refused_and_probe_records_excluded(self):
        self._seed(
            [
                self._rec(GOAL_A, refused=True),  # deliberate REFUSED, not a failure
                self._rec(GOAL_A, task_id="watch:ambient-gap-probe-calendar"),
                self._rec(GOAL_B, task_id="watch:ambient-gap-probe-email-send"),
            ]
        )
        self.assertEqual(mine(), [])

    def test_window_filters_old_failures(self):
        self._seed(
            [
                self._rec(GOAL_A, days_ago=1),
                self._rec(GOAL_A, days_ago=30),  # outside a 7-day window
            ]
        )
        self.assertEqual(len(mine(days=7)), 0)
        self.assertEqual(len(mine(days=0)), 1)  # no window = all

    def test_covered_by_existing_trigger_skipped(self):
        """The real dedupe shape: the gmail-summary failures are covered by
        the enabled morning-gmail-summary trigger even though the sender
        text differs (accounts.google.com vs $facts.gmail_sender)."""
        config = Path(os.environ["FRIDAY_WATCHER_CONFIG"])
        config.write_text(
            json.dumps(
                {
                    "triggers": [
                        {
                            "id": "morning-gmail-summary",
                            "goal": "find the most recent unread email from $facts.gmail_sender and summarize it in at most 5 plain sentences",
                            "schedule": {
                                "type": "time",
                                "at": "09:00",
                                "days": ["mon", "tue", "wed", "thu", "fri"],
                            },
                            "enabled": True,
                            "allow": ["gmail.*"],
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self._seed([self._rec(GOAL_A), self._rec(GOAL_A, days_ago=2)])
        self.assertEqual(mine(), [])

    def test_not_covered_by_unrelated_trigger(self):
        config = Path(os.environ["FRIDAY_WATCHER_CONFIG"])
        config.write_text(
            json.dumps(
                {
                    "triggers": [
                        {
                            "id": "morning-gmail-summary",
                            "goal": "find the most recent unread email from $facts.gmail_sender and summarize it in at most 5 plain sentences",
                            "schedule": {"type": "time", "at": "09:00"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        self._seed([self._rec(GOAL_B), self._rec(GOAL_B, days_ago=2)])
        clusters = mine()
        self.assertEqual(len(clusters), 1)
        self.assertEqual(clusters[0]["goal"], GOAL_B)

    def test_sorted_by_occurrences(self):
        self._seed(
            [
                self._rec(GOAL_B),
                self._rec(GOAL_B, days_ago=2),
                self._rec(GOAL_B, days_ago=3),
                self._rec(GOAL_A),
                self._rec(GOAL_A, days_ago=2),
            ]
        )
        clusters = mine()
        self.assertEqual([c["goal"] for c in clusters], [GOAL_B, GOAL_A])

    def test_watch_l0_evidence_attached(self):
        Path(os.environ["FRIDAY_LOG_FILE"]).write_text(
            json.dumps(
                {
                    "layer": "WATCH",
                    "primitive": "trigger",
                    "result": "FAILED",
                    "args": {"id": "x", "goal": GOAL_B},
                    "extra": {"status": "ABORT"},
                }
            )
            + "\n",
            encoding="utf-8",
        )
        self._seed([self._rec(GOAL_B), self._rec(GOAL_B, days_ago=2)])
        c = mine()[0]
        self.assertEqual(len(c["l0_evidence"]), 1)


class TestDraft(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.set_env(
            FRIDAY_TASKS_FILE=str(self.mktmp() / "tasks.jsonl"),
            FRIDAY_LOG_FILE=str(self.mktmp() / "log.jsonl"),
            FRIDAY_WATCHER_CONFIG=str(self.mktmp() / "watcher.json"),
            FRIDAY_PROPOSED_TRIGGERS_DIR=str(self.mktmp() / "proposals"),
        )

    def _cluster(self) -> dict:
        return {
            "goal": GOAL_B,
            "occurrences": 2,
            "task_ids": ["a", "b"],
            "timestamps": [_ts(1), _ts(2)],
            "last_failed_at": _ts(1),
            "l0_evidence": [],
        }

    def test_deterministic_draft_is_inert_and_valid(self):
        t = _draft_trigger(self._cluster())
        self.assertEqual(t["goal"], GOAL_B)  # verbatim, never rewritten
        self.assertFalse(t["enabled"])  # inert until a human approves
        self.assertEqual(t["allow"], [])  # nothing may run until granted
        self.assertEqual(t["schedule"]["type"], "time")
        # validates through the real watcher schema
        from friday.watcher import _validate_trigger

        _validate_trigger(t, set())

    def test_verbatim_goal_survives_llm_path(self):
        with mock.patch(
            "friday.l1.dev._run_claude",
            return_value={
                "result": json.dumps(
                    {
                        "id": "pause-close",
                        "schedule": {"type": "time", "at": "18:30", "days": ["mon"]},
                        "allow": ["media.*", "window.*"],
                        "rationale_note": "keep the desktop clean nightly",
                    }
                )
            },
        ):
            t = _draft_trigger(self._cluster(), use_llm=True)
        self.assertEqual(t["goal"], GOAL_B)  # the goal is quoted evidence
        self.assertEqual(t["schedule"]["at"], "18:30")
        self.assertEqual(t["allow"], ["media.*", "window.*"])
        self.assertFalse(t["enabled"])

    def test_llm_garbage_falls_back_deterministic(self):
        with mock.patch("friday.l1.dev._run_claude", return_value={"result": "not json"}):
            t = _draft_trigger(self._cluster(), use_llm=True)
        self.assertEqual(t["allow"], [])
        self.assertEqual(t["schedule"]["at"], "09:00")
        self.assertFalse(t["enabled"])

    def test_llm_non_time_schedule_falls_back(self):
        with mock.patch(
            "friday.l1.dev._run_claude",
            return_value={
                "result": json.dumps(
                    {"id": "x", "schedule": {"type": "file", "directory": "/tmp"}, "allow": []}
                )
            },
        ):
            t = _draft_trigger(self._cluster(), use_llm=True)
        self.assertEqual(t["schedule"]["type"], "time")

    def test_unique_id_avoids_existing_trigger_ids(self):
        config = Path(os.environ["FRIDAY_WATCHER_CONFIG"])
        config.write_text(
            json.dumps(
                {
                    "triggers": [
                        {
                            "id": "pause-whatever",
                            "goal": "unrelated thing",
                            "schedule": {"type": "time", "at": "09:00"},
                        }
                    ]
                }
            ),
            encoding="utf-8",
        )
        t = _draft_trigger(self._cluster(), taken_ids={"pause-whatever"})
        self.assertNotEqual(t["id"], "pause-whatever")


class TestPropose(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.set_env(
            FRIDAY_TASKS_FILE=str(self.mktmp() / "tasks.jsonl"),
            FRIDAY_LOG_FILE=str(self.mktmp() / "log.jsonl"),
            FRIDAY_WATCHER_CONFIG=str(self.mktmp() / "watcher.json"),
            FRIDAY_PROPOSED_TRIGGERS_DIR=str(self.mktmp() / "proposals"),
        )
        # seed two recurring failures of the same goal
        path = Path(os.environ["FRIDAY_TASKS_FILE"])
        with open(path, "a", encoding="utf-8") as fh:
            for ago in (1, 2):
                fh.write(
                    json.dumps(
                        {
                            "task_id": f"run-{ago}",
                            "goal": GOAL_B,
                            "gate6_passed": False,
                            "timestamp": _ts(ago),
                            "proof": json.dumps({"status": "ABORT"}),
                        }
                    )
                    + "\n"
                )

    def _config_text(self) -> str:
        p = Path(os.environ["FRIDAY_WATCHER_CONFIG"])
        return p.read_text(encoding="utf-8") if p.is_file() else ""

    def test_writes_inert_proposal_and_rationale(self):
        written = propose()
        self.assertEqual(len(written), 1)
        d = Path(written[0])
        trigger = json.loads((d / "trigger.json").read_text(encoding="utf-8"))
        self.assertFalse(trigger["enabled"])
        self.assertEqual(trigger["goal"], GOAL_B)
        rationale = (d / "rationale.md").read_text(encoding="utf-8")
        self.assertIn("WARNING: this goal has FAILED 2 time(s)", rationale)
        self.assertIn(GOAL_B, rationale)
        self.assertIn("To approve", rationale)
        self.assertIn('"enabled": false', rationale)

    def test_proposal_validates_through_watcher_loader(self):
        from friday.watcher import load_config

        written = propose()
        d = Path(written[0])
        trigger = json.loads((d / "trigger.json").read_text(encoding="utf-8"))
        # a config carrying this trigger must load cleanly (plus a dummy
        # field-free second trigger is not needed - the one trigger suffices)
        tmp = self.mktmp() / "merged.json"
        tmp.write_text(json.dumps({"triggers": [trigger]}), encoding="utf-8")
        loaded = load_config(tmp)
        self.assertEqual(len(loaded), 1)
        self.assertFalse(loaded[0]["enabled"])

    def test_idempotent_never_reproposes(self):
        propose()
        self.assertEqual(propose(), [])

    def test_dry_run_writes_nothing(self):
        with mock.patch("friday.l1.dev._run_claude") as m:
            written = propose(dry_run=True)
        self.assertEqual(len(written), 1)
        self.assertFalse(Path(os.environ["FRIDAY_PROPOSED_TRIGGERS_DIR"]).exists())
        m.assert_not_called()

    def test_never_touches_watcher_config(self):
        before = self._config_text()
        propose()
        self.assertEqual(self._config_text(), before)  # config byte-identical

    def test_llm_draft_note_stays_out_of_trigger_json(self):
        """Regression (review 2026-08-11): the artifact a human copies into
        config must be clean - the LLM's rationale note is documentation
        (rationale.md only), never a watcher field in trigger.json."""
        with mock.patch(
            "friday.l1.dev._run_claude",
            return_value={
                "result": json.dumps(
                    {
                        "id": "pause-close",
                        "schedule": {"type": "time", "at": "18:30", "days": ["mon"]},
                        "allow": ["media.*", "window.*"],
                        "rationale_note": "keep the desktop clean nightly",
                    }
                )
            },
        ):
            written = propose(use_llm=True)
        d = Path(written[0])
        trigger = json.loads((d / "trigger.json").read_text(encoding="utf-8"))
        self.assertNotIn("_draft_note", trigger)
        self.assertFalse(any(k.startswith("_") for k in trigger))  # no private fields on disk
        self.assertIn(
            "keep the desktop clean nightly", (d / "rationale.md").read_text(encoding="utf-8")
        )

    def test_existing_proposal_dir_covered(self):
        propose()
        written = propose()
        self.assertEqual(written, [])
        # and a NEW different goal still proposes
        path = Path(os.environ["FRIDAY_TASKS_FILE"])
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(
                json.dumps(
                    {
                        "task_id": "z",
                        "goal": "send a daily standup note to my whatsapp",
                        "gate6_passed": False,
                        "timestamp": _ts(1),
                        "proof": json.dumps({"status": "ABORT"}),
                    }
                )
                + "\n"
            )
            fh.write(
                json.dumps(
                    {
                        "task_id": "z2",
                        "goal": "send a daily standup note to my whatsapp",
                        "gate6_passed": False,
                        "timestamp": _ts(2),
                        "proof": json.dumps({"status": "ABORT"}),
                    }
                )
                + "\n"
            )
        self.assertEqual(len(propose()), 1)


class TestSummary(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.set_env(FRIDAY_LOG_FILE=str(self.mktmp() / "log.jsonl"))

    def test_top_signatures(self):
        Path(os.environ["FRIDAY_LOG_FILE"]).write_text(
            '{"result": "FAILED", "layer": "L3", "primitive": "step.1", "exception": "PreconditionError: x"}\n'
            * 3
            + '{"result": "ABORT", "layer": "L4", "primitive": "plan", "exception": "no valid plan"}\n',
            encoding="utf-8",
        )
        top = l0_failure_summary()
        self.assertEqual(top[0]["count"], 3)
        self.assertEqual(top[0]["primitive"], "step.1")


class TestHelpers(EnvTestCase):
    def test_normalize_goal(self):
        self.assertEqual(_normalize_goal("  Find   the FILE! "), "find the file")

    def test_goal_covered_substring_and_token_overlap(self):
        triggers = [
            {
                "goal": "find the most recent unread email from $facts.gmail_sender and summarize it in at most 5 plain sentences"
            }
        ]
        # substring containment
        self.assertTrue(_goal_covered("summarize it in at most 5 plain sentences", triggers))
        # token overlap despite different sender text (the real gmail case)
        self.assertTrue(_goal_covered(GOAL_A, triggers))
        # unrelated goal is NOT covered
        self.assertFalse(_goal_covered(GOAL_B, triggers))
