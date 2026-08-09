"""L4 planner: validate_plan (schema + blocked + kwargs), build_catalog
(no blocked primitives, checks listed), project facts (load/override/
substitution/collisions), prompt assembly, JSON extraction."""

from __future__ import annotations

import json
import unittest

from friday.errors import FridayError
from friday.l4 import planner
from tests.helpers import EnvTestCase

GOOD_PLAN = {
    "goal": "find the receipt",
    "steps": [
        {
            "primitive": "files.find_file",
            "args": {"name": "receipt", "directory": "/tmp"},
            "verify": {"check": "checks.file_exists", "args": {"path": "$steps.1.result.path"}, "expect": True},
        }
    ],
}


class TestValidatePlan(EnvTestCase):
    def test_good_plan(self):
        ok, err = planner.validate_plan(GOOD_PLAN)
        self.assertTrue(ok, err)

    def test_not_a_dict(self):
        self.assertFalse(planner.validate_plan([])[0])

    def test_missing_goal(self):
        self.assertFalse(planner.validate_plan({"steps": []})[0])

    def test_empty_steps(self):
        self.assertFalse(planner.validate_plan({"goal": "x", "steps": []})[0])

    def test_unknown_primitive(self):
        p = json.loads(json.dumps(GOOD_PLAN))
        p["steps"][0]["primitive"] = "nope.nope"
        ok, err = planner.validate_plan(p)
        self.assertFalse(ok)
        self.assertIn("unknown or unregistered", err)

    def test_blocked_primitive(self):
        p = {"goal": "x", "steps": [{"primitive": "window.shutdown", "args": {},
                                     "verify": {"check": "checks.window_client_count", "args": {}, "expect": 0}}]}
        ok, err = planner.validate_plan(p)
        self.assertFalse(ok)
        self.assertIn("EXECUTOR_BLOCKED", err)

    def test_missing_verify(self):
        p = {"goal": "x", "steps": [{"primitive": "files.find_file", "args": {}}]}
        self.assertFalse(planner.validate_plan(p)[0])

    def test_unknown_check(self):
        p = json.loads(json.dumps(GOOD_PLAN))
        p["steps"][0]["verify"]["check"] = "checks.nope"
        self.assertFalse(planner.validate_plan(p)[0])

    def test_bad_kwarg_to_primitive(self):
        p = json.loads(json.dumps(GOOD_PLAN))
        p["steps"][0]["args"]["bogus_arg"] = 1
        ok, err = planner.validate_plan(p)
        self.assertFalse(ok)
        self.assertIn("does not accept arg", err)

    def test_bad_kwarg_to_check(self):
        p = json.loads(json.dumps(GOOD_PLAN))
        p["steps"][0]["verify"]["args"]["bogus"] = 1
        self.assertFalse(planner.validate_plan(p)[0])

    def test_retries_non_int(self):
        p = json.loads(json.dumps(GOOD_PLAN))
        p["steps"][0]["retries"] = "three"
        self.assertFalse(planner.validate_plan(p)[0])

    def test_bool_timing_rejected(self):
        p = json.loads(json.dumps(GOOD_PLAN))
        p["steps"][0]["backoff_s"] = True
        self.assertFalse(planner.validate_plan(p)[0])

    def test_non_positive_timing_rejected(self):
        p = json.loads(json.dumps(GOOD_PLAN))
        p["steps"][0]["verify_wait_s"] = 0
        self.assertFalse(planner.validate_plan(p)[0])

    def test_unresolved_facts_rejected(self):
        p = json.loads(json.dumps(GOOD_PLAN))
        p["steps"][0]["args"]["directory"] = "$facts.downloads"
        ok, err = planner.validate_plan(p)
        self.assertFalse(ok)
        self.assertIn("$facts", err)


class TestCatalog(EnvTestCase):
    def test_lists_primitives_and_checks(self):
        cat = planner.build_catalog()
        self.assertIn("window.list_clients", cat)
        self.assertIn("notify.notify_send", cat)
        self.assertIn("checks.file_exists", cat)
        self.assertIn("checks.message_sent", cat)

    def test_hides_blocked_primitives(self):
        cat = planner.build_catalog()
        self.assertNotIn("window.shutdown", cat)


class TestFacts(EnvTestCase):
    def test_defaults_when_no_file(self):
        d = self.mktmp()
        self.set_env(FRIDAY_FACTS_FILE=str(d / "missing.json"))
        facts = planner.load_project_facts()
        self.assertIn("test_tone", facts.file_paths)

    def test_load_and_resolve_paths(self):
        d = self.mktmp()
        f = d / "facts.json"
        f.write_text(json.dumps({"file_paths": {"downloads": "~/Downloads"}, "recipients": {"wa": "123"}}), encoding="utf-8")
        facts = planner.load_project_facts(f)
        self.assertTrue(facts.file_paths["downloads"].startswith("/"))
        self.assertEqual(facts.recipients["wa"], "123")

    def test_collision_raises(self):
        d = self.mktmp()
        f = d / "facts.json"
        f.write_text(json.dumps({"file_paths": {"dup": "x"}, "recipients": {"dup": "y"}}), encoding="utf-8")
        with self.assertRaises(FridayError):
            planner.load_project_facts(f)

    def test_bad_json_raises(self):
        d = self.mktmp()
        f = d / "facts.json"
        f.write_text("{not json", encoding="utf-8")
        with self.assertRaises(FridayError):
            planner.load_project_facts(f)

    def test_substitute_facts_refs(self):
        d = self.mktmp()
        f = d / "facts.json"
        f.write_text(json.dumps({"file_paths": {"readme": "README.md"}}), encoding="utf-8")
        project = planner.load_project_facts(f)
        out = planner._substitute_facts_refs({"a": {"p": "$facts.readme"}, "b": ["$facts.readme"]}, project)
        self.assertTrue(out["a"]["p"].endswith("README.md"))
        self.assertEqual(out["a"]["p"], out["b"][0])

    def test_substitute_unknown_raises(self):
        d = self.mktmp()
        f = d / "facts.json"
        f.write_text("{}", encoding="utf-8")
        project = planner.load_project_facts(f)
        with self.assertRaises(FridayError):
            planner._substitute_facts_refs("$facts.nope", project)


class TestExtractJson(EnvTestCase):
    def test_fenced(self):
        self.assertEqual(planner._extract_json('```json\n{"a": 1}\n```'), {"a": 1})

    def test_bare(self):
        self.assertEqual(planner._extract_json('{"a": 1}'), {"a": 1})

    def test_garbage(self):
        self.assertIsNone(planner._extract_json("not json at all"))

    def test_embedded(self):
        self.assertEqual(planner._extract_json('prefix {"a": 1} suffix'), {"a": 1})


class TestPrompt(EnvTestCase):
    def test_prompt_contains_goal_and_catalog(self):
        prompt = planner.build_prompt("do the thing")
        self.assertIn("do the thing", prompt)
        self.assertIn("PRIMITIVES:", prompt)
        self.assertIn("READ-ONLY CHECKS", prompt)

    def test_prompt_carries_rejection_reason(self):
        prompt = planner.build_prompt("g", last_error="your plan was bad")
        self.assertIn("your plan was bad", prompt)


if __name__ == "__main__":
    unittest.main()
