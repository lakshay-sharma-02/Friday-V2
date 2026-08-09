"""L1 primitive: dev (Claude Code CLI as subprocess).

This primitive executes and reports only - verification is the caller's
(L2's) job, never its own. Any permission-bypassing flag is an explicit
opt-in argument per call, never a silent default: it is an authorization
boundary, so `allow_bypass_permissions` defaults to False.
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError, PrimitiveTimeout

CLAUDE = "claude"

# Default model alias for this machine. The stock default is broken here
# (cc/claude-sonnet-5 -> 404; the 'haiku'/'sonnet' aliases route to EOL
# models). 'opus' resolves correctly. Override per call via the model arg.
MODEL_ALIAS = "opus"

# Dangerous capabilities (arbitrary shell execution, permission-bypassing
# flags) require an explicit environment opt-in. Without this flag ANY
# goal string - or a confused LLM - could steer the pipeline toward shell;
# the flag is the authorization boundary, and it is checked BEFORE claude
# is ever invoked.
DANGEROUS_ENV = "FRIDAY_ALLOW_DANGEROUS"


def _require_dangerous_opt_in(what: str) -> None:
    """Refuse a dangerous capability unless the user opted in with
    FRIDAY_ALLOW_DANGEROUS=1. PreconditionError (a caller bug, never
    retried by the executor's contract-derived policy) so a plan reaching
    for shell fails loudly and immediately, before any side effect."""
    if os.environ.get(DANGEROUS_ENV) != "1":
        raise PreconditionError(
            f"{what} is gated behind {DANGEROUS_ENV}=1; refusing without explicit opt-in"
        )


def _run_claude(
    task: str,
    cwd: str | None,
    timeout_s: int,
    model: str,
    bypass: bool,
) -> dict[str, Any]:
    cmd = [CLAUDE, "-p", task, "--output-format", "json"]
    if model:
        cmd += ["--model", model]
    if bypass:
        cmd += ["--permission-mode", "bypassPermissions"]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, cwd=cwd)
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveTimeout(
            f"claude -p did not finish within {timeout_s}s (task: {task[:120]}...)",
            state="no execution guarantee; the task may still be running",
        ) from exc
    if proc.returncode != 0:
        raise PrimitiveError(
            f"claude exited rc={proc.returncode}: {proc.stderr.strip()[:500]}",
            state="no execution guarantee",
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise PrimitiveError(
            "claude did not return JSON; raw output attached in 'state'",
            state=f"raw: {proc.stdout[:500]}",
        ) from exc


@contract(
    precondition="cwd exists (if given) and task is a non-empty instruction; "
    "allow_bypass_permissions=True additionally requires FRIDAY_ALLOW_DANGEROUS=1.",
    postcondition="Claude Code executes the task and returns its structured response.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError/PrimitiveTimeout from the subprocess; the task may have had "
    "side effects even on failure - verification is the caller's job. "
    "PreconditionError when allow_bypass_permissions=True but "
    "FRIDAY_ALLOW_DANGEROUS=1 is not set (checked before claude runs).",
    returns="dict: the `claude --output-format json` envelope (result, is_error, usage, ...).",
)
def run(
    task: str,
    *,
    cwd: str | None = None,
    timeout_s: int = 300,
    model: str = MODEL_ALIAS,
    allow_bypass_permissions: bool = False,
) -> dict[str, Any]:
    if not task or not task.strip():
        raise PrimitiveError("run requires a non-empty task", state="nothing executed")
    if allow_bypass_permissions:
        _require_dangerous_opt_in("dev.run(allow_bypass_permissions=True)")
    return _run_claude(task, cwd, timeout_s, model, allow_bypass_permissions)


@contract(
    precondition="cwd exists and command is a non-empty shell command string; "
    "FRIDAY_ALLOW_DANGEROUS=1 must be set - run_shell executes arbitrary shell.",
    postcondition="Claude Code runs the command and reports {exit_code, stdout, stderr}.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if claude fails or the result is not the required JSON; the "
    "command may have run regardless - verify effects with L2 before retrying. "
    "PreconditionError when FRIDAY_ALLOW_DANGEROUS=1 is not set (checked before "
    "claude runs - the gate is the authorization boundary).",
    returns="dict: {exit_code, stdout, stderr, model, duration_ms}.",
)
def run_shell(
    cwd: str,
    command: str,
    *,
    timeout_s: int = 120,
    model: str = MODEL_ALIAS,
    allow_bypass_permissions: bool = False,
) -> dict[str, Any]:
    if not command or not command.strip():
        raise PrimitiveError("run_shell requires a non-empty command", state="nothing executed")
    _require_dangerous_opt_in("dev.run_shell")
    task = (
        "Run the shell command below exactly as written, in the given working "
        "directory. Do not modify it, do not explain, do not wrap the output in "
        "markdown. Reply with a single JSON object having exactly these keys:\n"
        '{"exit_code": <int>, "stdout": <string>, "stderr": <string>}\n'
        f"Working directory: {cwd}\n"
        f"Command: {command}"
    )
    env = _run_claude(task, cwd, timeout_s, model, allow_bypass_permissions)
    result = env.get("result", "")
    try:
        parsed = json.loads(result) if isinstance(result, str) else result
    except json.JSONDecodeError as exc:
        raise PrimitiveError(
            "claude did not return the required JSON envelope",
            state=f"raw result: {str(result)[:500]}",
        ) from exc
    raw_code = parsed.get("exit_code", -1)
    try:
        exit_code = int(raw_code)
    except (TypeError, ValueError):
        raise PrimitiveError(
            "claude returned a non-integer exit_code",
            state=f"raw result: {str(result)[:500]}",
        ) from None
    return {
        "exit_code": exit_code,
        "stdout": str(parsed.get("stdout", "")),
        "stderr": str(parsed.get("stderr", "")),
        "model": model,
        "duration_ms": env.get("duration_ms"),
    }
