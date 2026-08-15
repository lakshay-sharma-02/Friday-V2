"""automated_gate - the mechanical checks that run BEFORE a human signs a
capability-gap proposal (friday/register_proposal.py).

The gap loop's earlier round proved the mechanism with a manual-only gate
(APPROVED.md signature). This module makes the review step mechanical:

  AST checks (friday/automated_gate.py, this file)
    - imports:      only modules the shipped L1 primitives actually import
                    (derived below), plus a small documented stdlib set
    - danger calls: exec/eval/compile/__import__, any subprocess.* call
                    EXCEPT the bounded pattern the shipped primitives
                    use for external tool I/O - the READ shape
                    (subprocess.run([...], capture_output=True,
                    timeout=...)) for reads and the WRITE shape
                    (subprocess.run([...], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL, timeout=...)) for writes,
                    because wl-copy/xclip fork a daemon that inherits pipe
                    fds and capture_output then blocks EOF forever (see
                    _is_safe_subprocess_run; without this carve-out a
                    genuine clipboard primitive could never be drafted,
                    since reading/writing the Linux clipboard REQUIRES
                    wl-paste/xclip/wl-copy),
                    os.system/os.popen/os.spawn*/os.exec*/os.fork, pty.spawn
                    (mirrors what the shipped executor gates already treat
                    as dangerous - there was NO reusable danger list, so
                    this set is derived here, documented, and strict)
    - contract fn:  the impl must define the function named by the contract
    - dead args:    every declared parameter must be used in the body (the
                    exact defect a human caught by hand last round: an impl
                    that ignored its own `name` argument)
    - decorator:    the contracted function MUST be decorated with @contract(...)
                    (a missing decorator = the primitive never enters REGISTRY;
                    observed live on the clipboard draft, 2026-08-14)
    - consistency:  every log_transform the contract names must be defined by
                    the impl (an undefined one is a NameError at import); no
                    bare-builtin raises (RuntimeError/...) the contract never
                    declares - the executor's retry policy keys on FridayError

  Sandboxed test run
    - test.py is danger-checked (exec/eval/subprocess/os-system/dev.run)
      BEFORE it is executed - the file the sandbox runs is not trusted
      code. Imports are NOT restricted in test.py (tests legitimately
      import unittest/tempfile); the sandbox env carries no credentials
      and no claude CLI.
    - the proposal's own test.py then runs in an isolated subprocess: a
      temp HOME and temp cwd (tempfile.TemporaryDirectory), no credential
      env vars, all FRIDAY_*/WHATSAPP_*/TELEGRAM_*/DISCORD_*/GITHUB_
      vars stripped, any PATH entry that contains the claude CLI removed,
      temp log/gap/tasks paths, a timeout, and the DRAFT impl injected
      over friday.l1.<module> so the tests exercise the draft, not
      whatever is currently registered.
    - fs-scope (check_fs_scope): literal file-WRITE calls (open 'w/a/x',
      os.remove/os.rename/..., shutil.*, Path(...).write_*/open) must not
      target an absolute path, '~' expansion, or a '..' traversal - the
      sandbox can only write inside its own temp dir. Applied to BOTH
      impl.py and test.py before either is executed (the sandbox never
      runs an AST-rejected draft's test).

  Registration check (check_registration)
    - After the impl AST passes, the DRAFT is executed in the same isolated
      subprocess and the contracted name must ACTUALLY land in REGISTRY.
      A draft that compiles and whose own test passes can still be DEAD ON
      ARRIVAL - the clipboard.read_text round (2026-08-14) produced exactly
      that: a self-check-clean draft whose impl had NO @contract decorator
      (registration wrote the file but the primitive never entered REGISTRY
      and the executor kept refusing it) and a contract declaring a
      log_transform the impl never defined (NameError at import). Both are
      structural and both are rejected here, before any human review.

Documented limits: network egress is NOT hard-blocked and file READS of
local paths are not restricted - with no credentials present and the
claude CLI removed from PATH, the live primitives cannot authenticate or
spend, but the sandbox is env-level, not OS-level (full
seccomp/containerization remains aspirational). A path built at runtime
(variables, tempfile calls) is not caught by the static fs-scope check.

  Build verification (run_build_verify)
    - After the sandboxed TEST run passes, the DRAFT function is executed
      against something resembling its real target - the self-authored
      test.py (which a draft's author could have written to trivially
      pass) is not the only check.
    - files.* READ-family (declares a name/pattern param): REAL harmless
      targets - a temp dir with a real file. The present-name probe must
      return that EXACT absolute path; the absent-name probe must return
      a str; a missing directory may raise FridayError but nothing else.
      A draft that returns the bare name, ignores directory, or returns
      a non-str is caught here.
    - files.* WRITE-family (declares a path-ish AND a content-ish param,
      e.g. files.write_text(path, text) - 2026-08-13): REAL harmless
      targets in the same temp dir. Probes call the DRAFT with absolute
      sandbox paths and VERIFY THE FILE ON DISK: created with the exact
      content, overwritten by a second write, appended when the fn
      declares an append param, and error probes (missing parent /
      empty path) that may raise FridayError but nothing else. A draft
      that returns a non-str, writes nothing, writes the wrong content,
      appends when it should overwrite (or vice versa), or crashes with
      a non-FridayError is caught here - regardless of what its
      self-authored test asserted.
    - files.* that declares neither family -> honest not-applicable
      (never probed blind).
    - SUBPROCESS-READ family (clipboard.read_text shape, 2026-08-14): a
      non-files module whose impl shells out through the bounded
      subprocess.run pattern with a no-arg contracted fn gets probes with a
      MOCKED external tool: success -> str result; tool failure and timeout
      -> FridayError, never a bare builtin (the RuntimeError defect a human
      hand-corrected on the clipboard draft). Reading the real clipboard
      under the sandbox would be meaningless, but the impl's error-class
      behavior is probeable - the exact gap that previously forced a human
      to hand-fix the draft.
    - other module classes: no safe real target in this session -> an
      HONEST "build-verification not applicable, human review required"
      report line, never a silent skip or a pretended pass.

A failed check writes its reason into rationale.md automatically (the
file is created if the draft never wrote one) and the proposal NEVER
reaches the human signature. The gate is structural only: it cannot
catch logically-wrong-but-syntactically-clean code - a human still
reviews the diff and signs APPROVED.md. Caveat: a test that calls
importlib.reload on the injected module would re-read the real file
from disk and bypass the draft injection - edge case, documented, not
engineered against.
"""

from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from friday.lessons import record_lesson_event

PROJECT_ROOT = Path(__file__).resolve().parents[1]
L1_DIR = PROJECT_ROOT / "friday" / "l1"

DEFAULT_SANDBOX_TIMEOUT_S = 30

# ---------------------------------------------------------------- allowlists
#
# The import allowlist is DERIVED from what the shipped L1 primitives
# actually import (friday/l1/*.py): stdlib base64/json/os/time/pathlib/
# typing/signal/socket/subprocess/threading/re, third-party requests and
# playwright, and the friday package itself. The EXTRA set below is a
# small, documented addition of pure-compute stdlib modules a legitimate
# draft is likely to need; everything else is rejected. Extend either set
# deliberately, not by default. test_automated_gate asserts the observed
# real imports stay within the allowlist.
_OBSERVED_STDLIB = frozenset(
    {"__future__", "base64", "fnmatch", "json", "os", "re", "signal", "socket",
     "subprocess", "threading", "time", "pathlib", "typing"}
)
_OBSERVED_THIRD_PARTY = frozenset({"requests", "playwright"})
_EXTRA_SAFE_STDLIB = frozenset(
    {"collections", "dataclasses", "datetime", "email", "enum", "functools",
     "io", "itertools", "math", "string", "uuid"}
)
# 'email' was added deliberately for the hand-built gmail.send_document
# proposal (2026-08-11): pure MIME message/attachment construction for the
# Gmail API send endpoint - no network, exec, shell or filesystem of its
# own. A draft that imports email but does anything beyond MIME assembly
# is still caught by the danger / fs-scope passes.
ALLOWED_IMPORTS = frozenset(
    _OBSERVED_STDLIB | _OBSERVED_THIRD_PARTY | _EXTRA_SAFE_STDLIB | {"friday"}
)

# Danger calls mirroring what the shipped gates already treat as dangerous
# (dev.run_shell / dev.run(allow_bypass_permissions=True) behind
# FRIDAY_ALLOW_DANGEROUS=1, EXECUTOR_BLOCKED primitives): arbitrary
# execution and shell. No reusable list existed in the repo - this set is
# the derived, documented mirror.
_DANGER_BUILTINS = frozenset({"exec", "eval", "compile", "__import__", "input"})
_DANGER_ATTRS = frozenset({
    "os.system", "os.popen", "os.fork", "os.startfile",
    "os.spawnl", "os.spawnle", "os.spawnlp", "os.spawnlpe",
    "os.spawnv", "os.spawnve", "os.spawnvp", "os.spawnvpe",
    "os.execl", "os.execle", "os.execlp", "os.execlpe",
    "os.execv", "os.execve", "os.execvp", "os.execvpe",
    "pty.spawn",
    # the paid, side-effecting claude subprocess - a draft or its test
    # must never reach it
    "dev.run", "dev.run_shell", "friday.l1.dev.run", "friday.l1.dev.run_shell",
})


# --------------------------------------------------------------- AST checks


def _dotted_name(node: ast.AST) -> str:
    """subprocess.run / os.system -> 'subprocess.run' (best effort)."""
    parts: list[str] = []
    cur: ast.AST | None = node
    while isinstance(cur, ast.Attribute):
        parts.append(cur.attr)
        cur = cur.value
    if isinstance(cur, ast.Name):
        parts.append(cur.id)
    return ".".join(reversed(parts))


def check_imports(source: str) -> list[str]:
    """Every top-level import must be in the derived L1 allowlist."""
    issues: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return issues  # unparseable source is reported by validate_impl
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                if top not in ALLOWED_IMPORTS:
                    issues.append(
                        f"imports {alias.name!r} - top-level {top!r} is not in "
                        "the derived L1 import allowlist"
                    )
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            if top and top not in ALLOWED_IMPORTS:
                issues.append(
                    f"imports {node.module!r} - top-level {top!r} is not in "
                    "the derived L1 import allowlist"
                )
    return issues


# File-write targets that must never escape the sandbox: absolute paths,
# '..' traversal segments, or '~' expansion (HOME is redirected to the
# sandbox only while the sandbox holds - defense in depth). Relative
# writes land in the sandbox cwd and are allowed. Only statically-
# resolvable literal paths are caught - a path built at runtime (variables,
# tempfile calls) is not caught by this AST check (documented limit;
# full OS-level isolation remains aspirational).
_FS_WRITE_OS = frozenset({
    "os.remove", "os.unlink", "os.rmdir", "os.mkdir", "os.makedirs",
    "os.rename", "os.replace", "os.open",
})
_FS_WRITE_SHUTIL = frozenset({
    "shutil.move", "shutil.copy", "shutil.copy2", "shutil.copytree",
    "shutil.rmtree", "shutil.copyfile",
})
_PATH_WRITE_METHODS = frozenset({
    "write_text", "write_bytes", "touch", "unlink", "mkdir", "rename",
    "replace", "rmdir", "open",
})


def _path_literal(node: ast.AST) -> str | None:
    """Best-effort literal path from a string constant, Path('x'), or a
    Path('x') / 'y' join chain. None when not statically resolvable."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Call):
        if node.args and isinstance(node.func, ast.Name) and node.func.id in (
            "Path", "PurePath", "PurePosixPath", "PureWindowsPath"
        ):
            return _path_literal(node.args[0])
        return None
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        left = _path_literal(node.left)
        right = _path_literal(node.right)
        if left is not None and right is not None and not os.path.isabs(right):
            return left.rstrip("/") + "/" + right.lstrip("/")
    return None


def _unsafe_path(p: str) -> bool:
    """Absolute, '~'-expanding, or containing a '..' traversal segment."""
    if p.startswith("~"):
        return True
    if os.path.isabs(p):
        return True
    return any(seg == ".." for seg in p.split("/"))


def check_fs_scope(source: str) -> list[str]:
    """Reject literal file-WRITE calls whose path escapes the sandbox dir:
    open(..., 'w'/'a'/'x'), os.remove/os.rename/..., shutil.*, and
    Path(...).write_*/open('w') style calls on absolute / '..' / '~'
    paths. Relative writes (which land in the sandbox cwd) are allowed;
    reads are NOT restricted (that stays a documented limit)."""
    issues: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return issues
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id == "open":
            if len(node.args) >= 2 and isinstance(node.args[1], ast.Constant) \
                    and isinstance(node.args[1].value, str) \
                    and any(c in node.args[1].value for c in "wax+"):
                p = _path_literal(node.args[0])
                if p and _unsafe_path(p):
                    issues.append(
                        f"open({p!r}, {node.args[1].value!r}) writes outside the "
                        "sandbox (absolute / '..' / '~')"
                    )
            continue
        if isinstance(fn, ast.Attribute):
            dotted = _dotted_name(fn)
            if dotted in _FS_WRITE_OS or dotted in _FS_WRITE_SHUTIL:
                # os.open(path, flags): only a WRITE intent (O_WRONLY/O_RDWR/
                # O_APPEND/O_CREAT/O_TRUNC in the flags) is a sandbox escape -
                # os.open(path, os.O_RDONLY) is a read and must not be
                # false-flagged. Unresolvable flags stay conservative (flagged).
                if dotted == "os.open" and len(node.args) >= 2:
                    flag_names = {
                        a.attr for a in ast.walk(node.args[1])
                        if isinstance(a, ast.Attribute)
                    }
                    if not (flag_names & {"O_WRONLY", "O_RDWR", "O_APPEND", "O_CREAT", "O_TRUNC"}):
                        continue  # read-only os.open - allowed
                if node.args:
                    p = _path_literal(node.args[0])
                    if p and _unsafe_path(p):
                        issues.append(f"{dotted}({p!r}) targets a path outside the sandbox")
                continue
            method = dotted.rsplit(".", 1)[-1]
            if method in _PATH_WRITE_METHODS:
                if method == "open":
                    # Path.open(mode=...): the mode may be the first positional
                    # arg OR a keyword - both are write-capable when they
                    # contain a write char (w/a/x/+).
                    mode = node.args[0] if node.args else None
                    for kw in node.keywords:
                        if kw.arg == "mode":
                            mode = kw.value
                    if not (isinstance(mode, ast.Constant) and isinstance(mode.value, str)
                            and any(c in mode.value for c in "wax+")):
                        continue  # Path.open without a write mode is a read
                p = _path_literal(fn.value)
                if p and _unsafe_path(p):
                    issues.append(f"{dotted} on {p!r} writes outside the sandbox")
    return issues


def _is_safe_subprocess_run(node: ast.Call) -> bool:
    """True ONLY for the bounded, statically-visible subprocess.run shapes
    the shipped L1 primitives use for external tool I/O:

      - READ shape:  subprocess.run([...], capture_output=True, timeout=...)
        (git.log, notify_send, _hyprctl, clipboard.read_text) - output is
        captured, never inherited.
      - WRITE shape: subprocess.run([...], input=<str>,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=...)
        - output is DISCARDED, never inherited. REQUIRED for write-family
        primitives like clipboard.write_text: wl-copy/xclip fork a daemon
        that inherits the child's pipe fds, so capture_output=True blocks
        EOF forever (the run only ends via its own timeout and every write
        fails) - discarding output is the only shape that completes.

    The carve-out exists because genuine clipboard primitives CANNOT exist
    on Linux without shelling out to wl-paste/xclip/wl-copy - the blanket
    'any subprocess.* call' rule (which also rejects the shipped pattern)
    made them undraftable. Everything else under subprocess.* stays
    rejected.
    Safety conditions (each is structural, not semantic):
      - the call target is exactly subprocess.run (not check_output,
        Popen, call, check_call, run with shell=True, ...)
      - the command is a list/tuple LITERAL of string constants - the
        whole command is visible in the draft source; a variable or a
        shell string hides what runs and is rejected
      - shell is absent or explicitly False
      - EITHER capture_output=True (read) OR BOTH stdout=subprocess.DEVNULL
        and stderr=subprocess.DEVNULL (write) - never both (subprocess
        itself rejects the contradictory mix at runtime), and never a
        partial DEVNULL (the remaining pipe would be inherited)
      - a timeout is present (bounded, never unbounded)
    A wrong-but-clean command (e.g. a destructive binary in the list) is
    still a HUMAN-review concern - the gate catches the structural
    escape (shell/string/variable/unbounded), exactly as documented for
    the write-family limits."""
    fn = node.func
    if not (isinstance(fn, ast.Attribute) and _dotted_name(fn) == "subprocess.run"):
        return False
    if not node.args:
        return False
    cmd = node.args[0]
    if not isinstance(cmd, (ast.List, ast.Tuple)):
        return False
    if not all(
        isinstance(e, ast.Constant) and isinstance(e.value, str) for e in cmd.elts
    ):
        return False
    capture_ok = False
    stdout_devnull = False
    stderr_devnull = False
    timeout_ok = False
    for kw in node.keywords:
        if kw.arg == "shell":
            if not (isinstance(kw.value, ast.Constant) and kw.value.value is False):
                return False
        elif kw.arg == "capture_output":
            capture_ok = (
                isinstance(kw.value, ast.Constant) and kw.value.value is True
            )
        elif kw.arg == "stdout":
            stdout_devnull = (
                isinstance(kw.value, ast.Attribute)
                and _dotted_name(kw.value) == "subprocess.DEVNULL"
            )
        elif kw.arg == "stderr":
            stderr_devnull = (
                isinstance(kw.value, ast.Attribute)
                and _dotted_name(kw.value) == "subprocess.DEVNULL"
            )
        elif kw.arg == "timeout":
            timeout_ok = True
    # capture_output=True and stdout/stderr=DEVNULL are mutually exclusive -
    # subprocess itself raises ValueError for the mix
    if capture_ok and (stdout_devnull or stderr_devnull):
        return False
    read_shape = capture_ok
    write_shape = stdout_devnull and stderr_devnull
    return timeout_ok and (read_shape or write_shape)


def check_danger(source: str) -> list[str]:
    """Any exec/eval/os.system-style call is rejected outright, and any
    subprocess.* call EXCEPT the bounded pattern shipped primitives use -
    the READ shape (`subprocess.run([...], capture_output=True,
    timeout=...)`) and the WRITE shape (`subprocess.run([...],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=...)`, for
    tools whose daemon inherits pipe fds) - see _is_safe_subprocess_run."""
    issues: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return issues
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if isinstance(fn, ast.Name) and fn.id in _DANGER_BUILTINS:
            issues.append(f"calls {fn.id}() - arbitrary-execution builtin")
        elif isinstance(fn, ast.Attribute):
            dotted = _dotted_name(fn)
            if dotted in _DANGER_ATTRS:
                issues.append(f"calls {dotted}() - dangerous/arbitrary execution")
            elif dotted.startswith("subprocess.") and not _is_safe_subprocess_run(node):
                issues.append(f"calls {dotted}() - dangerous/arbitrary execution")
    return issues


def _fn_params(source: str, fn_name: str) -> list[str]:
    """Declared parameter names of the contracted function (excluding
    self/cls) - build-verify probes only pass arguments the draft actually
    declares, so a probe never false-fails on an unexpected kwarg."""
    fn = _find_function(source, fn_name)
    if fn is None:
        return []
    return [a.arg for a in fn.args.args + fn.args.posonlyargs + fn.args.kwonlyargs
            if a.arg not in ("self", "cls")]


def _find_function(source: str, fn_name: str) -> ast.FunctionDef | None:
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return None
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef) and node.name == fn_name:
            return node
    return None


def check_contract_function(source: str, fn_name: str) -> list[str]:
    """The impl must actually define the function its contract names."""
    if _find_function(source, fn_name) is None:
        return [f"impl does not define the contracted function {fn_name}()"]
    return []


def check_dead_args(source: str, fn_name: str) -> list[str]:
    """Every declared parameter of the contracted function must be USED in
    its body - the exact defect the human gate caught by hand last round
    (an impl that ignored its own `name` argument and hardcoded a literal).
    `self`/`cls` and *args/**kwargs are exempt; a name used anywhere in
    the function's tree (including nested scopes) counts as used, so this
    over-approximates usage rather than false-rejecting."""
    fn = _find_function(source, fn_name)
    if fn is None:
        return []
    params = [a.arg for a in fn.args.args + fn.args.posonlyargs + fn.args.kwonlyargs
              if a.arg not in ("self", "cls")]
    used = {n.id for n in ast.walk(fn) if isinstance(n, ast.Name)}
    return [f"parameter {p!r} is declared but never used" for p in params if p not in used]


# Builtin exception names a draft must NOT raise explicitly unless its own
# contract text declares them: the executor's retry policy keys on the
# FridayError family (friday/errors.py), so a primitive that raises a bare
# builtin against a contract declaring a Friday error class fails its own
# contract on first real failure - observed live 2026-08-14: the clipboard
# draft raised RuntimeError against a failure_mode declaring PrimitiveError.
_BUILTIN_EXC_NAMES = frozenset({
    "ArithmeticError", "AssertionError", "AttributeError", "EOFError", "Exception",
    "ImportError", "IndexError", "KeyError", "LookupError", "MemoryError",
    "NameError", "NotImplementedError", "OSError", "OverflowError",
    "RecursionError", "ReferenceError", "RuntimeError", "StopIteration",
    "SyntaxError", "SystemError", "TimeoutError", "TypeError", "UnicodeError",
    "ValueError", "ZeroDivisionError", "IOError", "EnvironmentError",
})


def check_contract_decorator(source: str, fn_name: str) -> list[str]:
    """The contracted function MUST be decorated with @contract(...). Without
    the decorator the impl never enters the REGISTRY, so the executor keeps
    refusing the primitive even after 'registration' - the exact defect a human
    hand-corrected on the first clipboard.read_text draft (2026-08-14: the
    draft passed the structural self-check yet would never have been callable)."""
    fn = _find_function(source, fn_name)
    if fn is None:
        return []  # the missing-function check reports that separately
    for d in fn.decorator_list:
        if (isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == "contract") or \
                (isinstance(d, ast.Name) and d.id == "contract"):
            return []
    return [
        f"{fn_name}() is not decorated with @contract(...) - the impl would never "
        "enter the REGISTRY and the executor would keep refusing it",
    ]


def check_contract_consistency(contract: dict[str, Any], source: str) -> list[str]:
    """contract.json may name a log_transform; the impl MUST define it at module
    level. A contract declaring a transform the impl never defines is a NameError
    at import time - the exact defect a human hand-corrected on the clipboard
    draft (contract declared _log_redact_clipboard_meta, impl had no such
    function). Static and cheap; runs at triage AND at the gate."""
    lt = contract.get("log_transform")
    if not isinstance(lt, str) or not lt:
        return []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return []
    defs = {n.name for n in tree.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))}
    if lt not in defs:
        return [
            f"contract declares log_transform={lt!r} but the impl never defines "
            "it - the module would fail with NameError at import",
        ]
    return []


def check_raise_classes(source: str, contract: dict[str, Any]) -> list[str]:
    """The impl must not explicitly raise a bare builtin exception the contract
    never declares: the executor's retry policy keys on the FridayError family,
    so a draft raising RuntimeError against a failure_mode declaring PrimitiveError
    fails its own contract on first real failure (the clipboard defect a human
    hand-corrected 2026-08-14). IMPLICIT propagation (files.write_text letting
    OSError escape through a `with` block) is NOT an explicit raise and is not
    flagged - that is documented as legitimate for that primitive. A raise whose
    exception name appears in the contract's own text is allowed (the contract
    declares it)."""
    contract_text = " ".join(
        str(contract.get(k, "")) for k in ("failure_mode", "precondition", "postcondition", "returns")
    ).lower()
    issues: list[str] = []
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return issues
    for node in ast.walk(tree):
        if not isinstance(node, ast.Raise) or node.exc is None:
            continue
        exc = node.exc
        name: str | None = None
        if isinstance(exc, ast.Call) and isinstance(exc.func, ast.Name):
            name = exc.func.id
        elif isinstance(exc, ast.Name):
            name = exc.id
        if name in _BUILTIN_EXC_NAMES and name.lower() not in contract_text:
            issues.append(
                f"raises builtin {name}() but the contract declares "
                f"failure_mode={contract.get('failure_mode', '')!r} - raise a "
                "FridayError subclass (PrimitiveError/PreconditionError) instead "
                "so the executor's retry policy classifies it"
            )
    return issues


def check_impl_ast(
    source: str, fn_name: str, contract: dict[str, Any] | None = None
) -> list[str]:
    """The full static pass: imports, danger calls, sandbox-escaping
    writes, contract function, dead arguments - plus, when the contract is
    supplied (the gate and the triage self-check both pass it), the
    contract-consistency checks: the @contract decorator present, every
    log_transform the contract names defined by the impl, and no
    bare-builtin raises the contract never declares. Returns [] when the
    impl is structurally clean."""
    issues = (
        check_imports(source)
        + check_danger(source)
        + check_fs_scope(source)
        + check_contract_function(source, fn_name)
        + check_dead_args(source, fn_name)
    )
    if contract is not None:
        issues += (
            check_contract_decorator(source, fn_name)
            + check_contract_consistency(contract, source)
            + check_raise_classes(source, contract)
        )
    return issues


# ------------------------------------------------------ build verification

# Executes the DRAFT function against REAL harmless targets (files.*) in
# the same isolated env as the sandbox test. Reads a probe spec JSON:
#   {"fn": <name>, "probes": [...]}
# Probe kinds:
#   read/error (legacy): {"args": {...},
#                         "expect_path": <exact str result> |
#                         "expect": "str" |
#                         "allow_friday_error": true}
#   write: {"kind": "write", "calls": [{"args": {...}, "expect_content": <str>}, ...]}
#     each call invokes fn(**args), requires a str result, and verifies the
#     file at the args' path arg exists with exactly expect_content on disk
#     (overwrite/append semantics are exercised by the call sequence).
# Prints one PROBE_OK/PROBE_FAIL line per probe plus a BUILD_RESULT line.
_BUILD_RUNNER = r"""
import importlib
import json
import sys
import types
from pathlib import Path


def _path_arg(args: dict) -> str | None:
    # the declared path argument of a write-family call
    for key in ("path", "file_path", "filename", "target"):
        if isinstance(args.get(key), str):
            return args[key]
    return None


def _run_write_probe(fn, calls) -> str | None:
    # sequential write calls; None = all passed, else a PROBE_FAIL text
    for j, call in enumerate(calls):
        try:
            result = fn(**call["args"])
        except Exception as exc:
            if call.get("allow_friday_error") and isinstance(exc, FridayError):
                continue
            return f"call {j} raised {type(exc).__name__}: {exc}"
        if not isinstance(result, str):
            return f"call {j} write returned {type(result).__name__}, expected a str path"
        target = _path_arg(call["args"])
        if target is None or not Path(target).is_file():
            return f"call {j} write did not create the file at {target!r}"
        content = Path(target).read_text(encoding="utf-8")
        expected = call.get("expect_content")
        if expected is not None and content != expected:
            return f"call {j} content mismatch: expected {expected!r}, got {content!r}"
    return None


def _run_subread_probe(fn, mod, probe, FridayError) -> str | None:
    # A subprocess-read primitive (clipboard.read_text shape): patch the
    # module's subprocess.run (and a `from subprocess import run` binding, if
    # present) with a fake, then call fn() with no args and check the contract
    # shape: success -> str result; tool failure/timeout -> FridayError, NEVER
    # a bare builtin (the RuntimeError defect a human hand-corrected on the
    # clipboard draft, 2026-08-14). None = probe passed, else a FAIL text.
    # FridayError is passed in: the runner imports it locally inside main()
    # (sys.path is set up there), so the helper takes it as a parameter.
    import subprocess as _sp

    class _FakeProc:
        def __init__(self, *, returncode=0, stdout=b"", stderr=b""):
            self.returncode = returncode
            self.stdout = stdout
            self.stderr = stderr

    mock = probe.get("mock", {})
    exc_name = mock.get("raise")

    def _fake_run(*_a, **_kw):
        if exc_name:
            raise TimeoutError("mocked timeout")
        return _FakeProc(
            returncode=mock.get("returncode", 0),
            stdout=(mock.get("stdout") or "").encode(),
            stderr=(mock.get("stderr") or "").encode(),
        )

    # patch both call styles: `subprocess.run(...)` (module attr) and
    # `from subprocess import run` (bare name bound in the module namespace)
    if getattr(mod, "subprocess", None) is not None:
        mod.subprocess.run = _fake_run
    if getattr(mod, "run", None) is not None and callable(mod.run):
        mod.run = _fake_run
    try:
        result = fn()
    except FridayError:
        if probe.get("expect") == "friday_or_str":
            return None
        return f"raised FridayError on a success mock (expected a str result)"
    except Exception as exc:
        return (
            f"raised {type(exc).__name__}: {exc} - expected FridayError "
            "(or a str result); bare builtins never satisfy a contract "
            "declaring a Friday error class"
        )
    if probe.get("expect") == "str":
        if not isinstance(result, str):
            return f"expected str result, got {type(result).__name__}: {result!r}"
        return None
    if probe.get("expect") == "friday_or_str":
        if isinstance(result, str):
            return None
        return f"expected FridayError or a str result, got {type(result).__name__}: {result!r}"
    return None


def main() -> int:
    root, impl_path, module, existing, probes_path = sys.argv[1:6]
    sys.path.insert(0, root)
    if existing == "1":
        mod = importlib.import_module(f"friday.l1.{module}")
    else:
        mod = types.ModuleType(f"friday.l1.{module}")
        mod.__file__ = impl_path
    src = open(impl_path, encoding="utf-8").read()
    # same in-place injection as the sandbox runner - see _SANDBOX_RUNNER
    exec(compile(src, impl_path, "exec"), mod.__dict__)
    sys.modules[f"friday.l1.{module}"] = mod
    pkg = sys.modules.get("friday.l1")
    if pkg is not None:
        setattr(pkg, module, mod)
    from friday.errors import FridayError

    spec = json.load(open(probes_path, encoding="utf-8"))
    fn = getattr(mod, spec["fn"])
    failed = 0
    for i, p in enumerate(spec["probes"]):
        if p.get("kind") == "write":
            msg = _run_write_probe(fn, p["calls"])
            if msg:
                print(f"PROBE_FAIL {i} {msg}")
                failed += 1
            else:
                print(f"PROBE_OK {i} write probes passed (created/overwrote/appended temp files)")
            continue
        if p.get("kind") == "subread":
            msg = _run_subread_probe(fn, mod, p, FridayError)
            if msg:
                print(f"PROBE_FAIL {i} {msg}")
                failed += 1
            else:
                print(f"PROBE_OK {i} subprocess-read probes passed (mocked tool: success->str, failure/timeout->FridayError)")
            continue
        try:
            result = fn(**p["args"])
        except Exception as exc:
            if p.get("allow_friday_error") and isinstance(exc, FridayError):
                print(f"PROBE_OK {i} (raised {type(exc).__name__} - acceptable)")
                continue
            print(f"PROBE_FAIL {i} raised {type(exc).__name__}: {exc}")
            failed += 1
            continue
        if "expect_path" in p:
            if not isinstance(result, str) or result != p["expect_path"]:
                print(f"PROBE_FAIL {i} expected path {p['expect_path']!r}, got {result!r} ({type(result).__name__})")
                failed += 1
                continue
        elif p.get("expect") == "str" and not isinstance(result, str):
            print(f"PROBE_FAIL {i} expected str, got {type(result).__name__}: {result!r}")
            failed += 1
            continue
        print(f"PROBE_OK {i} -> {result!r}")
    print("BUILD_RESULT", "fail" if failed else "ok")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    sys.exit(main())
"""


# Read-family params (find_file / find_file_exact / find_recent_doc).
_READ_PARAMS = frozenset({"name", "pattern", "repo_path"})
# Write-family params: a path-ish AND a content-ish arg (files.write_text).
_WRITE_PATH_PARAMS = frozenset({"path", "file_path", "filename", "target"})
_WRITE_CONTENT_PARAMS = frozenset({"text", "content", "data"})


def _uses_bounded_subprocess(source: str) -> bool:
    """True when the impl shells out through the read-only bounded subprocess
    pattern shipped primitives use (subprocess.run([...], capture_output=True,
    timeout=...)) - the signal that a non-files draft is a clipboard-style
    external-read primitive whose build-verify can probe with a mocked tool."""
    try:
        tree = ast.parse(source)
    except SyntaxError:
        return False
    return any(
        isinstance(n, ast.Call) and _is_safe_subprocess_run(n) for n in ast.walk(tree)
    )


def _build_probe_family(fn_name: str, params: list[str]) -> str:
    """Derive the probe family from the DRAFT's DECLARED parameters rather
    than the contract name: read-family declares a name/pattern arg;
    write-family declares a path-ish AND a content-ish arg (the observed
    files.write_text(path, text) shape). Neither -> not-applicable (never
    probed blind). This is Fix 2 (2026-08-13): the first CLEAN write draft
    was false-rejected because the probes hardcoded read semantics."""
    if set(params) & _READ_PARAMS:
        return "read"
    if (set(params) & _WRITE_PATH_PARAMS) and (set(params) & _WRITE_CONTENT_PARAMS):
        return "write"
    return "none"


def run_build_verify(
    proposal: Path,
    contract: dict[str, Any],
    impl_src: str,
    *,
    timeout_s: int = DEFAULT_SANDBOX_TIMEOUT_S,
) -> tuple[str, list[str]]:
    """Run the DRAFT function against something resembling its real target
    after its own test.py passed. files.* gets REAL harmless targets in a
    temp dir: READ-family drafts are probed with a real file (present-name
    must return that EXACT path, absent-name a str, a missing directory
    may raise FridayError but nothing else); WRITE-family drafts are
    probed by CALLING them against absolute temp paths and VERIFYING THE
    FILE ON DISK (created with exact content, overwritten by a second
    write, appended when declared, and error probes raising nothing worse
    than FridayError). A files.* draft declaring neither family, or any
    other module class, is HONESTLY flagged not-applicable (human review
    required), never silently skipped. Returns (status, report_lines);
    status is "pass" | "reject" | "not-applicable". A reject fails the
    gate before the signature."""
    module = contract["name"].partition(".")[0]
    fn_name = contract["name"].partition(".")[2]
    params = _fn_params(impl_src, fn_name)
    if module != "files":
        # SUBPROCESS-READ family (2026-08-14): a module class like clipboard
        # that reads an external tool through the bounded subprocess.run
        # pattern has NO safe real target in this session (reading the real
        # clipboard under the sandbox is meaningless) - but its behavior IS
        # probeable with a MOCKED subprocess.run: success must return a str,
        # a tool failure and a timeout must surface as FridayError, never a
        # bare builtin (the RuntimeError defect a human hand-corrected on the
        # clipboard draft). Probes run when the impl uses the bounded pattern
        # and the contracted fn takes no args (read_text() shape) - otherwise
        # honest not-applicable, never probed blind.
        if not params and _uses_bounded_subprocess(impl_src):
            probes = [
                {"kind": "subread", "mock": {"returncode": 0, "stdout": "probe text\n"}, "expect": "str"},
                {"kind": "subread", "mock": {"returncode": 1, "stderr": "tool failed"}, "expect": "friday_or_str"},
                {"kind": "subread", "mock": {"raise": "TimeoutError"}, "expect": "friday_or_str"},
            ]
            try:
                with tempfile.TemporaryDirectory(prefix="friday_buildverify_") as td:
                    sandbox = Path(td)
                    spec_path = sandbox / "probes.json"
                    spec_path.write_text(json.dumps({"fn": fn_name, "probes": probes}), encoding="utf-8")
                    runner = sandbox / "build_runner.py"
                    runner.write_text(_BUILD_RUNNER, encoding="utf-8")
                    existing = "1" if (L1_DIR / f"{module}.py").is_file() else "0"
                    cmd = [
                        sys.executable, str(runner), str(PROJECT_ROOT),
                        str((proposal / "impl.py").resolve()), module, existing, str(spec_path),
                    ]
                    try:
                        proc = subprocess.run(
                            cmd, capture_output=True, text=True,
                            timeout=timeout_s, cwd=str(sandbox), env=_sanitized_env(sandbox),
                        )
                    except subprocess.TimeoutExpired:
                        return "reject", ["build-verify: REJECT - timed out while probing the mocked tool"]
                    out = proc.stdout + "\n" + proc.stderr
                    fails = [l for l in out.splitlines() if l.startswith("PROBE_FAIL")]
                    if proc.returncode != 0 or fails:
                        detail = fails[0] if fails else (out.strip().splitlines()[-1] if out.strip() else "unknown")
                        return "reject", [f"build-verify: REJECT - {detail}"]
                    return "pass", [
                        "build-verify: PASS - subprocess-read probes (mocked tool): "
                        "success -> str; tool failure/timeout -> FridayError, never "
                        "a bare builtin (the clipboard error-class fix, 2026-08-14)",
                    ]
            except OSError as exc:
                return "reject", [f"build-verify: REJECT - probe setup failed: {exc}"]
        return "not-applicable", [
            f"build-verify: NOT APPLICABLE for module class {module!r} - no "
            "safe real target for this class this session; human review "
            "required (documented limit)",
        ]
    family = _build_probe_family(fn_name, params)
    if family == "none":
        return "not-applicable", [
            f"build-verify: NOT APPLICABLE - files.{fn_name} declares neither a "
            "read arg (name/pattern/repo_path) nor a write pair (path+content); "
            "no safe generic probe for this shape; human review required",
        ]
    try:
        with tempfile.TemporaryDirectory(prefix="friday_buildverify_") as td:
            sandbox = Path(td)

            def _args(**kw):
                return {k: v for k, v in kw.items() if k in params}

            if family == "read":
                target = sandbox / "report.pdf"
                target.write_text("probe target", encoding="utf-8")
                probes = [
                    {"args": _args(name="report.pdf", directory=str(sandbox)), "expect_path": str(target)},
                    {"args": _args(name="definitely-not-present-xyz.pdf", directory=str(sandbox)), "expect": "str"},
                    {"args": _args(name="x", directory=str(sandbox / "no-such-dir")), "allow_friday_error": True},
                ]
            else:  # write family
                target1 = sandbox / "notes.md"
                target2 = sandbox / "log.txt"
                probes = [
                    {"kind": "write", "calls": [
                        {"args": _args(path=str(target1), text="hello"), "expect_content": "hello"},
                        {"args": _args(path=str(target1), text="goodbye"), "expect_content": "goodbye"},
                    ]},
                ]
                if "append" in params:
                    probes.append({"kind": "write", "calls": [
                        {"args": _args(path=str(target2), text="line1\n"), "expect_content": "line1\n"},
                        {"args": _args(path=str(target2), text="line2\n", append=True), "expect_content": "line1\nline2\n"},
                    ]})
                # missing-parent must raise FridayError or return, never a
                # raw OSError/TypeError (the contract says PreconditionError)
                probes.append({"kind": "error", "args": _args(path=str(sandbox / "no-such-dir" / "f.txt"), text="x"), "allow_friday_error": True})
            spec_path = sandbox / "probes.json"
            spec_path.write_text(json.dumps({"fn": fn_name, "probes": probes}), encoding="utf-8")
            runner = sandbox / "build_runner.py"
            runner.write_text(_BUILD_RUNNER, encoding="utf-8")
            existing = "1" if (L1_DIR / f"{module}.py").is_file() else "0"
            cmd = [
                sys.executable, str(runner), str(PROJECT_ROOT),
                str((proposal / "impl.py").resolve()), module, existing, str(spec_path),
            ]
            try:
                proc = subprocess.run(
                    cmd, capture_output=True, text=True,
                    timeout=timeout_s, cwd=str(sandbox), env=_sanitized_env(sandbox),
                )
            except subprocess.TimeoutExpired:
                return "reject", ["build-verify: REJECT - timed out while probing the real target"]
            out = proc.stdout + "\n" + proc.stderr
            fails = [l for l in out.splitlines() if l.startswith("PROBE_FAIL")]
            if proc.returncode != 0 or fails:
                detail = fails[0] if fails else (out.strip().splitlines()[-1] if out.strip() else "unknown")
                return "reject", [f"build-verify: REJECT - {detail}"]
            if family == "write":
                return "pass", [
                    "build-verify: PASS - files.* write probes: created+overwrote "
                    "(and appended, when declared) a real temp file with verified "
                    "content; missing-parent raised FridayError or returned "
                    "(Fix 2, 2026-08-13)",
                ]
            return "pass", [
                "build-verify: PASS - files.* real-target probes: present name -> exact "
                "path, absent -> str, bad directory -> FridayError handled",
            ]
    except OSError as exc:
        return "reject", [f"build-verify: REJECT - probe setup failed: {exc}"]


# ------------------------------------------------------ sandboxed test run

# Runs in a SEPARATE subprocess: execs the DRAFT impl into the real
# module's namespace (existing module) or a fresh one (new module),
# injects it as friday.l1.<module> in sys.modules so the proposal's own
# test.py exercises the draft, then runs the test file. The subprocess
# env is sanitized by the parent (temp HOME, no credentials, no FRIDAY_*
# overrides) - see _sanitized_env.
_SANDBOX_RUNNER = r"""
import importlib
import runpy
import sys
import types


def main() -> int:
    root, impl_path, test_path, module, existing = sys.argv[1:6]
    sys.path.insert(0, root)
    if existing == "1":
        mod = importlib.import_module(f"friday.l1.{module}")
    else:
        mod = types.ModuleType(f"friday.l1.{module}")
        mod.__file__ = impl_path
    src = open(impl_path, encoding="utf-8").read()
    # Exec the DRAFT IN PLACE into the module's own namespace - NOT into a
    # copy that replaces sys.modules. A copy is bypassed by the common
    # import styles `from friday.l1 import files` and `import ... as`
    # (they bind the package ATTRIBUTE, which the earlier real import
    # already set, never consulting sys.modules) - observed live
    # 2026-08-13: a clean files.write_text draft was false-rejected with
    # 'module friday.l1.files has no attribute write_text'. The sandbox
    # is a throwaway subprocess, so mutating the real module is safe.
    exec(compile(src, impl_path, "exec"), mod.__dict__)
    sys.modules[f"friday.l1.{module}"] = mod
    # keep the package attribute in sync so EVERY import style (including
    # `from friday.l1 import files`) resolves to the draft
    pkg = sys.modules.get("friday.l1")
    if pkg is not None:
        setattr(pkg, module, mod)
    # The gate's own argv must not leak into the test: unittest.main()
    # inside the test file parses sys.argv[1:] as test names, and the
    # runner's internal args would be misread as imports.
    sys.argv = [test_path]
    try:
        runpy.run_path(test_path, run_name="__main__")
    except SystemExit as exc:
        code = exc.code
        return code if isinstance(code, int) else (0 if code is None else 1)
    return 0


if __name__ == "__main__":
    sys.exit(main())
"""

# Runs in a SEPARATE subprocess: execs the DRAFT impl in place (same
# injection as the sandbox runner) and asserts the contracted name actually
# lands in REGISTRY. A draft that compiles and even passes its own test can
# still be DEAD ON ARRIVAL - the clipboard.read_text round (2026-08-14)
# produced exactly that: a self-check-clean draft whose impl had NO
# @contract decorator (so registration wrote the file but the primitive
# never entered REGISTRY and the executor kept refusing it) and a contract
# declaring log_transform=_log_redact_clipboard_meta the impl never defined
# (NameError at import). Both are structurally checkable and both are
# checked here, BEFORE any human review.
_REGISTRATION_RUNNER = r"""
import sys
import types


def main() -> int:
    root, impl_path, module, existing, expected = sys.argv[1:6]
    sys.path.insert(0, root)
    # ALWAYS a fresh module - never import the real friday.l1.<module>,
    # even when it exists on disk. Importing the real module would satisfy
    # the check vacuously (its already-registered primitive is in REGISTRY
    # from its own import), so an undecorated re-draft of a registered
    # module would pass - the exact dead-on-arrival class this check
    # exists to catch (observed live 2026-08-14: the two negative
    # registration tests started passing vacuously the moment
    # clipboard.read_text was registered). The draft must register the
    # name ON ITS OWN.
    mod = types.ModuleType(f"friday.l1.{module}")
    mod.__file__ = impl_path
    src = open(impl_path, encoding="utf-8").read()
    try:
        exec(compile(src, impl_path, "exec"), mod.__dict__)
    except Exception as exc:
        print(f"REGISTER_FAIL import raised {type(exc).__name__}: {exc}")
        return 1
    sys.modules[f"friday.l1.{module}"] = mod
    pkg = sys.modules.get("friday.l1")
    if pkg is not None:
        setattr(pkg, module, mod)
    from friday.contracts import REGISTRY

    if expected in REGISTRY:
        print(f"REGISTER_OK {expected} is in REGISTRY")
        return 0
    print(f"REGISTER_FAIL {expected} NOT in REGISTRY after exec - missing @contract decorator?")
    return 1


if __name__ == "__main__":
    sys.exit(main())
"""


def check_registration(
    impl_path: Path,
    contract_name: str,
    *,
    timeout_s: int = DEFAULT_SANDBOX_TIMEOUT_S,
) -> tuple[bool, str]:
    """Assert the DRAFT actually registers the contracted name when its code
    runs: exec the impl in place (same isolated subprocess as the sandbox:
    temp HOME, no credentials, timeout) and require `name in REGISTRY`.
    Catches the dead-on-arrival class the clipboard round exposed - a draft
    that compiles and whose test passes yet whose impl is missing the
    @contract decorator (never registers, executor keeps refusing) or
    references a log_transform it never defines (NameError at import).
    Returns (ok, summary)."""
    module = contract_name.partition(".")[0]
    existing = "1" if (L1_DIR / f"{module}.py").is_file() else "0"
    cmd = [
        sys.executable, "<runner>", str(PROJECT_ROOT),
        str(Path(impl_path).resolve()), module, existing, contract_name,
    ]
    try:
        with tempfile.TemporaryDirectory(prefix="friday_regcheck_") as td:
            sandbox = Path(td)
            runner = sandbox / "reg_runner.py"
            runner.write_text(_REGISTRATION_RUNNER, encoding="utf-8")
            cmd[1] = str(runner)
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout_s, cwd=str(sandbox), env=_sanitized_env(sandbox),
            )
    except subprocess.TimeoutExpired:
        return False, f"registration check timed out after {timeout_s}s"
    tail = (proc.stdout + "\n" + proc.stderr).strip()
    if proc.returncode != 0:
        lines = tail.splitlines()[-6:]
        return False, "registration check FAILED:\n" + "\n".join(lines)
    return True, "draft registers the contracted name"


_STRIP_MARKERS = ("TOKEN", "SECRET", "PASSWORD", "PASSWD", "API_KEY", "APIKEY",
                  "PRIVATE_KEY", "PASSPHRASE", "KEY")


def _sanitized_env(sandbox_dir: Path) -> dict[str, str]:
    """Subprocess env with every credential-bearing and Friday-override var
    removed, HOME pointed at the sandbox (so pass/gpg lookups fail), and
    the FRIDAY_* logging/triage paths redirected to temp files. Network is
    not hard-blocked (documented limit); with no credentials present the
    live primitives cannot authenticate anyway."""
    env = {
        k: v for k, v in os.environ.items()
        if not any(m in k.upper() for m in _STRIP_MARKERS)
    }
    for key in list(env):
        up = key.upper()
        if up.startswith(("FRIDAY_", "WHATSAPP_", "TELEGRAM_", "DISCORD_", "GITHUB_")):
            env.pop(key, None)
    env.pop("FRIDAY_ALLOW_DANGEROUS", None)
    env["FRIDAY_LOG_FILE"] = str(sandbox_dir / "log.jsonl")
    env["FRIDAY_GAPS_FILE"] = str(sandbox_dir / "gaps.jsonl")
    env["FRIDAY_TASKS_FILE"] = str(sandbox_dir / "tasks.jsonl")
    env["FRIDAY_PROPOSALS_DIR"] = str(sandbox_dir / "proposals")
    env["HOME"] = str(sandbox_dir)
    # tempfile inside the sandbox must land in the sandbox, not the real
    # /tmp: tempfile.mkstemp()/NamedTemporaryFile are not statically
    # resolvable by check_fs_scope, so redirect the tempdir env instead.
    env["TMPDIR"] = env["TMP"] = env["TEMP"] = str(sandbox_dir)
    # The sandbox must never be able to invoke the claude CLI (a paid,
    # side-effecting subprocess) from an LLM-generated test.
    kept = [s for s in env.get("PATH", "").split(os.pathsep)
            if s and not (Path(s) / "claude").is_file()]
    env["PATH"] = os.pathsep.join(kept)
    return env


def run_sandbox_test(
    impl_path: Path,
    test_path: Path,
    contract_name: str,
    *,
    timeout_s: int = DEFAULT_SANDBOX_TIMEOUT_S,
) -> tuple[bool, str]:
    """Run the proposal's own test.py against the DRAFT impl in an isolated
    subprocess. A proposal without test.py is a documented SKIP (the gate
    still enforces AST + signature). Returns (passed, human summary)."""
    if not Path(test_path).is_file():
        return True, "no test.py in the proposal - sandbox run skipped (documented limit)"
    module = contract_name.partition(".")[0]
    existing = "1" if (L1_DIR / f"{module}.py").is_file() else "0"
    cmd = [
        sys.executable, "<runner>", str(PROJECT_ROOT),
        str(Path(impl_path).resolve()), str(Path(test_path).resolve()),
        module, existing,
    ]
    try:
        with tempfile.TemporaryDirectory(prefix="friday_sandbox_") as td:
            sandbox = Path(td)
            runner = sandbox / "runner.py"
            runner.write_text(_SANDBOX_RUNNER, encoding="utf-8")
            cmd[1] = str(runner)
            proc = subprocess.run(
                cmd, capture_output=True, text=True,
                timeout=timeout_s, cwd=str(sandbox), env=_sanitized_env(sandbox),
            )
    except subprocess.TimeoutExpired:
        return False, f"sandbox test run timed out after {timeout_s}s"
    tail = (proc.stdout + "\n" + proc.stderr).strip()
    if proc.returncode != 0:
        lines = tail.splitlines()[-12:]
        return False, f"sandbox test run FAILED (exit {proc.returncode}):\n" + "\n".join(lines)
    head = " ".join(tail.split())[:300]
    return True, f"sandbox test run PASSED (exit 0){(' - ' + head) if head else ''}"


# ------------------------------------------------------------- the gate


def run_automated_gate(
    proposal: Path,
    *,
    contract: dict[str, Any],
    impl_src: str,
    timeout_s: int = DEFAULT_SANDBOX_TIMEOUT_S,
) -> tuple[bool, list[str]]:
    """AST checks + sandboxed test run for one proposal. Always appends the
    full report to rationale.md (rejection reasons included, per the spec -
    a failed gate never reaches the human signature). Returns (ok, report)."""
    fn_name = contract["name"].partition(".")[2]
    issues = check_impl_ast(impl_src, fn_name, contract)
    lines: list[str] = []
    if issues:
        # short-circuit: an AST-rejected draft is NEVER executed, not even
        # its own sandbox test - running a dangerous draft is itself a risk
        lines += [f"AST REJECT: {i}" for i in issues]
        lines.append("sandbox: SKIPPED - the draft was rejected at AST, so its test was not executed")
        # record the failure class as a lesson event - the raw material of
        # the lessons loop (best-effort, never breaks the gate)
        record_lesson_event(
            category="draft_ast", source="automated_gate",
            detail=f"{contract['name']}: {issues[0]}", primitive=contract["name"],
        )
        _append_report(proposal / "rationale.md", lines)
        return False, lines
    lines.append(
        "AST checks: passed - imports allowed; no dangerous calls; no "
        f"sandbox-escaping writes; {fn_name}() defined; no dead arguments; "
        "@contract decorator present; log_transform (if any) defined; no "
        "undeclared bare-builtin raises"
    )
    # REGISTRATION check: a draft that compiles and passes its own test can
    # still be dead on arrival - missing @contract decorator (never enters
    # REGISTRY, executor keeps refusing) or a log_transform the impl never
    # defines (NameError at import). Both were hand-corrected on the first
    # clipboard.read_text draft (2026-08-14); both are structural and are
    # checked here, before any human review.
    reg_ok, reg_summary = check_registration(
        proposal / "impl.py", contract["name"], timeout_s=timeout_s
    )
    if not reg_ok:
        lines.append(f"registration: REJECT - {reg_summary}")
        record_lesson_event(
            category="draft_no_register", source="automated_gate",
            detail=f"{contract['name']}: {reg_summary}", primitive=contract["name"],
        )
        _append_report(proposal / "rationale.md", lines)
        return False, lines
    lines.append("registration: PASS - draft registers the contracted name when imported")
    # The FILE THE SANDBOX EXECUTES (test.py) is itself danger- and
    # fs-scope-checked before it runs - the LLM writes both files. Imports
    # are NOT restricted here: a test file legitimately imports
    # unittest/tempfile, and the sandbox's env already strips credentials
    # + the claude CLI, and literal writes must stay inside the sandbox cwd.
    test_path = proposal / "test.py"
    test_src = test_path.read_text(encoding="utf-8") if test_path.is_file() else ""
    test_issues = (check_danger(test_src) + check_fs_scope(test_src)) if test_src else []
    if test_issues:
        lines += [f"test.py AST REJECT: {i}" for i in test_issues]
        lines.append("sandbox: SKIPPED - the test file itself was rejected at AST")
        record_lesson_event(
            category="draft_ast", source="automated_gate",
            detail=f"{contract['name']} test.py: {test_issues[0]}", primitive=contract["name"],
        )
        _append_report(proposal / "rationale.md", lines)
        return False, lines
    sandbox_ok, sandbox_summary = run_sandbox_test(
        proposal / "impl.py", test_path, contract["name"], timeout_s=timeout_s
    )
    if sandbox_ok:
        lines.append(f"sandbox: PASS - {sandbox_summary}")
    else:
        lines.append(f"sandbox: REJECT - {sandbox_summary}")
        record_lesson_event(
            category="draft_test_fail", source="automated_gate",
            detail=f"{contract['name']}: {sandbox_summary}", primitive=contract["name"],
        )
        _append_report(proposal / "rationale.md", lines)
        return False, lines
    # Build verification: the draft's OWN test passing is not the only
    # check - run the function against something resembling its real
    # target (files.* gets REAL temp-dir probes; other classes are
    # honestly flagged not-applicable). A reject fails the gate here,
    # before the human signature.
    bv_status, bv_lines = run_build_verify(proposal, contract, impl_src, timeout_s=timeout_s)
    lines += bv_lines
    if bv_status == "reject":
        record_lesson_event(
            category="draft_build_verify_fail", source="automated_gate",
            detail=f"{contract['name']}: {bv_lines[0] if bv_lines else 'build-verify rejected'}",
            primitive=contract["name"],
        )
        _append_report(proposal / "rationale.md", lines)
        return False, lines
    _append_report(proposal / "rationale.md", lines)
    return True, lines


def _append_report(rationale: Path, lines: list[str]) -> None:
    """Append the gate report to the proposal's rationale.md so a human
    reviewer sees what the mechanics proved BEFORE the diff to review.
    Creates the file if a hand-made proposal never wrote one - the
    rejection reason must always land somewhere visible."""
    if not rationale.is_file():
        try:
            rationale.parent.mkdir(parents=True, exist_ok=True)
            rationale.write_text("# rationale\n", encoding="utf-8")
        except OSError:
            return  # best-effort; an unwritable rationale never blocks the gate
    block = [
        "",
        "## Automated gate (friday/automated_gate.py)",
        f"- run: {datetime.now(timezone.utc).isoformat(timespec='seconds')}",
        *(f"- {line}" for line in lines),
        "",
        "The automated gate catches STRUCTURAL defects only - it does not",
        "validate design or safety intent. Review the impl against its",
        "contract, then sign APPROVED.md to register.",
    ]
    try:
        with open(rationale, "a", encoding="utf-8") as fh:
            fh.write("\n".join(block) + "\n")
    except OSError:
        pass  # best-effort; an unwritable rationale never blocks the gate
