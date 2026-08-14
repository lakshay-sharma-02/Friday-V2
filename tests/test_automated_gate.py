"""Automated gate (friday/automated_gate.py): the AST checks that run on a
draft impl BEFORE any human review, the sandboxed test execution, and the
subprocess env sanitization. Everything is hermetic: sandbox runs use temp
impl/test files, and the only subprocess spawned is the gate's own sandbox
runner (fast, no network, no credentials)."""

from __future__ import annotations

import ast
import os
import unittest
from pathlib import Path

from friday import automated_gate
from friday.automated_gate import (
    ALLOWED_IMPORTS,
    _build_probe_family,
    _sanitized_env,
    check_danger,
    check_dead_args,
    check_fs_scope,
    check_impl_ast,
    check_imports,
    run_automated_gate,
    run_sandbox_test,
)
from tests.helpers import EnvTestCase

# A structurally clean draft: uses both declared args, no imports, no danger.
CLEAN_IMPL = (
    "def clean_prim(name: str, directory: str | None = None) -> str:\n"
    '    """Resolve name under directory."""\n'
    '    base = directory or "."\n'
    "    return base + \"/\" + name\n"
)

BAD_IMPORTS = [
    "import numpy\n\ndef f(x):\n    return x\n",
    "import evil.thing\n\ndef f(x):\n    return x\n",
    "from requests_oauthlib import x\n\ndef f():\n    return 1\n",
]
DANGER_IMPLS = [
    'def f():\n    exec("x = 1")\n',
    'def f():\n    eval("1 + 1")\n',
    'def f():\n    __import__("os")\n',
    "import subprocess\n\ndef f():\n    subprocess.run([\"ls\"])\n",
    "import os\n\ndef f():\n    os.system(\"ls\")\n",
]
DEAD_ARG_IMPL = (
    "def bad_prim(name: str, directory: str | None = None) -> str:\n"
    '    return "/fixed/path"\n'
)


class TestImportAllowlist(EnvTestCase):
    def test_derived_from_real_primitives(self):
        """The allowlist must cover every import the shipped L1 primitives
        actually use - the derivation is mechanical, not decorative."""
        l1_dir = Path(__file__).resolve().parents[1] / "friday" / "l1"
        observed: set[str] = set()
        for p in l1_dir.glob("*.py"):
            if p.name == "__init__.py":
                continue
            src = p.read_text(encoding="utf-8")
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        observed.add(alias.name.split(".")[0])
                elif isinstance(node, ast.ImportFrom):
                    observed.add((node.module or "").split(".")[0])
        self.assertTrue(observed, "no imports observed in friday/l1?")
        self.assertTrue(observed <= ALLOWED_IMPORTS,
                        f"shipped primitives import outside the allowlist: {observed - ALLOWED_IMPORTS}")

    def test_unseen_import_rejected(self):
        for src in BAD_IMPORTS:
            self.assertTrue(check_imports(src), src)

    def test_allowed_imports_pass(self):
        self.assertEqual(check_imports("import os\n"), [])
        self.assertEqual(check_imports("import requests\n"), [])
        self.assertEqual(check_imports("from friday.contracts import contract\n"), [])
        self.assertEqual(check_imports("from pathlib import Path\n"), [])


class TestDangerChecks(EnvTestCase):
    def test_dangerous_calls_rejected(self):
        for src in DANGER_IMPLS:
            self.assertTrue(check_danger(src), f"not flagged: {src!r}")

    def test_clean_impl_no_danger(self):
        self.assertEqual(check_danger(CLEAN_IMPL), [])


class TestDeadArgs(EnvTestCase):
    def test_ignored_argument_flagged(self):
        issues = check_dead_args(DEAD_ARG_IMPL, "bad_prim")
        self.assertIn("parameter 'name' is declared but never used", issues)

    def test_used_arguments_clean(self):
        self.assertEqual(check_dead_args(CLEAN_IMPL, "clean_prim"), [])


class TestContractFunction(EnvTestCase):
    def test_missing_function_flagged(self):
        from friday.automated_gate import check_contract_function

        self.assertTrue(check_contract_function("x = 1\n", "missing_fn"))

    def test_present_function_clean(self):
        from friday.automated_gate import check_contract_function

        self.assertEqual(check_contract_function(CLEAN_IMPL, "clean_prim"), [])


class TestCombinedAst(EnvTestCase):
    def test_clean_impl_passes_all(self):
        self.assertEqual(check_impl_ast(CLEAN_IMPL, "clean_prim"), [])

    def test_dead_arg_surfaces(self):
        self.assertIn("never used", check_impl_ast(DEAD_ARG_IMPL, "bad_prim")[0])

    def test_subprocess_call_surfaces_even_with_allowed_import(self):
        src = "import subprocess\n\ndef f(name):\n    return subprocess.run([name])\n"
        issues = check_impl_ast(src, "f")
        self.assertTrue(any("subprocess.run" in i for i in issues), issues)


class TestSandbox(EnvTestCase):
    def _proposal_files(self, impl: str, test: str, name: str) -> tuple[Path, Path]:
        d = self.mktmp(prefix="friday_gate_")
        impl_path = d / "impl.py"
        impl_path.write_text(impl, encoding="utf-8")
        test_path = d / "test.py"
        test_path.write_text(test, encoding="utf-8")
        return impl_path, test_path

    def _adder_test(self) -> str:
        return (
            "import unittest\n"
            "from friday.l1.demo_adder import adder\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        self.assertEqual(adder(2, 3), 5)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )

    def test_passing_test_runs_in_sandbox(self):
        impl, test = self._proposal_files(
            "def adder(a: int, b: int) -> int:\n    return a + b\n",
            self._adder_test(),
            "demo_adder.adder",
        )
        ok, summary = run_sandbox_test(impl, test, "demo_adder.adder", timeout_s=30)
        self.assertTrue(ok, summary)
        self.assertIn("PASSED", summary)

    def test_failing_test_rejected(self):
        impl, test = self._proposal_files(
            "def adder(a: int, b: int) -> int:\n    return a - b\n",
            self._adder_test(),
            "demo_adder.adder",
        )
        ok, summary = run_sandbox_test(impl, test, "demo_adder.adder", timeout_s=30)
        self.assertFalse(ok)
        self.assertIn("FAILED", summary)

    def test_draft_is_what_gets_tested_not_the_registered_function(self):
        """The sandbox injects the DRAFT over the real module - a draft that
        changes behavior must be what the test exercises (existing module)."""
        impl, test = self._proposal_files(
            "def find_file_exact(name: str, directory: str | None = None) -> str:\n"
            '    return "DRAFT_RAN"\n',
            "import unittest\n"
            "from friday.l1.files import find_file_exact\n"
            "class T(unittest.TestCase):\n"
            "    def test_draft(self):\n"
            "        self.assertEqual(find_file_exact(\"x\"), \"DRAFT_RAN\")\n",
            "files.find_file_exact",
        )
        ok, summary = run_sandbox_test(impl, test, "files.find_file_exact", timeout_s=30)
        self.assertTrue(ok, summary)

    def test_package_level_import_style_sees_the_draft(self):
        """Regression (2026-08-13 live): a draft whose test uses the
        package-level style `from friday.l1 import files` was false-rejected
        - that style binds the package ATTRIBUTE (set by the earlier real
        import), never consulting sys.modules, so the old copy-and-swap
        injection was bypassed ('module friday.l1.files has no attribute
        write_text'). The draft must be exec'd IN PLACE so every import
        style resolves to it."""
        impl, test = self._proposal_files(
            "def find_file_exact(name: str, directory: str | None = None) -> str:\n"
            '    return "PACKAGE_STYLE_RAN"\n',
            "import unittest\n"
            "from friday.l1 import files\n"
            "class T(unittest.TestCase):\n"
            "    def test_draft(self):\n"
            "        self.assertEqual(files.find_file_exact(\"x\"), \"PACKAGE_STYLE_RAN\")\n",
            "files.find_file_exact",
        )
        ok, summary = run_sandbox_test(impl, test, "files.find_file_exact", timeout_s=30)
        self.assertTrue(ok, summary)

    def test_missing_test_file_is_documented_skip(self):
        impl = self.mktmp() / "impl.py"
        impl.write_text(CLEAN_IMPL, encoding="utf-8")
        ok, summary = run_sandbox_test(impl, self.mktmp() / "nope.py", "demo.sk", timeout_s=30)
        self.assertTrue(ok)
        self.assertIn("skipped", summary)


class TestFsScope(EnvTestCase):
    """The sandbox filesystem hole: literal file-WRITE calls whose path
    escapes the sandbox (absolute / '..' / '~') are rejected; relative
    writes (which land in the sandbox cwd) are allowed; reads stay a
    documented limit; runtime-built paths are not statically caught."""

    def test_absolute_open_write_rejected(self):
        src = 'def f():\n    open("/etc/cron.d/x", "w").write("x")\n'
        issues = check_fs_scope(src)
        self.assertTrue(issues)
        self.assertIn("outside the sandbox", issues[0])

    def test_dotdot_traversal_rejected(self):
        src = 'def f():\n    open("../evil", "w").write("x")\n'
        self.assertTrue(check_fs_scope(src))

    def test_home_expansion_rejected(self):
        src = 'def f():\n    open("~/escape", "w").write("x")\n'
        self.assertTrue(check_fs_scope(src))

    def test_relative_write_allowed(self):
        src = 'def f():\n    open("out.txt", "w").write("x")\n'
        self.assertEqual(check_fs_scope(src), [])

    def test_path_method_absolute_write_rejected(self):
        src = 'def f():\n    Path("/tmp/x").write_text("y")\n'
        self.assertTrue(check_fs_scope(src))

    def test_path_method_relative_write_allowed(self):
        self.assertEqual(check_fs_scope('def f():\n    Path("out.txt").write_text("y")\n'), [])

    def test_path_join_traversal_rejected(self):
        src = (
            'def f():\n'
            '    Path("a") / ".." / "x"\n'
            '    Path("a") / "../x"\n'
            '    (Path("a") / ".." / "x").write_text("y")\n'
        )
        self.assertTrue(check_fs_scope(src))

    def test_os_remove_absolute_rejected(self):
        src = 'def f():\n    import os\n    os.remove("/etc/passwd")\n'
        self.assertTrue(check_fs_scope(src))

    def test_os_open_absolute_rejected(self):
        """os.open(path, flags) with a WRITE flag - the path must stay in the sandbox."""
        src = 'def f():\n    import os\n    os.open("/tmp/evil", os.O_WRONLY | os.O_CREAT)\n'
        self.assertTrue(check_fs_scope(src))

    def test_os_open_readonly_absolute_allowed(self):
        """os.open(path, os.O_RDONLY) is a READ - reads are a documented
        limit, not a sandbox escape (no false positive)."""
        src = 'def f():\n    import os\n    os.open("/etc/passwd", os.O_RDONLY)\n'
        self.assertEqual(check_fs_scope(src), [])

    def test_path_open_keyword_mode_absolute_rejected(self):
        """Path.open(mode=...) with the mode as a KEYWORD is a write too."""
        src = 'def f():\n    Path("/tmp/evil").open(mode="w").write("x")\n'
        self.assertTrue(check_fs_scope(src))

    def test_read_absolute_not_flagged(self):
        """The sandbox FS check targets WRITES; reads of local files remain
        a documented known limit (full OS-level isolation is aspirational)."""
        self.assertEqual(check_fs_scope('def f():\n    open("/etc/passwd").read()\n'), [])

    def test_dynamic_path_not_statically_flagged(self):
        self.assertEqual(check_fs_scope('def f(p):\n    open(p, "w").write("x")\n'), [])


class TestEnvSanitization(EnvTestCase):
    def test_credentials_and_overrides_stripped(self):
        os.environ["WHATSAPP_ACCESS_TOKEN"] = "w-secret"
        os.environ["FRIDAY_ALLOW_DANGEROUS"] = "1"
        os.environ["FRIDAY_LOG_FILE"] = "/real/log.jsonl"
        sandbox = Path("/tmp/sandbox")
        env = _sanitized_env(sandbox)
        # credential-bearing and gate-flag vars are STRIPPED entirely...
        for key in ("WHATSAPP_ACCESS_TOKEN", "FRIDAY_ALLOW_DANGEROUS"):
            self.assertNotIn(key, env, key)
        # ...while FRIDAY_* logging/triage vars are REDIRECTED to the sandbox
        self.assertEqual(env["FRIDAY_LOG_FILE"], "/tmp/sandbox/log.jsonl")
        self.assertEqual(env["FRIDAY_GAPS_FILE"], "/tmp/sandbox/gaps.jsonl")
        self.assertEqual(env["HOME"], "/tmp/sandbox")
        # tempfile inside the sandbox must land in the sandbox, never the
        # real /tmp (mkstemp/NamedTemporaryFile are not statically catchable)
        for k in ("TMPDIR", "TMP", "TEMP"):
            self.assertEqual(env[k], "/tmp/sandbox", k)


class TestBuildVerify(EnvTestCase):
    """The build stage: the DRAFT function runs against REAL harmless
    targets (files.*) after its own test.py passed - catching drafts whose
    self-authored test passes but whose impl is wrong on first real
    invocation. Other module classes are honestly flagged not-applicable."""

    CONTRACT = {
        "name": "files.find_file_exact",
        "precondition": "name is a non-empty string; directory (if given) exists.",
        "postcondition": "Returns the absolute path of the first exact filename match, or '' when absent.",
        "idempotency": "idempotent",
        "failure_mode": "PreconditionError for a missing directory.",
        "returns": "str",
    }

    def _proposal(self, impl: str, test: str) -> Path:
        d = self.mktmp(prefix="friday_gate_")
        (d / "contract.json").write_text(__import__("json").dumps(self.CONTRACT), encoding="utf-8")
        (d / "impl.py").write_text(impl, encoding="utf-8")
        (d / "test.py").write_text(test, encoding="utf-8")
        (d / "rationale.md").write_text("# rationale\n", encoding="utf-8")
        return d

    @staticmethod
    def _test(body: str) -> str:
        indented = "\n".join("            " + ln for ln in body.splitlines())
        return (
            "import unittest\n"
            "import tempfile\n"
            "from pathlib import Path\n"
            "from friday.l1.files import find_file_exact\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            f"{indented}\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )

    def test_catches_test_passes_but_impl_wrong(self):
        """The draft's own test passes (isinstance str) yet its impl returns
        the bare NAME, not the real path - build-verify catches it."""
        impl = (
            "def find_file_exact(name: str, directory: str | None = None) -> str:\n"
            '    base = directory or "."\n'
            "    return name  # wrong: ignores the lookup, returns the input\n"
        )
        test = self._test(
            "d = tempfile.mkdtemp()\n"
            "Path(d, 'report.pdf').write_text('x')\n"
            "self.assertIsInstance(find_file_exact('report.pdf', d), str)"
        )
        d = self._proposal(impl, test)
        ok, lines = run_automated_gate(d, contract=self.CONTRACT, impl_src=impl)
        self.assertFalse(ok, lines)
        joined = "\n".join(lines)
        self.assertIn("build-verify: REJECT", joined, lines)
        self.assertIn("expected path", joined, lines)
        rationale = (d / "rationale.md").read_text(encoding="utf-8")
        self.assertIn("build-verify: REJECT", rationale)

    def test_correct_draft_passes_both_stages(self):
        impl = (
            "from pathlib import Path\n"
            "from friday.errors import PreconditionError\n"
            "def find_file_exact(name: str, directory: str | None = None) -> str:\n"
            '    base = Path(directory) if directory else Path(".")\n'
            "    if not base.is_dir():\n"
            "        raise PreconditionError(f'directory does not exist: {base}')\n"
            "    matches = sorted((p for p in base.iterdir() if p.is_file() and p.name == name), key=str)\n"
            "    return str(matches[0]) if matches else ''\n"
        )
        test = self._test(
            "d = tempfile.mkdtemp()\n"
            "Path(d, 'report.pdf').write_text('x')\n"
            "self.assertEqual(find_file_exact('report.pdf', d), str(Path(d, 'report.pdf')))"
        )
        d = self._proposal(impl, test)
        ok, lines = run_automated_gate(d, contract=self.CONTRACT, impl_src=impl)
        self.assertTrue(ok, lines)
        self.assertTrue(any("build-verify: PASS" in l for l in lines), lines)

    def test_wrong_return_shape_rejected(self):
        """Returns a Path object (not str) - the present-name probe's exact
        type check catches it even though the self-test only checks
        is-not-None."""
        impl = (
            "from pathlib import Path\n"
            "def find_file_exact(name: str, directory: str | None = None) -> str:\n"
            '    base = Path(directory) if directory else Path(".")\n'
            "    for p in base.iterdir():\n"
            "        if p.is_file() and p.name == name:\n"
            "            return p  # Path, not str - wrong return shape\n"
            "    return ''\n"
        )
        test = self._test(
            "d = tempfile.mkdtemp()\n"
            "Path(d, 'report.pdf').write_text('x')\n"
            "self.assertIsNotNone(find_file_exact('report.pdf', d))"
        )
        d = self._proposal(impl, test)
        ok, lines = run_automated_gate(d, contract=self.CONTRACT, impl_src=impl)
        self.assertFalse(ok, lines)
        self.assertTrue(any("build-verify: REJECT" in l for l in lines), lines)

    WRITE_CONTRACT = {
        "name": "files.write_text",
        "precondition": "path is a non-empty string; text is a str; the parent directory exists.",
        "postcondition": "Creates or overwrites (or appends to) the file at path with the given text.",
        "idempotency": "commutative-safe",
        "failure_mode": "PreconditionError when the parent directory does not exist.",
        "returns": "str: the absolute path of the written file.",
    }

    GOOD_WRITE_IMPL = (
        "from pathlib import Path\n"
        "from friday.errors import PreconditionError\n"
        "def write_text(path: str, text: str, *, append: bool = False) -> str:\n"
        "    p = Path(path)\n"
        "    if not p.parent.is_dir():\n"
        "        raise PreconditionError(f'parent does not exist: {p.parent}')\n"
        "    mode = 'a' if append else 'w'\n"
        "    with p.open(mode, encoding='utf-8') as f:\n"
        "        f.write(text)\n"
        "    return str(p)\n"
    )

    @staticmethod
    def _write_test(body: str) -> str:
        indented = "\n".join("            " + ln for ln in body.splitlines())
        return (
            "import unittest\n"
            "import tempfile\n"
            "from pathlib import Path\n"
            "from friday.l1.files import write_text\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            f"{indented}\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )

    def _write_proposal(self, impl: str, test: str) -> Path:
        d = self.mktmp(prefix="friday_gate_")
        (d / "contract.json").write_text(
            __import__("json").dumps(self.WRITE_CONTRACT), encoding="utf-8")
        (d / "impl.py").write_text(impl, encoding="utf-8")
        (d / "test.py").write_text(test, encoding="utf-8")
        (d / "rationale.md").write_text("# rationale\n", encoding="utf-8")
        return d

    def test_probe_family_detection(self):
        """Fix 2: the probe family is derived from the DRAFT's declared
        params, never assumed from the module name."""
        self.assertEqual(_build_probe_family("find_file_exact", ["name", "directory"]), "read")
        self.assertEqual(_build_probe_family("write_text", ["path", "text", "append"]), "write")
        self.assertEqual(_build_probe_family("mystery", ["x", "y"]), "none")

    def test_correct_write_draft_passes_build_verify(self):
        """A genuinely correct write_text draft passes the write probes:
        file created with exact content, overwritten by a second write,
        appended when append=True, errors stay FridayError."""
        test = self._write_test(
            "d = tempfile.mkdtemp()\n"
            "p = str(Path(d, 'notes.md'))\n"
            "r = write_text(p, 'hello')\n"
            "self.assertIsInstance(r, str)\n"
            "self.assertEqual(Path(p).read_text(), 'hello')"
        )
        d = self._write_proposal(self.GOOD_WRITE_IMPL, test)
        ok, lines = run_automated_gate(d, contract=self.WRITE_CONTRACT, impl_src=self.GOOD_WRITE_IMPL)
        self.assertTrue(ok, lines)
        self.assertTrue(any("build-verify: PASS" in l and "write probes" in l for l in lines), lines)

    def test_write_draft_that_appends_when_it_should_overwrite_is_caught(self):
        """The draft's own test passes (writes once, checks content) but the
        impl always appends - the build-verify OVERWRITE probe (second write
        must REPLACE, not concatenate) catches it mechanically."""
        impl = (
            "from pathlib import Path\n"
            "from friday.errors import PreconditionError\n"
            "def write_text(path: str, text: str, *, append: bool = False) -> str:\n"
            "    p = Path(path)\n"
            "    if not p.parent.is_dir():\n"
            "        raise PreconditionError(f'parent does not exist: {p.parent}')\n"
            "    mode = 'a' if append else 'a'  # WRONG: ignores the flag, always appends\n"
            "    with p.open(mode, encoding='utf-8') as f:\n"
            "        f.write(text)\n"
            "    return str(p)\n"
        )
        test = self._write_test(
            "d = tempfile.mkdtemp()\n"
            "p = str(Path(d, 'notes.md'))\n"
            "r = write_text(p, 'hello')\n"
            "self.assertIsInstance(r, str)\n"
            "self.assertEqual(Path(p).read_text(), 'hello')"
        )
        d = self._write_proposal(impl, test)
        ok, lines = run_automated_gate(d, contract=self.WRITE_CONTRACT, impl_src=impl)
        self.assertFalse(ok, lines)
        joined = "\n".join(lines)
        self.assertIn("build-verify: REJECT", joined, lines)
        self.assertIn("content mismatch", joined, lines)

    def test_write_draft_without_append_param_still_passes(self):
        """The append probe is conditional on the DRAFT declaring append -
        a write_text without it must not be false-rejected by passing an
        unexpected kwarg."""
        impl = (
            "from pathlib import Path\n"
            "from friday.errors import PreconditionError\n"
            "def write_text(path: str, text: str) -> str:\n"
            "    p = Path(path)\n"
            "    if not p.parent.is_dir():\n"
            "        raise PreconditionError(f'parent does not exist: {p.parent}')\n"
            "    with p.open('w', encoding='utf-8') as f:\n"
            "        f.write(text)\n"
            "    return str(p)\n"
        )
        test = self._write_test(
            "d = tempfile.mkdtemp()\n"
            "p = str(Path(d, 'notes.md'))\n"
            "r = write_text(p, 'hello')\n"
            "self.assertIsInstance(r, str)\n"
            "self.assertEqual(Path(p).read_text(), 'hello')"
        )
        d = self._write_proposal(impl, test)
        ok, lines = run_automated_gate(d, contract=self.WRITE_CONTRACT, impl_src=impl)
        self.assertTrue(ok, lines)
        self.assertTrue(any("build-verify: PASS" in l and "write probes" in l for l in lines), lines)

    def test_not_applicable_class_is_honestly_flagged(self):
        """demo.adder has no safe real target - the gate does NOT pretend it
        passed; it states 'not applicable, human review required' and the
        proposal may still proceed (AST + sandbox passed)."""
        contract = {
            "name": "demo.adder",
            "precondition": "a, b are ints.",
            "postcondition": "returns the sum.",
            "idempotency": "idempotent",
            "failure_mode": "f",
            "returns": "int",
        }
        d = self.mktmp(prefix="friday_gate_")
        (d / "contract.json").write_text(__import__("json").dumps(contract), encoding="utf-8")
        impl = "def adder(a: int, b: int) -> int:\n    return a + b\n"
        (d / "impl.py").write_text(impl, encoding="utf-8")
        (d / "test.py").write_text(
            "import unittest\n"
            "from friday.l1.demo import adder\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        self.assertEqual(adder(1, 2), 3)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            encoding="utf-8",
        )
        (d / "rationale.md").write_text("# rationale\n", encoding="utf-8")
        ok, lines = run_automated_gate(d, contract=contract, impl_src=impl)
        self.assertTrue(ok, lines)
        self.assertTrue(any("NOT APPLICABLE" in l and "human review required" in l for l in lines), lines)
        rationale = (d / "rationale.md").read_text(encoding="utf-8")
        self.assertIn("NOT APPLICABLE", rationale)


class TestRunAutomatedGate(EnvTestCase):
    def _proposal(self, impl: str, test: str, contract: dict) -> Path:
        d = self.mktmp(prefix="friday_gate_")
        (d / "contract.json").write_text(__import__("json").dumps(contract), encoding="utf-8")
        (d / "impl.py").write_text(impl, encoding="utf-8")
        (d / "test.py").write_text(test, encoding="utf-8")
        (d / "rationale.md").write_text("# rationale\n", encoding="utf-8")
        return d

    GOOD_CONTRACT = {
        "name": "demo.adder",
        "precondition": "a, b are ints.",
        "postcondition": "returns the sum.",
        "idempotency": "idempotent",
        "failure_mode": "f",
        "returns": "int",
    }

    def _good_test(self) -> str:
        return (
            "import unittest\n"
            "from friday.l1.demo import adder\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        self.assertEqual(adder(1, 2), 3)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n"
        )

    def test_clean_proposal_passes_and_reports_to_rationale(self):
        d = self._proposal(
            "def adder(a: int, b: int) -> int:\n    return a + b\n",
            self._good_test(),
            self.GOOD_CONTRACT,
        )
        ok, lines = run_automated_gate(d, contract=self.GOOD_CONTRACT, impl_src=(d / "impl.py").read_text())
        self.assertTrue(ok, lines)
        rationale = (d / "rationale.md").read_text(encoding="utf-8")
        self.assertIn("Automated gate", rationale)
        self.assertIn("AST checks: passed", rationale)
        self.assertIn("sandbox: PASS", rationale)

    def test_bad_import_fails_before_any_signature_consideration(self):
        d = self._proposal(
            "import numpy\n\ndef adder(a: int, b: int) -> int:\n    return a + b\n",
            self._good_test(),
            self.GOOD_CONTRACT,
        )
        ok, lines = run_automated_gate(d, contract=self.GOOD_CONTRACT, impl_src=(d / "impl.py").read_text())
        self.assertFalse(ok)
        self.assertTrue(any("AST REJECT" in l for l in lines), lines)
        rationale = (d / "rationale.md").read_text(encoding="utf-8")
        self.assertIn("AST REJECT", rationale)

    def test_dead_argument_fails(self):
        d = self._proposal(
            "def adder(a: int, b: int) -> int:\n    return 42\n",
            self._good_test(),
            self.GOOD_CONTRACT,
        )
        ok, lines = run_automated_gate(d, contract=self.GOOD_CONTRACT, impl_src=(d / "impl.py").read_text())
        self.assertFalse(ok)
        self.assertTrue(any("never used" in l for l in lines), lines)

    def test_dangerous_test_file_rejected_before_execution(self):
        """The file the sandbox EXECUTES is itself AST-checked - a clean
        impl cannot smuggle a dangerous test.py past the gate."""
        d = self._proposal(
            "def adder(a: int, b: int) -> int:\n    return a + b\n",
            "import os\n"
            "import unittest\n"
            "from friday.l1.demo import adder\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        os.system('true')\n"
            "        self.assertEqual(adder(1, 2), 3)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            self.GOOD_CONTRACT,
        )
        ok, lines = run_automated_gate(d, contract=self.GOOD_CONTRACT, impl_src=(d / "impl.py").read_text())
        self.assertFalse(ok)
        self.assertTrue(any("test.py AST REJECT" in l for l in lines), lines)
        self.assertTrue(any("os.system" in l for l in lines), lines)

    def test_gate_rejects_absolute_write_in_test_file(self):
        """A test.py that writes an absolute path is rejected before the
        sandbox runs it - the executed file is not trusted code."""
        d = self._proposal(
            "def adder(a: int, b: int) -> int:\n    return a + b\n",
            "import unittest\n"
            "from friday.l1.demo import adder\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        open('/etc/cron.d/x', 'w').write('x')\n"
            "        self.assertEqual(adder(1, 2), 3)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            self.GOOD_CONTRACT,
        )
        ok, lines = run_automated_gate(d, contract=self.GOOD_CONTRACT, impl_src=(d / "impl.py").read_text())
        self.assertFalse(ok)
        self.assertTrue(any("outside the sandbox" in l for l in lines), lines)

    def test_gate_allows_relative_write_inside_sandbox(self):
        """A relative write lands in the sandbox cwd and is both allowed by
        the AST check and exercised by the sandboxed test run."""
        d = self._proposal(
            "def adder(a: int, b: int) -> int:\n    return a + b\n",
            "import unittest\n"
            "from pathlib import Path\n"
            "from friday.l1.demo import adder\n"
            "class T(unittest.TestCase):\n"
            "    def test_ok(self):\n"
            "        Path('out.txt').write_text('x')\n"
            "        self.assertTrue(Path('out.txt').is_file())\n"
            "        self.assertEqual(adder(1, 2), 3)\n"
            "if __name__ == '__main__':\n"
            "    unittest.main()\n",
            self.GOOD_CONTRACT,
        )
        ok, lines = run_automated_gate(d, contract=self.GOOD_CONTRACT, impl_src=(d / "impl.py").read_text())
        self.assertTrue(ok, lines)


if __name__ == "__main__":
    unittest.main()
