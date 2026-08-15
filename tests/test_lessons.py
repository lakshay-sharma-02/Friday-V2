"""Lessons loop: event recording, candidate generalization, the approved
store, and bounded prompt injection (triage / planner / digest). All
lessons files are temp (FRIDAY_LESSONS_FILE / FRIDAY_APPROVED_LESSONS /
FRIDAY_PROPOSED_LESSONS_DIR); nothing ever touches the real
var/logs/lessons.jsonl, config/lessons.json, or gates/proposed_lessons/.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest import mock

from friday.lessons import (
    INJECT_LIMIT,
    MIN_EXAMPLES,
    all_events,
    approved_lessons,
    candidate_path,
    generalize,
    record_lesson_event,
    render_known_mistakes,
)
from tests.helpers import EnvTestCase

TRIAGE_LESSON = {
    "category": "draft_schema",
    "targets": ["triage"],
    "statement": "The contract name must be '<module>.<fn>'.",
}
DIGEST_LESSON = {
    "category": "digest_misattribution",
    "targets": ["digest"],
    "statement": "Never attribute a mechanism to a repo without it in that repo's own content.",
}


def _write_approved(lessons: list[dict]) -> None:
    path = Path(os.environ["FRIDAY_APPROVED_LESSONS"])
    path.write_text(json.dumps({"lessons": lessons}), encoding="utf-8")


class TestRecord(EnvTestCase):
    def test_record_writes_well_formed_event(self):
        eid = record_lesson_event(
            category="draft_schema", source="register_proposal",
            detail="demo.x: contract name must be '<module>.<fn>'", primitive="demo.x",
        )
        events = all_events()
        self.assertEqual(len(events), 1)
        e = events[0]
        self.assertEqual(e["event_id"], eid)
        self.assertEqual(e["category"], "draft_schema")
        self.assertEqual(e["source"], "register_proposal")
        self.assertEqual(e["primitive"], "demo.x")
        self.assertTrue(e["timestamp"])

    def test_detail_truncated(self):
        record_lesson_event(category="x", source="s", detail="z" * 2000)
        self.assertLessEqual(len(all_events()[0]["detail"]), 500)

    def test_malformed_lines_skipped_never_raised(self):
        path = Path(os.environ["FRIDAY_LESSONS_FILE"])
        path.write_text('{"category": "a"}\nnot json\n{"category": "b"}\n', encoding="utf-8")
        self.assertEqual([e["category"] for e in all_events()], ["a", "b"])

    def test_events_append_in_order(self):
        record_lesson_event(category="one", source="s", detail="d1")
        record_lesson_event(category="two", source="s", detail="d2")
        self.assertEqual([e["category"] for e in all_events()], ["one", "two"])


class TestApprovedStore(EnvTestCase):
    def test_no_file_means_no_lessons(self):
        self.assertEqual(approved_lessons(), [])
        self.assertEqual(render_known_mistakes("triage"), "")

    def test_valid_entries_load_and_render(self):
        _write_approved([TRIAGE_LESSON, DIGEST_LESSON])
        self.assertEqual(len(approved_lessons()), 2)
        block = render_known_mistakes("triage")
        self.assertIn("## KNOWN MISTAKES", block)
        self.assertIn("'<module>.<fn>'", block)
        # target filtering: the digest lesson must not leak into triage
        self.assertNotIn("Never attribute", block)
        self.assertIn("Never attribute", render_known_mistakes("digest"))

    def test_invalid_entries_excluded_fail_open(self):
        path = Path(os.environ["FRIDAY_APPROVED_LESSONS"])
        path.write_text(json.dumps({"lessons": [
            TRIAGE_LESSON,
            {"category": "draft_schema"},  # no statement
            {"category": "x", "statement": "s", "targets": ["nope"]},  # bad target
            {"statement": "s", "targets": ["triage"]},  # no category
        ]}), encoding="utf-8")
        self.assertEqual(len(approved_lessons()), 1)  # only the valid one
        block = render_known_mistakes("triage")
        self.assertIn("'<module>.<fn>'", block)
        self.assertNotIn("no statement", block)

    def test_malformed_store_is_fail_open(self):
        Path(os.environ["FRIDAY_APPROVED_LESSONS"]).write_text("not json", encoding="utf-8")
        self.assertEqual(approved_lessons(), [])
        self.assertEqual(render_known_mistakes("triage"), "")

    def test_invalid_utf8_store_is_fail_open(self):
        """Regression (review 2026-08-11): read_text raises
        UnicodeDecodeError - NOT OSError - on invalid UTF-8 bytes, and a
        single bad byte in the approved store must degrade to an empty
        block, never crash the planner/triage/digest prompts."""
        Path(os.environ["FRIDAY_APPROVED_LESSONS"]).write_bytes(b"\xff\xfe not utf8")
        self.assertEqual(approved_lessons(), [])
        self.assertEqual(render_known_mistakes("triage"), "")

    def test_injection_is_bounded(self):
        lessons = [dict(TRIAGE_LESSON, statement=f"lesson {i}") for i in range(20)]
        _write_approved(lessons)
        block = render_known_mistakes("triage")
        self.assertLessEqual(block.count("lesson "), INJECT_LIMIT)


class TestGeneralize(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.set_env(FRIDAY_PROPOSED_LESSONS_DIR=str(self.mktmp()))

    def test_below_min_examples_no_candidate(self):
        record_lesson_event(category="draft_schema", source="register_proposal", detail="one")
        self.assertEqual(generalize(), [])
        self.assertFalse(candidate_path("draft_schema").exists())

    def test_cluster_writes_candidate_with_evidence(self):
        for i in range(MIN_EXAMPLES):
            record_lesson_event(category="draft_schema", source="register_proposal", detail=f"reject {i}")
        written = generalize()
        self.assertEqual(len(written), 1)
        md = Path(written[0])
        text = md.read_text(encoding="utf-8")
        self.assertIn("STATUS: PROPOSED", text)
        self.assertIn("'<module>.<fn>'", text)  # the canonical statement
        self.assertIn("reject 0", text)
        self.assertIn("reject 1", text)
        self.assertIn("To approve", text)
        # sidecar tracks covered events
        sidecar = md.with_suffix(".events.json")
        data = json.loads(sidecar.read_text(encoding="utf-8"))
        self.assertEqual(len(data["event_ids"]), MIN_EXAMPLES)

    def test_idempotent_no_rewrite_for_covered_events(self):
        for _ in range(MIN_EXAMPLES):
            record_lesson_event(category="draft_schema", source="s", detail="d")
        generalize()
        written = generalize()  # no new events -> no candidate rewrite
        self.assertEqual(written, [])

    def test_new_evidence_extends_candidate(self):
        for _ in range(MIN_EXAMPLES):
            record_lesson_event(category="draft_schema", source="s", detail="old")
        generalize()
        record_lesson_event(category="draft_schema", source="s", detail="new evidence")
        written = generalize()
        self.assertEqual(len(written), 1)
        text = Path(written[0]).read_text(encoding="utf-8")
        self.assertIn("new evidence", text)
        self.assertIn("old", text)

    def test_unregistered_category_never_candidates(self):
        record_lesson_event(category="mystery_cat", source="s", detail="a")
        record_lesson_event(category="mystery_cat", source="s", detail="b")
        self.assertEqual(generalize(), [])
        self.assertFalse(candidate_path("mystery_cat").exists())

    def test_event_without_id_never_forces_rewrite(self):
        """Regression (review 2026-08-11): a parseable event missing
        event_id reads as forever-fresh (None is never in the covered set)
        and would rewrite the candidate on every run. It must be skipped
        like a malformed line."""
        import json as _json

        for _ in range(MIN_EXAMPLES):
            record_lesson_event(category="draft_schema", source="s", detail="d")
        generalize()
        # append a malformed-but-parseable event with no event_id
        path = Path(os.environ["FRIDAY_LESSONS_FILE"])
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(_json.dumps({"category": "draft_schema", "source": "s", "detail": "no id"}) + "\n")
        self.assertEqual(generalize(), [])  # no rewrite without fresh tracked events


class TestInjection(EnvTestCase):
    """The three prompt sites embed their own target's approved block."""

    def test_triage_prompt_includes_lessons(self):
        _write_approved([TRIAGE_LESSON])
        from friday.gap_triage import _build_prompt

        prompt = _build_prompt([{"gap_id": "1", "goal_context": "g"}])
        self.assertIn("## KNOWN MISTAKES", prompt)
        self.assertIn("'<module>.<fn>'", prompt)

    def test_triage_prompt_empty_without_lessons(self):
        from friday.gap_triage import _build_prompt

        prompt = _build_prompt([{"gap_id": "1", "goal_context": "g"}])
        self.assertNotIn("KNOWN MISTAKES", prompt)

    def test_planner_prompt_includes_lessons(self):
        _write_approved([{"category": "planner_schema", "targets": ["planner"],
                          "statement": "The plan must match the executor schema exactly."}])
        from friday.l4.planner import build_prompt

        prompt = build_prompt("do the thing")
        self.assertIn("## KNOWN MISTAKES", prompt)
        self.assertIn("executor schema exactly", prompt)

    def test_digest_task_includes_lessons(self):
        _write_approved([DIGEST_LESSON])
        from friday.l1 import dev

        with mock.patch.object(dev, "_run_claude", return_value={"result": "digest text"}) as m:
            dev.digest({"friday": "git log one", "vivaha": "retheme"})
        task = m.call_args[0][0]
        self.assertIn("## KNOWN MISTAKES", task)
        self.assertIn("Never attribute", task)


class TestRecordSites(EnvTestCase):
    """The real record sites: the approval gate, the automated gate, the
    digest attribution check, and the planner's retry loop each write a
    lesson event on their failure path."""

    def setUp(self):
        super().setUp()
        self.set_env(FRIDAY_L1_DIR=str(self.mktmp()), FRIDAY_PROPOSALS_DIR=str(self.mktmp()))

    def _proposal(self, contract_name: str = "demo.new_prim",
                  impl: str = (
                      "from friday.contracts import Idempotency, contract\n"
                      "@contract(precondition=\"p\", postcondition=\"q\",\n"
                      "          idempotency=Idempotency.IDEMPOTENT, failure_mode=\"f\", returns=\"bool\")\n"
                      "def new_prim() -> bool:\n"
                      "    return True\n"
                  )) -> Path:
        d = Path(os.environ["FRIDAY_PROPOSALS_DIR"]) / "demo.new_prim"
        d.mkdir(parents=True)
        (d / "contract.json").write_text(json.dumps({
            "name": contract_name, "precondition": "p", "postcondition": "q",
            "idempotency": "idempotent", "failure_mode": "f", "returns": "bool",
        }), encoding="utf-8")
        (d / "impl.py").write_text(impl, encoding="utf-8")
        (d / "test.py").write_text(
            "import unittest\nfrom friday.l1.demo import new_prim\n"
            "class T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(new_prim())\n",
            encoding="utf-8",
        )
        return d

    def test_schema_rejection_records_draft_schema(self):
        from friday.register_proposal import approve_and_register

        d = self._proposal(contract_name="a.b.c")  # three dots - schema reject
        ok, _ = approve_and_register(d)
        self.assertFalse(ok)
        cats = [e["category"] for e in all_events()]
        self.assertEqual(cats, ["draft_schema"])
        self.assertEqual(all_events()[0]["primitive"], "a.b.c")

    def test_gate_rejection_records_draft_ast(self):
        from friday.register_proposal import approve_and_register

        d = self._proposal(impl="import subprocess\n\ndef new_prim() -> bool:\n    return subprocess.run(['true']).returncode == 0\n")
        (d / "APPROVED.md").write_text("APPROVED\n", encoding="utf-8")
        ok, _ = approve_and_register(d)
        self.assertFalse(ok)
        cats = [e["category"] for e in all_events()]
        self.assertEqual(cats, ["draft_ast"])

    def test_clean_proposal_records_nothing(self):
        from friday.register_proposal import approve_and_register

        d = self._proposal()
        (d / "APPROVED.md").write_text("APPROVED\n", encoding="utf-8")
        ok, msg = approve_and_register(d)
        self.assertTrue(ok, msg)
        self.assertEqual(all_events(), [])

    def test_digest_misattribution_records_event(self):
        from friday.l1.digestcheck import verify_attribution

        ctx = {"friday": "gmail watcher tests", "vivaha": "cloudflare worker queue"}
        digest = "Use Friday's cloudflare worker pattern for moderation."
        out = verify_attribution(digest, ctx)
        self.assertIn("UNVERIFIED", out)
        cats = [e["category"] for e in all_events()]
        self.assertEqual(cats, ["digest_misattribution"])
        self.assertIn("cloudflare", all_events()[0]["detail"])

    def test_planner_schema_failure_records_lesson(self):
        from friday.l4.planner import plan

        # an unparseable plan -> planner_unparseable; then a schema-invalid
        # plan -> planner_schema (both recorded per attempt)
        env = {"result": "not json at all", "is_error": False}
        with mock.patch("friday.l1.dev.run", return_value=env):
            with self.assertRaises(Exception):
                plan("do the thing", attempts=1)
        self.assertEqual([e["category"] for e in all_events()], ["planner_unparseable"])
