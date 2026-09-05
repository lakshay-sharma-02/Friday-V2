"""Dev adapter — Claude CLI substrate.

This is the LLM backbone: Friday calls `claude -p` for planning,
digests, and any task requiring reasoning. The same substrate
powers both L4 planning and L1 digest calls.

The bypass flag (allow_bypass_permissions) is an explicit opt-in
for arbitrary shell access — never default.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from typing import Any

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PreconditionError, PrimitiveError

MODEL_ALIAS = "opus"
DEFAULT_TIMEOUT_S = 120


@contract(
    precondition="prompt is a non-empty string.",
    postcondition="Returns the LLM response as a dict with 'result' key.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if claude CLI fails or times out.",
    returns="dict: {result: str, is_error: bool, model: str}.",
)
def run(
    prompt: str,
    cwd: str = ".",
    timeout_s: int = DEFAULT_TIMEOUT_S,
    model: str = "",
    allow_bypass_permissions: bool = False,
) -> dict[str, Any]:
    """Run a prompt through Claude CLI and return the response.

    This is the primary LLM interface: goal planning, digest synthesis,
    and any task that needs reasoning.

    allow_bypass_permissions=True passes --dangerously-skip-permissions
    to claude, which allows arbitrary shell execution. This flag is
    NEVER set by the planner or executor — only by explicit user opt-in.
    """
    if not prompt or not prompt.strip():
        raise PreconditionError("run requires a non-empty prompt")

    if allow_bypass_permissions and os.environ.get("FRIDAY_ALLOW_DANGEROUS") != "1":
        raise PreconditionError(
            "FRIDAY_ALLOW_DANGEROUS=1 is required for bypass permissions"
        )

    model = model or os.environ.get("FRIDAY_MODEL", MODEL_ALIAS)
    cmd = ["claude", "-p", "--output-format", "json", "--model", model]

    if allow_bypass_permissions:
        cmd.append("--dangerously-skip-permissions")

    try:
        # shell=True + a LIST is a POSIX trap: on Linux the shell runs only
        # the first element and silently drops every flag after it (so
        # -p / --output-format json / --model never reach claude). Use a
        # direct exec on POSIX; keep cmd.exe on Windows only, where a .cmd
        # shim cannot be exec'd directly and the list must be joined first.
        if sys.platform == "win32":
            proc_args: Any = subprocess.list2cmdline(cmd)
            run_kwargs: dict[str, Any] = {"shell": True}
        else:
            proc_args = cmd
            run_kwargs = {}
        result = subprocess.run(
            proc_args,
            input=prompt,
            capture_output=True,
            text=True,
            timeout=timeout_s,
            cwd=cwd,
            **run_kwargs,
        )
    except FileNotFoundError as exc:
        raise PrimitiveError(
            "claude CLI not found — install it first",
            state="no LLM available",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveError(
            f"claude timed out after {timeout_s}s",
            state="prompt may have been too long",
        ) from exc

    if result.returncode != 0:
        return {
            "result": f"Error (rc={result.returncode}): {result.stderr[:2000]}",
            "is_error": True,
            "model": model,
        }

    # Parse JSON output
    try:
        response = json.loads(result.stdout)
        return {
            "result": response.get("result", result.stdout),
            "is_error": response.get("is_error", False),
            "model": model,
        }
    except json.JSONDecodeError:
        return {
            "result": result.stdout,
            "is_error": False,
            "model": model,
        }


@contract(
    precondition="prompt is a non-empty string.",
    postcondition="Returns the LLM response as plain text.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if claude CLI fails or times out.",
    returns="str: the LLM response text.",
)
def run_shell(
    prompt: str,
    cwd: str = ".",
    timeout_s: int = DEFAULT_TIMEOUT_S,
) -> str:
    """Run a prompt through Claude CLI with shell access.

    DANGER: This allows arbitrary shell execution. Only use when
    FRIDAY_ALLOW_DANGEROUS=1 is set.
    """
    if os.environ.get("FRIDAY_ALLOW_DANGEROUS") != "1":
        raise PreconditionError(
            "FRIDAY_ALLOW_DANGEROUS=1 is required for run_shell"
        )
    result = run(
        prompt,
        cwd=cwd,
        timeout_s=timeout_s,
        allow_bypass_permissions=True,
    )
    return result.get("result", "")


@contract(
    precondition="context is a non-empty dict with gathered data.",
    postcondition="Returns a synthesized digest as plain text.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if the LLM call fails.",
    returns="str: the synthesized digest.",
)
def digest(
    context: dict[str, Any],
    instruction: str = "Synthesize a concise weekly digest from this data.",
    timeout_s: int = 120,
) -> str:
    """LLM-in-primitive: cross-project digest synthesis.

    Takes gathered context (git logs, status docs, etc.) and produces
    a synthesized digest. The one LLM-in-primitive exception — a digest
    is a terminal read-only artifact.
    """
    # Build the prompt from context
    parts = [instruction, ""]
    for label, data in context.items():
        if isinstance(data, str):
            parts.append(f"## {label}\n{data[:3000]}")
        elif isinstance(data, list):
            text = "\n".join(
                str(item) for item in data[:50]
            )
            parts.append(f"## {label}\n{text[:3000]}")
        elif isinstance(data, dict):
            text = json.dumps(data, indent=2, default=str)[:3000]
            parts.append(f"## {label}\n{text}")
        else:
            parts.append(f"## {label}\n{str(data)[:3000]}")

    prompt = "\n\n".join(parts)
    result = run(prompt, timeout_s=timeout_s)
    if result.get("is_error"):
        raise PrimitiveError(f"Digest synthesis failed: {result['result'][:200]}")
    return str(result.get("result", ""))


class DevAdapter(Adapter):
    """Dev adapter — LLM backbone."""

    @property
    def name(self) -> str:
        return "dev"

    @property
    def capabilities(self) -> list[str]:
        return ["run", "run_shell", "digest"]

    async def initialize(self) -> None:
        # Check if claude CLI is available
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise PrimitiveError("claude CLI not working properly")
        except FileNotFoundError as exc:
            raise PrimitiveError("claude CLI not found — install it first") from exc

    async def execute(self, action: str, **kwargs: Any) -> Any:
        if action == "run":
            return run(**kwargs)
        elif action == "run_shell":
            return run_shell(**kwargs)
        elif action == "digest":
            return digest(**kwargs)
        raise PrimitiveError(f"Unknown dev action: {action}")

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        try:
            # Same platform split as run(): never shell=True + a list on POSIX
            # (it would silently drop --version); Windows needs cmd.exe because
            # the claude npm shim is a .cmd file.
            if sys.platform == "win32":
                args: Any = subprocess.list2cmdline(["claude", "--version"])
                run_kwargs: dict[str, Any] = {"shell": True}
            else:
                args = ["claude", "--version"]
                run_kwargs = {}
            result = subprocess.run(
                args,
                capture_output=True,
                timeout=10,
                **run_kwargs,
            )
            return result.returncode == 0
        except Exception:
            return False


try:
    register_adapter(DevAdapter())
except Exception:
    pass
