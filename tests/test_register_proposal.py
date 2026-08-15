"""Minimal approval gate: signature required, contract schema validated,
impl syntax validated, registration idempotent, and the planner's L1
auto-discovery picks up new modules. Everything is hermetic - proposals
and the l1 target dir are temp (FRIDAY_PROPOSALS_DIR / FRIDAY_L1_DIR)."""

from __future__ import annotations

import json
from pathlib import Path

from friday.register_proposal import (
    approve_and_register,
    register,
    require_approval,
    validate_contract,
    validate_impl,
)
from tests.helpers import EnvTestCase

GOOD_CONTRACT = {
    "name": "demo.new_prim",
    "precondition": "p",
    "postcondition": "q",
    "idempotency": "idempotent",
    "failure_mode": "f",
    "returns": "bool",
}
GOOD_IMPL = (
    "from friday.contracts import Idempotency, contract\n"
    "@contract(precondition=\"p\", postcondition=\"q\",\n"
    "          idempotency=Idempotency.IDEMPOTENT, failure_mode=\"f\", returns=\"bool\")\n"
    "def new_prim() -> bool:\n"
    "    \"\"\"Do it.\"\"\"\n"
    "    return True\n"
)
GOOD_TEST = (
    "import unittest\n"
    "from friday.l1.demo import new_prim\n"
    "class T(unittest.TestCase):\n"
    "    def test_ok(self):\n"
    "        self.assertTrue(new_prim())\n"
)


class TestApprovalGate(EnvTestCase):
    def _proposal(self, *, marker: bool, token: bool = True) -> Path:
        d = self.mktmp() / "demo.new_prim"
        d.mkdir(parents=True)
        if marker:
            (d / "APPROVED.md").write_text(
                ("APPROVED\nsigned by the human gate\n" if token else "NOT YET\n"),
                encoding="utf-8",
            )
        return d

    def test_requires_approval_marker(self):
        ok, err = require_approval(self._proposal(marker=False))
        self.assertFalse(ok)
        self.assertIn("APPROVED.md", err)

    def test_marker_without_token_rejected(self):
        ok, _ = require_approval(self._proposal(marker=True, token=False))
        self.assertFalse(ok)

    def test_signed_proposal_accepted(self):
        ok, err = require_approval(self._proposal(marker=True))
        self.assertTrue(ok, err)

    def test_contract_must_be_json_object_not_source(self):
        # the defect seen in a real LLM draft
        ok, err = validate_contract('@contract(precondition="p")')
        self.assertFalse(ok)
        self.assertIn("plain JSON object", err)

    def test_contract_schema_validated(self):
        self.assertTrue(validate_contract(dict(GOOD_CONTRACT))[0])
        for bad, why in [
            (dict(GOOD_CONTRACT, idempotency="sometimes"), "idempotency"),
            (dict(GOOD_CONTRACT, name="no_dot"), "module"),
            (dict(GOOD_CONTRACT, name=""), "field"),
            ({}, "field"),
        ]:
            ok, err = validate_contract(bad)
            self.assertFalse(ok, why)
            self.assertTrue(err)

    def test_impl_must_compile_and_define_function(self):
        self.assertTrue(validate_impl(GOOD_IMPL, "new_prim")[0])
        ok, err = validate_impl("def broken(:\n", "new_prim")
        self.assertFalse(ok)
        self.assertIn("does not compile", err)
        ok, err = validate_impl("x = 1\n", "new_prim")
        self.assertFalse(ok)
        self.assertIn("does not define", err)


class TestRegister(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.set_env(FRIDAY_L1_DIR=str(self.mktmp()))

    def test_new_module_written_and_idempotent(self):
        import os

        target_dir = Path(os.environ["FRIDAY_L1_DIR"])
        ok, _ = register("demo.new_prim", GOOD_IMPL)
        self.assertTrue(ok)
        f = target_dir / "demo.py"
        self.assertTrue(f.is_file())
        self.assertIn("def new_prim", f.read_text(encoding="utf-8"))
        # idempotent: re-registering is a no-op success, not a duplicate def
        ok, msg = register("demo.new_prim", GOOD_IMPL)
        self.assertTrue(ok)
        self.assertIn("already registered", msg)
        self.assertEqual(f.read_text(encoding="utf-8").count("def new_prim"), 1)

    def test_appends_to_existing_module(self):
        import os

        target_dir = Path(os.environ["FRIDAY_L1_DIR"])
        (target_dir / "demo.py").write_text("EXISTING = 1\n", encoding="utf-8")
        ok, msg = register("demo.new_prim", GOOD_IMPL)
        self.assertTrue(ok)
        self.assertIn("appended", msg)
        text = (target_dir / "demo.py").read_text(encoding="utf-8")
        self.assertIn("EXISTING = 1", text)
        self.assertIn("def new_prim", text)

    def test_future_import_stripped_when_appending(self):
        """Regression (gmail.send_document): an impl beginning with
        `from __future__ import annotations` (idiomatic in standalone
        files) is a SyntaxError when appended at EOF of an existing module
        - register() must strip it so the module stays importable."""
        import os

        target_dir = Path(os.environ["FRIDAY_L1_DIR"])
        (target_dir / "demo.py").write_text("EXISTING = 1\n", encoding="utf-8")
        impl = (
            '"""Docstring."""\n'
            "from __future__ import annotations\n"
            "def new_prim() -> bool:\n"
            '    """Do it."""\n'
            "    return True\n"
        )
        ok, msg = register("demo.new_prim", impl)
        self.assertTrue(ok, msg)
        text = (target_dir / "demo.py").read_text(encoding="utf-8")
        self.assertNotIn("from __future__", text)  # stripped - see the docstring
        # the module must still compile AND import (a future import at EOF
        # would be a SyntaxError on import)
        compile(text, "<demo.py>", "exec")
        sys_path_before = list(__import__("sys").path)
        __import__("sys").path.insert(0, str(target_dir))
        try:
            import demo  # noqa: F401
        finally:
            __import__("sys").path[:] = sys_path_before
            __import__("sys").modules.pop("demo", None)

    def test_future_import_with_semicolon_keeps_remainder(self):
        """A single-line `from __future__ import x; y = 1` shares its line
        with another statement - the strip must keep the remainder, never
        delete other code along with the future import."""
        import os

        target_dir = Path(os.environ["FRIDAY_L1_DIR"])
        (target_dir / "demo.py").write_text("EXISTING = 1\n", encoding="utf-8")
        impl = (
            "from __future__ import annotations; MARKER = 1\n"
            "def new_prim() -> bool:\n"
            '    return MARKER == 1\n'
        )
        ok, msg = register("demo.new_prim", impl)
        self.assertTrue(ok, msg)
        text = (target_dir / "demo.py").read_text(encoding="utf-8")
        self.assertNotIn("from __future__", text)
        self.assertIn("MARKER = 1", text)  # the `;`-joined remainder survived
        compile(text, "<demo.py>", "exec")


class TestApproveAndRegister(EnvTestCase):
    def setUp(self):
        super().setUp()
        self.set_env(FRIDAY_L1_DIR=str(self.mktmp()), FRIDAY_PROPOSALS_DIR=str(self.mktmp()))

    def _proposal_dir(self) -> Path:
        import os

        d = Path(os.environ["FRIDAY_PROPOSALS_DIR"]) / "demo.new_prim"
        d.mkdir(parents=True)
        (d / "contract.json").write_text(json.dumps(GOOD_CONTRACT), encoding="utf-8")
        (d / "impl.py").write_text(GOOD_IMPL, encoding="utf-8")
        (d / "test.py").write_text(GOOD_TEST, encoding="utf-8")
        return d

    def test_full_gate_refuses_without_signature(self):
        ok, msg = approve_and_register(self._proposal_dir())
        self.assertFalse(ok)
        self.assertIn("REJECTED", msg)
        self.assertIn("APPROVED.md", msg)

    def test_full_gate_registers_signed_valid_proposal(self):
        d = self._proposal_dir()
        (d / "APPROVED.md").write_text("APPROVED\nhuman signed\n", encoding="utf-8")
        ok, msg = approve_and_register(d)
        self.assertTrue(ok, msg)
        self.assertIn("registered demo.new_prim", msg)
        import os

        f = Path(os.environ["FRIDAY_L1_DIR"]) / "demo.py"
        self.assertTrue(f.is_file())
        self.assertIn("def new_prim", f.read_text(encoding="utf-8"))

    def test_schema_rejection_is_annotated_in_rationale(self):
        """A contract-schema rejection must leave a rejection record in the
        proposal's rationale.md - a rejected draft must not keep saying
        APPROVAL: PENDING (observed on the first ambient gmail draft)."""
        d = self._proposal_dir()
        (d / "rationale.md").write_text("DRAFT\n- APPROVAL: PENDING\n", encoding="utf-8")
        (d / "contract.json").write_text(
            json.dumps(dict(GOOD_CONTRACT, name="a.b.c.d")), encoding="utf-8"
        )
        ok, msg = approve_and_register(d)
        self.assertFalse(ok)
        self.assertIn("REJECTED", msg)
        text = (d / "rationale.md").read_text(encoding="utf-8")
        self.assertIn("Gate rejection", text)
        self.assertIn("REJECTED", text)

    def test_gate_rejects_bad_contract_even_when_signed(self):
        d = self._proposal_dir()
        (d / "APPROVED.md").write_text("APPROVED\n", encoding="utf-8")
        (d / "contract.json").write_text(json.dumps(dict(GOOD_CONTRACT, idempotency="nope")), encoding="utf-8")
        ok, msg = approve_and_register(d)
        self.assertFalse(ok)
        self.assertIn("REJECTED", msg)

    def test_automated_gate_blocks_signed_dangerous_impl(self):
        """Even a SIGNED proposal is blocked: an impl calling subprocess is
        caught by AST before the signature step and never registered."""
        import os

        d = self._proposal_dir()
        (d / "APPROVED.md").write_text("APPROVED\n", encoding="utf-8")
        (d / "impl.py").write_text(
            "import subprocess\n\n"
            "def new_prim() -> bool:\n"
            '    return subprocess.run(["true"]).returncode == 0\n',
            encoding="utf-8",
        )
        ok, msg = approve_and_register(d)
        self.assertFalse(ok)
        self.assertIn("REJECTED by the automated gate", msg)
        self.assertIn("subprocess.run", msg)
        self.assertIn("sandbox: SKIPPED", msg)
        self.assertFalse((Path(os.environ["FRIDAY_L1_DIR"]) / "demo.py").is_file())

    def test_automated_gate_blocks_signed_dead_arg_impl(self):
        """The exact defect the human caught by hand last round (an impl
        ignoring its own argument) is now caught mechanically."""
        import os

        d = self._proposal_dir()
        (d / "APPROVED.md").write_text("APPROVED\n", encoding="utf-8")
        (d / "impl.py").write_text(
            "def new_prim(name: str) -> bool:\n    return True\n",
            encoding="utf-8",
        )
        ok, msg = approve_and_register(d)
        self.assertFalse(ok)
        self.assertIn("never used", msg)
        self.assertFalse((Path(os.environ["FRIDAY_L1_DIR"]) / "demo.py").is_file())

    def test_signed_valid_proposal_sandbox_runs_and_registers(self):
        """The full gate with a real test.py: AST passes, the sandbox runs
        the draft's test, the signature authorizes registration."""
        import os

        d = self._proposal_dir()
        (d / "APPROVED.md").write_text("APPROVED\nhuman signed\n", encoding="utf-8")
        ok, msg = approve_and_register(d)
        self.assertTrue(ok, msg)
        self.assertIn("AST checks: passed", msg)
        self.assertIn("sandbox: PASS", msg)
        self.assertIn("registered demo.new_prim", msg)
        self.assertTrue((Path(os.environ["FRIDAY_L1_DIR"]) / "demo.py").is_file())


class TestL1Discovery(EnvTestCase):
    def test_planner_discovers_modules_from_dir(self):
        from friday.l4.planner import _discover_l1_modules

        d = self.mktmp()
        self.set_env(FRIDAY_L1_DIR=str(d))
        (d / "alpha.py").write_text("", encoding="utf-8")
        (d / "beta.py").write_text("", encoding="utf-8")
        (d / "__init__.py").write_text("", encoding="utf-8")
        self.assertEqual(_discover_l1_modules(), ["alpha", "beta"])

    def test_falls_back_to_known_modules(self):
        from friday.l4.planner import _L1_MODULES, _discover_l1_modules

        self.set_env(FRIDAY_L1_DIR="/nonexistent/dir")
        self.assertEqual(_discover_l1_modules(), list(_L1_MODULES))
