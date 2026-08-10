"""gap_triage: JSON extraction, LLM drafting (mocked), artifact writing
with honest compile status, and idempotent processed-tracking. All gap
files are temp (FRIDAY_GAPS_FILE); the LLM is always mocked."""

from __future__ import annotations

import json
from unittest import mock

from friday.capability_gaps import record_gap, unprocessed_gaps
from friday.gap_triage import (
    _compiles,
    _extract_json,
    draft_one,
    proposal_dir,
    triage,
    write_proposal,
)
from tests.helpers import EnvTestCase

DRAFT = {
    "contract": {"name": "files.do_thing", "precondition": "p", "postcondition": "q",
                 "idempotency": "idempotent", "failure_mode": "f", "returns": "bool"},
    "impl": "def do_thing() -> bool:\n    \"\"\"Do the thing.\"\"\"\n    return True\n",
    "test": "import unittest\n\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
    "rationale": "Driven by: a real refused goal.",
}


class TestExtractJson(EnvTestCase):
    def test_plain_json(self):
        self.assertEqual(_extract_json('{"a": 1}'), {"a": 1})

    def test_markdown_fenced_json(self):
        self.assertEqual(_extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_prose_then_object(self):
        self.assertEqual(_extract_json('Here you go: {"a": {"b": 2}}'), {"a": {"b": 2}})

    def test_garbage_returns_none(self):
        self.assertIsNone(_extract_json("no json here"))
        self.assertIsNone(_extract_json(""))


class TestDraftOne(EnvTestCase):
    RECS = [{"gap_id": "1", "source": "executor", "attempted_primitive": "files.do_thing",
             "goal_context": "locate the missing thing", "refusal_reason": "no registered contract"}]

    def test_parses_llm_result(self):
        with mock.patch("friday.l1.dev._run_claude",
                        return_value={"result": json.dumps(DRAFT)}) as m:
            draft = draft_one(self.RECS)
        m.assert_called_once()
        self.assertEqual(draft["contract"]["name"], "files.do_thing")
        self.assertIn("def do_thing", draft["impl"])

    def test_retries_once_then_succeeds(self):
        side = [{"result": "not json at all"},
                {"result": json.dumps(DRAFT)}]
        with mock.patch("friday.l1.dev._run_claude", side_effect=side) as m:
            draft = draft_one(self.RECS)
        self.assertEqual(m.call_count, 2)
        self.assertEqual(draft["contract"]["idempotency"], "idempotent")

    def test_persistent_failure_returns_none(self):
        with mock.patch("friday.l1.dev._run_claude",
                        return_value={"result": "still not json"}) as m:
            self.assertIsNone(draft_one(self.RECS))
        self.assertEqual(m.call_count, 2)  # bounded retries, then None

    def test_llm_call_exception_leaves_group_unprocessed(self):
        """A dead claude CLI must not kill the whole triage run - the group
        stays unprocessed for the next run."""
        with mock.patch("friday.l1.dev._run_claude",
                        side_effect=RuntimeError("claude CLI down")) as m:
            self.assertIsNone(draft_one(self.RECS))
        self.assertEqual(m.call_count, 2)  # both attempts tried, then None


class TestTriage(EnvTestCase):
    def setUp(self):
        super().setUp()
        # never write drafts into the real gates/proposed_primitives/
        self.set_env(FRIDAY_PROPOSALS_DIR=str(self.mktmp()))

    def _seed_gap(self, gaps) -> None:
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        record_gap(source="executor", goal_id="locate the missing thing",
                   attempted_primitive="files.do_thing", attempted_args={"name": "x"},
                   goal_context="locate the missing thing", refusal_reason="no registered contract")

    def test_writes_artifacts_marks_processed_and_is_idempotent(self):
        gaps = self.mktmp() / "gaps.jsonl"
        self._seed_gap(gaps)
        with mock.patch("friday.l1.dev._run_claude",
                        return_value={"result": json.dumps(DRAFT)}) as m:
            written = triage()
        self.assertEqual(len(written), 1)
        d = proposal_dir("files.do_thing")
        for artifact in ("contract.json", "impl.py", "test.py", "rationale.md"):
            self.assertTrue((d / artifact).is_file(), artifact)
        rationale = (d / "rationale.md").read_text(encoding="utf-8")
        self.assertIn("APPROVAL: PENDING", rationale)
        self.assertIn("impl compiles: yes", rationale)
        self.assertIn("Driven by: a real refused goal.", rationale)
        self.assertEqual(unprocessed_gaps(), [])  # consumed
        # second run: no LLM call, nothing rewritten
        with mock.patch("friday.l1.dev._run_claude") as m:
            triage()
        m.assert_not_called()

    def test_llm_failure_leaves_group_unprocessed(self):
        gaps = self.mktmp() / "gaps.jsonl"
        self._seed_gap(gaps)
        with mock.patch("friday.l1.dev._run_claude", return_value={"result": "garbage"}):
            triage()
        self.assertFalse(proposal_dir("files.do_thing").exists())
        self.assertEqual(len(unprocessed_gaps()), 1)  # re-offered next run

    def test_compile_failure_reported_honestly(self):
        bad = dict(DRAFT, impl="def broken(:\n")
        recs = [{"gap_id": "1"}]
        d = write_proposal("x.broken", recs, bad)
        self.assertIn("impl compiles: no", (d / "rationale.md").read_text(encoding="utf-8"))
        self.assertIn("test compiles: yes", (d / "rationale.md").read_text(encoding="utf-8"))


class TestHelpers(EnvTestCase):
    def test_proposal_dir_sanitizes(self):
        self.set_env(FRIDAY_PROPOSALS_DIR=str(self.mktmp()))
        self.assertEqual(proposal_dir("files.do_thing").name, "files.do_thing")
        self.assertEqual(proposal_dir("a/b:c").name, "a_b_c")

    def test_compiles_does_not_execute(self):
        self.assertTrue(_compiles("x = 1\n"))
        self.assertFalse(_compiles("def broken(:\n"))
