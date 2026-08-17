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
    _normalize_contract_name,
    _self_check,
    draft_one,
    proposal_dir,
    triage,
    write_proposal,
)
from tests.helpers import EnvTestCase

# The real L1 convention (2026-08-14): a draft impl MUST carry the @contract
# decorator - the gate and the triage self-check both reject an undecorated
# impl (it would never enter REGISTRY). Every fixture models that convention.
CONTRACT_PREFIX = (
    "from friday.contracts import Idempotency, contract\n"
    '@contract(precondition="p", postcondition="q",\n'
    '          idempotency=Idempotency.IDEMPOTENT, failure_mode="f", returns="bool")\n'
)

DRAFT = {
    "contract": {
        "name": "files.do_thing",
        "precondition": "p",
        "postcondition": "q",
        "idempotency": "idempotent",
        "failure_mode": "f",
        "returns": "bool",
    },
    "impl": CONTRACT_PREFIX + 'def do_thing() -> bool:\n    """Do the thing."""\n    return True\n',
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
    RECS = [
        {
            "gap_id": "1",
            "source": "executor",
            "attempted_primitive": "files.do_thing",
            "goal_context": "locate the missing thing",
            "refusal_reason": "no registered contract",
        }
    ]

    def test_parses_llm_result(self):
        with mock.patch(
            "friday.l1.dev._run_claude", return_value={"result": json.dumps(DRAFT)}
        ) as m:
            draft, reason = draft_one(self.RECS)
        m.assert_called_once()
        self.assertEqual(draft["contract"]["name"], "files.do_thing")
        self.assertIn("def do_thing", draft["impl"])
        self.assertEqual(reason, "")

    def test_retries_once_then_succeeds(self):
        side = [{"result": "not json at all"}, {"result": json.dumps(DRAFT)}]
        with mock.patch("friday.l1.dev._run_claude", side_effect=side) as m:
            draft, _reason = draft_one(self.RECS)
        self.assertEqual(m.call_count, 2)
        self.assertEqual(draft["contract"]["idempotency"], "idempotent")

    def test_persistent_failure_returns_none(self):
        with mock.patch(
            "friday.l1.dev._run_claude", return_value={"result": "still not json"}
        ) as m:
            draft, reason = draft_one(self.RECS)
        self.assertIsNone(draft)
        self.assertIn("unparseable JSON", reason)  # the failure is DIAGNOSABLE
        self.assertEqual(m.call_count, 3)  # bounded retries, then None

    def test_llm_call_exception_leaves_group_unprocessed(self):
        """A dead claude CLI must not kill the whole triage run - the group
        stays unprocessed for the next run."""
        with mock.patch(
            "friday.l1.dev._run_claude", side_effect=RuntimeError("claude CLI down")
        ) as m:
            draft, reason = draft_one(self.RECS)
        self.assertIsNone(draft)
        self.assertIn("LLM call failed", reason)
        self.assertEqual(m.call_count, 3)  # all bounded attempts tried, then None

    def test_model_override_env_flows_through(self):
        """FRIDAY_TRIAGE_MODEL (a full model id) overrides the opus alias -
        the escape hatch when the default alias' provider is DEGRADED
        (observed live 2026-08-13). Default stays MODEL_ALIAS."""
        self.set_env(FRIDAY_TRIAGE_MODEL="oc/laguna-s-2.1-free")
        with mock.patch(
            "friday.l1.dev._run_claude", return_value={"result": json.dumps(DRAFT)}
        ) as m:
            draft, _reason = draft_one(self.RECS)
        self.assertIsNotNone(draft)
        # _run_claude(task, cwd, timeout_s, model, bypass)
        self.assertEqual(m.call_args.args[3], "oc/laguna-s-2.1-free")

    def test_model_defaults_to_alias_without_env(self):
        with mock.patch(
            "friday.l1.dev._run_claude", return_value={"result": json.dumps(DRAFT)}
        ) as m:
            draft, _reason = draft_one(self.RECS)
        self.assertIsNotNone(draft)
        self.assertEqual(m.call_args.args[3], "opus")

    # ---- model fallback chain (2026-08-14) ---------------------------

    def test_timeout_advances_to_fallback_model(self):
        """A PrimitiveTimeout on the primary model advances to the
        fallback for the next attempt - the cycle-2 failure (laguna-s too
        slow for the new-module draft shape) handled automatically instead
        of burning every attempt on a model that can't finish."""
        from friday.errors import PrimitiveTimeout

        self.set_env(FRIDAY_TRIAGE_FALLBACK_MODELS="oc/laguna-xs")
        side = [
            PrimitiveTimeout("claude -p did not finish within 300s", state="t"),
            {"result": json.dumps(DRAFT)},
        ]
        with mock.patch("friday.l1.dev._run_claude", side_effect=side) as m:
            draft, _reason = draft_one(self.RECS)
        self.assertIsNotNone(draft)
        self.assertEqual(m.call_count, 2)
        self.assertEqual(m.call_args_list[0].args[3], "opus")  # primary
        self.assertEqual(m.call_args_list[1].args[3], "oc/laguna-xs")  # fallback

    def test_hard_failure_advances_to_fallback_model(self):
        """The DEGRADED-provider case (claude rc=1, empty stderr): a
        PrimitiveError on the primary advances to the fallback."""
        from friday.errors import PrimitiveError

        self.set_env(FRIDAY_TRIAGE_FALLBACK_MODELS="oc/laguna-xs")
        side = [
            PrimitiveError("claude exited rc=1: ", state="no execution guarantee"),
            {"result": json.dumps(DRAFT)},
        ]
        with mock.patch("friday.l1.dev._run_claude", side_effect=side) as m:
            draft, reason = draft_one(self.RECS)
        self.assertIsNotNone(draft)
        self.assertEqual(m.call_count, 2)
        self.assertEqual(m.call_args_list[1].args[3], "oc/laguna-xs")
        self.assertEqual(reason, "")

    def test_no_fallback_reuses_same_model(self):
        """Default (no FRIDAY_TRIAGE_FALLBACK_MODELS) preserves the
        pre-chain behavior: a failed attempt retries the SAME model, then
        the group stays unprocessed - and the reason names the failed
        model so the failure is diagnosable."""
        with mock.patch(
            "friday.l1.dev._run_claude", side_effect=RuntimeError("claude CLI down")
        ) as m:
            draft, reason = draft_one(self.RECS)
        self.assertIsNone(draft)
        self.assertEqual(m.call_count, 3)
        self.assertEqual([c.args[3] for c in m.call_args_list], ["opus"] * 3)
        self.assertIn("LLM call failed", reason)
        self.assertIn("opus", reason)

    def test_structural_rejection_does_not_advance_chain(self):
        """A structurally-broken reply is a WORKING model's defect - the
        repair loop feeds the rejection back to the SAME model. The chain
        advances only on timeout/hard failure: a model that responds is
        alive even when its draft is wrong."""
        self.set_env(FRIDAY_TRIAGE_FALLBACK_MODELS="oc/laguna-xs")
        side = [{"result": "not json at all"}, {"result": json.dumps(DRAFT)}]
        with mock.patch("friday.l1.dev._run_claude", side_effect=side) as m:
            draft, _reason = draft_one(self.RECS)
        self.assertIsNotNone(draft)
        self.assertEqual(m.call_count, 2)
        self.assertEqual([c.args[3] for c in m.call_args_list], ["opus", "opus"])

    def test_chain_exhausted_reuses_last_model(self):
        """Primary AND fallback both fail: the last model is reused for the
        remaining bounded attempts, the group stays unprocessed, and the
        reason names the LAST model that failed."""
        from friday.errors import PrimitiveError

        self.set_env(FRIDAY_TRIAGE_FALLBACK_MODELS="oc/laguna-xs")
        with mock.patch(
            "friday.l1.dev._run_claude",
            side_effect=PrimitiveError("claude exited rc=1: ", state="s"),
        ) as m:
            draft, reason = draft_one(self.RECS)
        self.assertIsNone(draft)
        self.assertEqual(m.call_count, 3)
        self.assertEqual(
            [c.args[3] for c in m.call_args_list],
            ["opus", "oc/laguna-xs", "oc/laguna-xs"],
        )
        self.assertIn("oc/laguna-xs", reason)

    def test_fallback_chain_parses_order_and_whitespace(self):
        from friday.gap_triage import _triage_model_chain

        self.set_env(
            FRIDAY_TRIAGE_MODEL="oc/laguna-s-2.1-free",
            FRIDAY_TRIAGE_FALLBACK_MODELS=" oc/laguna-xs , openrouter/poolside/laguna-xs-2.1:free ",
        )
        self.assertEqual(
            _triage_model_chain(),
            ["oc/laguna-s-2.1-free", "oc/laguna-xs", "openrouter/poolside/laguna-xs-2.1:free"],
        )

    def test_chain_single_model_without_fallbacks(self):
        from friday.gap_triage import _triage_model_chain

        self.set_env(FRIDAY_TRIAGE_FALLBACK_MODELS="  , , ")
        self.assertEqual(_triage_model_chain(), ["opus"])


class TestNormalizeName(EnvTestCase):
    """The deterministic prefix repair (2026-08-13 live finding): the model
    repeatedly emitted 'friday.l1.files.write_text' - the fully-qualified
    Python path - instead of the '<module>.<fn>' contract name, even after
    the rejection was fed back. The prefix is stripped mechanically; the
    exact-name check still guards semantics."""

    def test_strips_friday_package_prefix(self):
        self.assertEqual(
            _normalize_contract_name("friday.l1.files.write_text"),
            "files.write_text",
        )

    def test_leaves_plain_module_fn_untouched(self):
        self.assertEqual(_normalize_contract_name("files.write_text"), "files.write_text")

    def test_two_part_name_untouched(self):
        self.assertEqual(_normalize_contract_name("gmail.send_document"), "gmail.send_document")

    def test_normalized_draft_passes_self_check(self):
        """The exact observed failure: a draft whose contract name is the
        fully-qualified path is normalized and then passes the checks - the
        gap is now SOLVABLE by the loop instead of rejected forever."""
        draft = {
            "contract": {
                "name": "friday.l1.files.write_text",
                "precondition": "p",
                "postcondition": "q",
                "idempotency": "idempotent",
                "failure_mode": "f",
                "returns": "str",
            },
            "impl": CONTRACT_PREFIX.replace('returns="bool"', 'returns="str"')
            + "def write_text(path: str, text: str) -> str:\n    # Write.\n    open(path, 'w', encoding='utf-8').write(text)\n    return path\n",
            "test": "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            "rationale": "r",
        }
        contract = draft["contract"]
        contract["name"] = _normalize_contract_name(contract["name"])
        self.assertEqual(_self_check("files.write_text", draft), [])

    def test_normalize_does_not_mask_a_rename(self):
        """A fully-qualified RENAME ('friday.l1.files.write_notes') normalizes
        to 'files.write_notes' and is still rejected by the exact-name check
        - the prefix repair must never mask a semantic defect."""
        draft = {
            "contract": {
                "name": "friday.l1.files.write_notes",
                "precondition": "p",
                "postcondition": "q",
                "idempotency": "idempotent",
                "failure_mode": "f",
                "returns": "str",
            },
            "impl": "def write_notes(path: str, text: str) -> str:\n    # Write.\n    return path\n",
            "test": "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            "rationale": "r",
        }
        contract = draft["contract"]
        contract["name"] = _normalize_contract_name(contract["name"])
        issues = _self_check("files.write_text", draft)
        self.assertTrue(any("EXACTLY equal" in i for i in issues), issues)


class TestSelfCheck(EnvTestCase):
    """The triage-time structural gate (Fix 1, 2026-08-13): every draft is
    run through the gate's OWN checks before it is written, and a broken
    draft gets the exact rejection fed back for a bounded repair retry -
    so structurally-broken LLM drafts are repaired at triage instead of
    reaching register_proposal only to fail there (the observed pattern:
    4/4 real drafts caught at gate stage 1)."""

    RECS = [
        {
            "gap_id": "1",
            "source": "executor",
            "attempted_primitive": "files.write_text",
            "goal_context": "write a note",
            "refusal_reason": "no registered contract",
        }
    ]

    def _broken_contract(self, name="friday.l1.files.write_notes"):
        return {
            "contract": {
                "name": name,
                "precondition": "p",
                "postcondition": "q",
                "idempotency": "idempotent",
                "failure_mode": "f",
                "returns": "str",
            },
            "impl": "def write_notes(path: str, text: str) -> str:\n    # Write.\n    return path\n",
            "test": "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            "rationale": "r",
        }

    def test_clean_draft_passes(self):
        self.assertEqual(_self_check("files.do_thing", DRAFT), [])

    def test_three_dot_contract_name_rejected(self):
        """The observed defect: a 4-segment qualified name instead of
        '<module>.<fn>' (real drafts emitted friday.l1.files.write_notes
        and friday.l1.gmail.send_receipt)."""
        issues = _self_check("files.write_text", self._broken_contract())
        self.assertTrue(any("<module>.<fn>" in i for i in issues), issues)

    def test_renamed_primitive_rejected(self):
        """A draft that renames the gapped primitive (write_text ->
        write_notes) passes schema but would never solve the gap - the
        exact-name check must catch it."""
        ok = {
            "name": "files.write_notes",
            "precondition": "p",
            "postcondition": "q",
            "idempotency": "idempotent",
            "failure_mode": "f",
            "returns": "str",
        }
        issues = _self_check(
            "files.write_text",
            dict(self._broken_contract(), contract=ok),
        )
        self.assertTrue(any("EXACTLY equal" in i for i in issues), issues)

    def test_uncompilable_impl_rejected(self):
        bad = dict(self._broken_contract(name="files.write_text"), impl="def broken(:\n")
        issues = _self_check("files.write_text", bad)
        self.assertTrue(any("impl" in i and "compile" in i for i in issues), issues)

    def test_dead_arg_and_ast_defects_rejected(self):
        bad = dict(
            self._broken_contract(name="files.write_text"),
            impl="def write_text(path: str, text: str) -> str:\n    return 'hardcoded'\n",
        )
        issues = _self_check("files.write_text", bad)
        self.assertTrue(any("never used" in i for i in issues), issues)

    def test_broken_draft_repaired_on_retry(self):
        """The centerpiece: a structurally-broken first draft gets the EXACT
        rejection fed back, and the second attempt's clean draft is accepted
        - the loop now PRODUCES survivors instead of shipping garbage to the
        gate."""
        broken = self._broken_contract()  # three-dot name, renamed primitive
        repaired = {
            "contract": {
                "name": "files.write_text",
                "precondition": "p",
                "postcondition": "q",
                "idempotency": "idempotent",
                "failure_mode": "f",
                "returns": "str",
            },
            "impl": CONTRACT_PREFIX.replace('returns="bool"', 'returns="str"')
            + "def write_text(path: str, text: str) -> str:\n    # Write the text to the path.\n    open(path, 'w', encoding='utf-8').write(text)\n    return path\n",
            "test": "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self):\n        self.assertTrue(True)\n",
            "rationale": "r",
        }
        side = [
            {"result": json.dumps(broken)},
            {"result": json.dumps(repaired)},
        ]  # second attempt repaired
        with mock.patch("friday.l1.dev._run_claude", side_effect=side) as m:
            draft, reason = draft_one(self.RECS)
        self.assertEqual(m.call_count, 2)
        self.assertEqual(draft["contract"]["name"], "files.write_text")
        self.assertEqual(reason, "")
        # the rejection was actually fed back into the second prompt
        second_prompt = m.call_args_list[1].args[0]
        self.assertIn("structural self-check failed", second_prompt)
        self.assertIn("<module>.<fn>", second_prompt)

    def test_persistently_broken_returns_none(self):
        """A draft that never passes the self-check is left unprocessed -
        never written as a known-broken artifact, and the REASON is
        visible (self-check rejection, not an opaque failure)."""
        broken = self._broken_contract()
        with mock.patch(
            "friday.l1.dev._run_claude", return_value={"result": json.dumps(broken)}
        ) as m:
            draft, reason = draft_one(self.RECS)
        self.assertIsNone(draft)
        self.assertIn("structural self-check failed", reason)
        self.assertEqual(m.call_count, 3)  # bounded repair attempts

    def test_test_py_compile_defect_rejected(self):
        """The self-check must not write a draft whose own test.py does not
        compile - that defect would otherwise only surface at the gate's
        sandbox run."""
        bad = dict(
            self._broken_contract(name="files.write_text"),
            impl="def write_text(path: str, text: str) -> str:\n    # Write.\n    return path\n",
            test="def broken(:",
        )
        issues = _self_check("files.write_text", bad)
        self.assertTrue(any("test.py does not compile" in i for i in issues), issues)

    def test_test_py_danger_ast_rejected(self):
        """The gate AST-checks test.py before executing it (the sandbox never
        runs an AST-rejected test); the self-check now mirrors that so the LLM
        repairs its test at draft time. Observed live 2026-08-14: the clipboard
        draft's test was rejected at the gate THREE times in a row
        (subprocess.CompletedProcess -> __import__ -> TimeoutExpired) because
        the self-check only compiled it."""
        bad = dict(
            self._broken_contract(name="files.write_text"),
            impl=CONTRACT_PREFIX.replace('returns="bool"', 'returns="str"')
            + "def write_text(path: str, text: str) -> str:\n    # Write.\n    return path\n",
            test="import os\nos.system('true')\n",
        )
        issues = _self_check("files.write_text", bad)
        self.assertTrue(any("test AST" in i and "os.system" in i for i in issues), issues)

    def test_test_py_subprocess_mock_constructor_rejected(self):
        """The exact clipboard test defect: building a mock via
        subprocess.CompletedProcess(...) is rejected by the gate's test.py
        danger check - and now by the triage self-check, so the LLM repairs it
        before the draft is ever written."""
        bad = dict(
            self._broken_contract(name="files.write_text"),
            impl=CONTRACT_PREFIX.replace('returns="bool"', 'returns="str"')
            + "def write_text(path: str, text: str) -> str:\n    # Write.\n    return path\n",
            test="import subprocess\nsubprocess.CompletedProcess([])\n",
        )
        issues = _self_check("files.write_text", bad)
        self.assertTrue(
            any("test AST" in i and "subprocess.CompletedProcess" in i for i in issues), issues
        )

    def test_missing_contract_decorator_rejected_at_triage(self):
        """The clipboard round's first defect is now repaired at TRIAGE: an
        impl without the @contract decorator would never enter REGISTRY - the
        self-check feeds that back to the LLM instead of writing a dead draft."""
        bad = dict(
            self._broken_contract(name="files.write_text"),
            impl="def write_text(path: str, text: str) -> str:\n    # Write.\n    return path\n",
        )
        issues = _self_check("files.write_text", bad)
        self.assertTrue(any("not decorated with @contract" in i for i in issues), issues)

    def test_undefined_log_transform_rejected_at_triage(self):
        """A contract naming a log_transform the impl never defines is a
        NameError at import - caught at triage, before the draft is written."""
        c = {
            "name": "files.write_text",
            "precondition": "p",
            "postcondition": "q",
            "idempotency": "idempotent",
            "failure_mode": "f",
            "returns": "str",
            "log_transform": "_log_redact_meta",
        }
        bad = dict(
            self._broken_contract(name="files.write_text"),
            contract=c,
            impl=CONTRACT_PREFIX.replace('returns="bool"', 'returns="str"')
            + "def write_text(path: str, text: str) -> str:\n    # Write.\n    return path\n",
        )
        issues = _self_check("files.write_text", bad)
        self.assertTrue(any("log_transform" in i and "never defines" in i for i in issues), issues)

    def test_bare_builtin_raise_rejected_at_triage(self):
        """A draft raising bare RuntimeError against a contract declaring
        PrimitiveError is repaired at triage, not at human review."""
        c = {
            "name": "files.write_text",
            "precondition": "p",
            "postcondition": "q",
            "idempotency": "idempotent",
            "failure_mode": "PrimitiveError when the write fails.",
            "returns": "str",
        }
        bad = dict(
            self._broken_contract(name="files.write_text"),
            contract=c,
            impl=CONTRACT_PREFIX.replace('returns="bool"', 'returns="str"')
            + "def write_text(path: str, text: str) -> str:\n"
            "    raise RuntimeError('boom')\n",
        )
        issues = _self_check("files.write_text", bad)
        self.assertTrue(any("raises builtin RuntimeError" in i for i in issues), issues)


class TestTriage(EnvTestCase):
    def setUp(self):
        super().setUp()
        # never write drafts into the real gates/proposed_primitives/
        self.set_env(FRIDAY_PROPOSALS_DIR=str(self.mktmp()))

    def _seed_gap(self, gaps) -> None:
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        record_gap(
            source="executor",
            goal_id="locate the missing thing",
            attempted_primitive="files.do_thing",
            attempted_args={"name": "x"},
            goal_context="locate the missing thing",
            refusal_reason="no registered contract",
        )

    def test_writes_artifacts_marks_processed_and_is_idempotent(self):
        gaps = self.mktmp() / "gaps.jsonl"
        self._seed_gap(gaps)
        with mock.patch(
            "friday.l1.dev._run_claude", return_value={"result": json.dumps(DRAFT)}
        ) as m:
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

    def test_registered_primitive_gaps_consumed_without_drafting(self):
        """The post-approval lifecycle: the ambient-gap probes keep refusing
        a primitive AFTER it is approved and registered. Triage must consume
        those gaps as SOLVED - never LLM-draft an existing primitive again
        (no duplicate proposals, no wasted calls)."""
        gaps = self.mktmp() / "gaps.jsonl"
        self.set_env(FRIDAY_GAPS_FILE=str(gaps))
        record_gap(
            source="watcher",
            trigger_id="ambient-gap-probe-calendar",
            attempted_primitive="files.find_file_exact",  # real, registered
            goal_context="probe",
            refusal_reason="trigger allowlist [...]",
        )
        with mock.patch("friday.l1.dev._run_claude") as m:
            written = triage()
        self.assertEqual(written, [])
        m.assert_not_called()  # a solved primitive never reaches the LLM
        self.assertEqual(unprocessed_gaps(), [])  # consumed
        self.assertFalse(proposal_dir("files.find_file_exact").exists())

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

    def test_written_proposal_records_self_check_status(self):
        """rationale.md must state whether the draft passed the triage
        self-check - a human reviewer sees it before reading the diff."""
        clean = dict(DRAFT, contract=dict(DRAFT["contract"], name="files.do_thing"))
        d = write_proposal("files.do_thing", [{"gap_id": "1"}], clean)
        text = (d / "rationale.md").read_text(encoding="utf-8")
        self.assertIn("structural self-check: passed", text)
        # a renamed-primitive draft reports the failure honestly
        d2 = write_proposal(
            "files.write_text", [{"gap_id": "1"}], DRAFT
        )  # DRAFT names files.do_thing
        text2 = (d2 / "rationale.md").read_text(encoding="utf-8")
        self.assertIn("structural self-check: FAILED", text2)


class TestHelpers(EnvTestCase):
    def test_proposal_dir_sanitizes(self):
        self.set_env(FRIDAY_PROPOSALS_DIR=str(self.mktmp()))
        self.assertEqual(proposal_dir("files.do_thing").name, "files.do_thing")
        self.assertEqual(proposal_dir("a/b:c").name, "a_b_c")

    def test_compiles_does_not_execute(self):
        self.assertTrue(_compiles("x = 1\n"))
        self.assertFalse(_compiles("def broken(:\n"))
