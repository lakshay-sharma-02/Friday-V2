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
from friday.lessons import render_known_mistakes

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
    # FRIDAY_MODEL: the WHOLE-AGENT emergency escape hatch (2026-08-13).
    # Every LLM consumer on this machine (planner, triage, digest,
    # summarize) flows through this one function, and the default model
    # alias routes through the user's local router to a free provider
    # model that can be DEGRADED for hours ('DEGRADED function cannot be
    # invoked', observed live). Setting FRIDAY_MODEL to a full model id
    # (e.g. 'oc/laguna-s-2.1-free') repoints EVERY call at a working
    # model - the loop stays alive instead of dead whenever the default
    # alias' provider is down. The override wins over the passed model
    # arg by design: it is the emergency escape hatch, and the per-consumer
    # knobs (e.g. FRIDAY_TRIAGE_MODEL) merely supply the model arg that
    # FRIDAY_MODEL can in turn supersede.
    if os.environ.get("FRIDAY_MODEL"):
        model = os.environ["FRIDAY_MODEL"]
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


# Default instruction for dev.digest - the cross-project digest prompt.
# The user's Phase C spec: (a) a plain summary of what happened in each
# repo, (b) at most 1-2 CONCRETE suggestions for how something in one
# repo could apply to the other - an actual specific pattern or piece of
# code, never vague "consider synergies" language.
DEFAULT_DIGEST_INSTRUCTION = (
    "You are Friday's cross-project digest. Below is recent activity from "
    "the user's projects, each under a label. Produce:\n"
    "(a) a plain 2-4 sentence summary of what happened in each project, and\n"
    "(b) at most 1-2 CONCRETE suggestions for how something in one project "
    "could apply to another - an actual specific pattern, piece of code, "
    "or approach that could transfer, not vague 'consider synergies' "
    "language. If the content is too thin for a specific suggestion, say so "
    "honestly rather than inventing one.\n"
    "Reply with ONLY the digest text."
)


@contract(
    precondition="context is a non-empty dict mapping labels to gathered "
    "content (strings or lists of strings); instruction (if given) is a "
    "non-empty string.",
    postcondition="Returns an LLM-generated plain-text digest of the "
    "gathered context. Makes NO state changes. NOTE: internally invokes "
    "the LLM via _run_claude - a DELIBERATE, documented exception to the "
    "rule 'primitives don't call LLMs' (a digest is a terminal read-only "
    "artifact, exactly like gmail.summarize).",
    idempotency=Idempotency.IDEMPOTENT,  # re-digesting is harmless (but see note)
    failure_mode="PreconditionError for an empty context or instruction; "
    "PrimitiveError when the LLM returns no usable digest text. NOTE: "
    "because the step is idempotent the executor may retry it, and each "
    "attempt is a fresh LLM call - the digest text is NOT guaranteed "
    "identical across attempts (it is a generated artifact, not stable "
    "state), and every attempt is a paid full-tier call.",
    returns="str: the digest text (the task's human-verifiable deliverable).",
)
def digest(
    context: dict[str, Any],
    instruction: str = DEFAULT_DIGEST_INSTRUCTION,
) -> str:
    """Synthesize a plain-text cross-project digest from gathered context.

    `context` maps labels (e.g. "friday git log", "agent-reach
    changelog") to content - strings or lists of strings, the outputs of
    read-only gather primitives (git.log / files.read_text). The LLM
    receives label-tagged content, so its summary can name each project;
    the returned text is the digest deliverable. Uses the same documented
    LLM-in-primitive exception as gmail.summarize (a digest is a terminal
    read-only artifact with no external state to verify against)."""
    if not isinstance(context, dict) or not context:
        raise PreconditionError("digest requires a non-empty 'context' dict")
    if not instruction or not instruction.strip():
        raise PreconditionError("digest requires a non-empty instruction")
    blocks: list[str] = []
    for label, content in context.items():
        if isinstance(content, (list, tuple)):
            rows = "\n".join(str(x)[:300] for x in content)
            blocks.append(f"[{label}]\n{rows}")
        else:
            blocks.append(f"[{label}]\n{str(content)[:12000]}")
    # the bounded, human-approved KNOWN MISTAKES block for synthesis
    # ("" when none approved) - most importantly the attribution lesson:
    # never credit a repo with a mechanism that is not in ITS OWN context
    known = render_known_mistakes("digest")
    task = f"{instruction}\n{known}\n\n--- gathered context ---\n\n" + "\n\n".join(blocks)
    # Deliberate, documented exception (mirrors gmail.summarize): call the
    # private _run_claude directly instead of the observed dev.run - the
    # task string embeds repo content, and the redaction discipline keeps
    # content out of the L0 log; dev.run would log its bound args. The
    # dev.digest L1 call itself is fully observed ({labels} -> digest).
    res = _run_claude(task, None, 180, MODEL_ALIAS, False)
    digest_text = ""
    if isinstance(res, dict):
        inner = res.get("result")
        if isinstance(inner, str):
            digest_text = inner
        elif isinstance(inner, dict):
            digest_text = str(inner.get("digest") or inner.get("result") or "")
    digest_text = digest_text.strip()
    if not digest_text:
        raise PrimitiveError(
            "dev.digest: LLM returned no usable digest text",
            state="digest not produced",
        )
    return digest_text
