"""L3 executor: the $steps.N.result resolver (dot/bracket/list-index),
blocked-primitive refusal, contract-derived retry policy, and the plan
state machine - all with zero side effects (file-based primitives only)."""

from __future__ import annotations

import unittest

from friday.errors import FridayError
from friday.l3.executor import (
    _apply_refs,
    _default_retries,
    _reject_future_refs,
    _split_ref_path,
    run_plan,
)
from tests.helpers import EnvTestCase


class TestRefResolver(EnvTestCase):
    # results as the executor stores them: {step_id: return_value}
    R = {
        1: {"message_id": "wamid.ABC", "to": "123"},
        2: [{"message_id": "m0"}, {"message_id": "m1"}],
    }

    def test_dot_path(self):
        self.assertEqual(_apply_refs("$steps.1.result.message_id", self.R), "wamid.ABC")

    def test_bracket_path(self):
        self.assertEqual(_apply_refs('$steps.1.result["message_id"]', self.R), "wamid.ABC")
        self.assertEqual(_apply_refs("$steps.1.result['to']", self.R), "123")

    def test_list_index_dot_and_bracket(self):
        self.assertEqual(_apply_refs("$steps.2.result.0.message_id", self.R), "m0")
        self.assertEqual(_apply_refs("$steps.2.result[1].message_id", self.R), "m1")

    def test_whole_result(self):
        self.assertEqual(
            _apply_refs("$steps.1.result", self.R), {"message_id": "wamid.ABC", "to": "123"}
        )

    def test_recursive_application(self):
        v = {"a": ["$steps.2.result.0.message_id"], "b": {"c": "$steps.1.result.to"}}
        self.assertEqual(_apply_refs(v, self.R), {"a": ["m0"], "b": {"c": "123"}})

    def test_literal_text_not_a_ref(self):
        self.assertEqual(_apply_refs("$steps.2.resultX", self.R), "$steps.2.resultX")

    def test_missing_step_raises(self):
        with self.assertRaises(FridayError):
            _apply_refs("$steps.9.result.x", self.R)

    def test_unknown_key_raises(self):
        with self.assertRaises(FridayError):
            _apply_refs("$steps.1.result.nope", self.R)

    def test_index_on_non_list_raises(self):
        with self.assertRaises(FridayError):
            _apply_refs("$steps.1.result.0", self.R)

    def test_out_of_range_index_raises(self):
        with self.assertRaises(FridayError):
            _apply_refs("$steps.2.result[9].message_id", self.R)

    def test_negative_index_rejected(self):
        with self.assertRaises(FridayError):
            _apply_refs("$steps.2.result[-1].message_id", self.R)

    def test_split_ref_path_mixed(self):
        self.assertEqual(_split_ref_path(".a[0].b", ""), ["a", "0", "b"])
        self.assertEqual(_split_ref_path('["key"]', ""), ["key"])

    def test_future_ref_rejected(self):
        with self.assertRaises(FridayError):
            _reject_future_refs({"p": "$steps.2.result.path"}, step_id=1)
        # self-ref and prior refs pass
        _reject_future_refs({"p": "$steps.1.result.path"}, step_id=1)
        _reject_future_refs({"p": "$steps.1.result.path"}, step_id=2)


class TestRetryPolicy(EnvTestCase):
    def test_derived_from_idempotency(self):
        self.assertEqual(_default_retries("whatsapp.send_text"), 0)  # at-most-once: never retry
        self.assertEqual(_default_retries("window.list_clients"), 2)  # idempotent
        self.assertEqual(_default_retries("window.close_window"), 2)  # commutative-safe
        self.assertIsNone(_default_retries("no.such.primitive"))


class TestRunPlan(EnvTestCase):
    def _find_plan(self, directory, name="alpha", expect=True, verify_wait_s=8.0, backoff_s=1.0):
        return {
            "goal": "find a file",
            "steps": [
                {
                    "primitive": "files.find_file",
                    "args": {"name": name, "directory": str(directory)},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result.path"},
                        "expect": expect,
                    },
                    # Fast timing on failure paths: polling a failing verify
                    # for the default 8s across retries would stall the suite.
                    "verify_wait_s": verify_wait_s,
                    "backoff_s": backoff_s,
                }
            ],
        }

    def test_successful_plan_completes(self):
        d = self.mktmp()
        (d / "alpha.txt").write_text("x", encoding="utf-8")
        result = run_plan(self._find_plan(d))
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.steps[0].status, "VERIFIED")
        self.assertEqual(result.steps[0].attempts, 1)

    def test_blocked_primitive_aborts(self):
        plan = {
            "goal": "x",
            "steps": [
                {
                    "primitive": "window.shutdown",
                    "args": {},
                    "verify": {"check": "checks.window_client_count", "args": {}, "expect": 0},
                }
            ],
        }
        with self.assertRaises(FridayError) as ctx:
            run_plan(plan)
        self.assertIn("EXECUTOR_BLOCKED", str(ctx.exception))

    def test_unknown_primitive_aborts(self):
        # files is a real module; files.nope_fn is not registered -> the
        # no-contract refusal fires (a fully unknown module imports fail
        # earlier with 'cannot be imported', which is also an ABORT).
        plan = {
            "goal": "x",
            "steps": [
                {
                    "primitive": "files.nope_fn",
                    "args": {},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "/x"},
                        "expect": True,
                    },
                }
            ],
        }
        with self.assertRaises(FridayError) as ctx:
            run_plan(plan)
        self.assertIn("no registered contract", str(ctx.exception))

    def test_malformed_step_aborts(self):
        plan = {"goal": "x", "steps": [{"primitive": "files.find_file"}]}  # no verify
        with self.assertRaises(FridayError) as ctx:
            run_plan(plan)
        self.assertIn("malformed plan step", str(ctx.exception))

    def test_zero_verify_wait_rejected_before_execution(self):
        plan = {
            "goal": "x",
            "steps": [
                {
                    "primitive": "window.list_clients",
                    "args": {},
                    "verify": {"check": "checks.window_client_count", "args": {}, "expect": 0},
                    "verify_wait_s": 0,
                }
            ],
        }
        with self.assertRaises(FridayError) as ctx:
            run_plan(plan)
        self.assertIn("verify_wait_s must be a positive finite number", str(ctx.exception))

    def test_future_ref_rejected_before_primitive_runs(self):
        plan = {
            "goal": "x",
            "steps": [
                {
                    "primitive": "files.find_file",
                    "args": {"name": "alpha", "directory": "/tmp"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.2.result.path"},
                        "expect": True,
                    },
                },
            ],
        }
        with self.assertRaises(FridayError) as ctx:
            run_plan(plan)
        self.assertIn("references future step 2", str(ctx.exception))

    def test_retry_exhaustion_aborts(self):
        d = self.mktmp()  # no matching file -> PreconditionError every attempt
        plan = self._find_plan(d, name="does-not-exist", verify_wait_s=0.1, backoff_s=0.05)
        with self.assertRaises(FridayError) as ctx:
            run_plan(plan)
        self.assertIn("plan aborted at step 1", str(ctx.exception))

    def test_verify_failure_exhausts_attempts(self):
        d = self.mktmp()
        (d / "alpha.txt").write_text("x", encoding="utf-8")
        # file exists but the plan demands it NOT exist -> verify never passes
        plan = self._find_plan(d, expect=False, verify_wait_s=0.1, backoff_s=0.05)
        with self.assertRaises(FridayError):
            run_plan(plan)

    def test_empty_steps_rejected(self):
        with self.assertRaises(FridayError):
            run_plan({"goal": "x", "steps": []})

    def test_verified_by_world_with_raised_primitive_has_none_result(self):
        """Regression: a step whose primitive raises on every attempt but
        whose verify passes from the WORLD's state (no self-ref) is
        VERIFIED with result=None - it must never crash with an unbound
        return_value NameError (the StepResult.result field is None,
        honest: no return value was produced)."""
        d = self.mktmp()
        (d / "already_there.txt").write_text("x", encoding="utf-8")
        # files.find_file('missing', d) raises PreconditionError every
        # attempt, but checks.file_exists on an unrelated existing path
        # passes immediately - verify does not reference the step's own
        # result, so the executor can VERIFY a failed primitive.
        plan = {
            "goal": "x",
            "steps": [
                {
                    "primitive": "files.find_file",
                    "args": {"name": "missing", "directory": str(d)},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": str(d / "already_there.txt")},
                        "expect": True,
                    },
                    "verify_wait_s": 0.1,
                    "backoff_s": 0.05,
                }
            ],
        }
        result = run_plan(plan)
        self.assertEqual(result.status, "COMPLETED")
        sr = result.steps[0]
        self.assertEqual(sr.status, "VERIFIED")
        self.assertIsNone(sr.result)  # no return value was ever produced
        self.assertIsNotNone(sr.error)  # the primitive failure is still recorded


if __name__ == "__main__":
    unittest.main()
