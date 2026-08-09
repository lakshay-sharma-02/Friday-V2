"""L3 - Deterministic plan executor.

A plan is a plain JSON list of {primitive, args, verify} steps - the exact
schema L4 will emit. The executor walks it under the state machine:

    PENDING -> RUNNING -> {VERIFIED, FAILED}
    FAILED -> RETRY (bounded, with backoff) -> RUNNING
    FAILED -> RETRY_EXHAUSTED -> ABORT (plan-level, loud, logged)

Rules (from the master plan):
  - Zero LLM calls. Fully testable against a hardcoded plan.
  - A primitive without a registered contract is never callable - the
    executor resolves every primitive through REGISTRY and refuses
    unknowns before doing anything.
  - Retry policy comes from the contract's idempotency class:
      idempotent       -> retry freely (read-only)
      commutative-safe -> retry freely (state converges)
      at-most-once     -> NO retry by default (retry can duplicate a
                          side effect, e.g. sending a message twice).
    A step may override with an explicit `retries` field, but the default
    is derived from the contract - the executor never guesses.
  - Verification goes through L2 checks only; the executor never mutates
    state to "make" a check pass. Verify failures are retried up to the
    step's allowed attempts, then the plan ABORTs loudly.
"""

from __future__ import annotations

import json
import math
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from friday.contracts import EXECUTOR_BLOCKED, REGISTRY, Idempotency
from friday.errors import FridayError
from friday.observability import emit_event, set_run_id, set_step_id

DEFAULT_BACKOFF_S = 1.0
DEFAULT_VERIFY_WAIT_S = 8.0
VERIFY_POLL_S = 0.5

# Plan-level result references: "$steps.2.result.address" resolves to the
# return value of step 2 (a dict), keyed by "address". This is how a
# deterministic plan composes steps (open, then close the thing just
# opened) without any LLM in the loop - L4 emits the same syntax.
# Integer segments index into LIST results: both "$steps.1.result.0.key"
# (dot) and "$steps.1.result[0].key" (bracket) are accepted - LLMs emit
# both, and a deterministic executor must not depend on which style the
# model chose. Quoted bracket keys ("$steps.2.result["message_id"]") are
# accepted too.
_REF = re.compile(r"^\$steps\.(\d+)\.result(.*)$")


# ------------------------------------------------------------------ schema


@dataclass
class VerifySpec:
    check: str
    expect: Any
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Step:
    primitive: str  # qualified name, e.g. "window.open_app" (REGISTRY key)
    args: dict[str, Any]
    verify: VerifySpec
    retries: int | None = None  # None -> derived from the contract's idempotency
    backoff_s: float = DEFAULT_BACKOFF_S
    verify_wait_s: float = DEFAULT_VERIFY_WAIT_S


@dataclass
class StepResult:
    step_id: int
    primitive: str
    status: str  # VERIFIED | FAILED | RETRY_EXHAUSTED | ABORTED
    attempts: int
    verify_actual: Any = None
    error: str | None = None


@dataclass
class PlanResult:
    goal: str
    status: str  # COMPLETED | ABORTED
    steps: list[StepResult] = field(default_factory=list)


# ------------------------------------------------------------- resolution


def _resolve_primitive(qualified: str) -> Callable:
    """Resolve 'module.function' ONLY if it has a registered contract and
    is not blocked. An unproven primitive is never callable by the
    executor, and a blocked one (EXECUTOR_BLOCKED, e.g. the destructive
    window.shutdown) is refused even though its contract exists.

    Import the module FIRST: @contract populates REGISTRY at import time,
    so a module that has not been imported yet looks unregistered even
    though its primitives are fully contracted."""
    import importlib

    module_name, _, fn_name = qualified.partition(".")
    try:
        mod = importlib.import_module(f"friday.l1.{module_name}")
    except ImportError as exc:
        # Unknown module must abort cleanly, not crash raw - the caller
        # turns KeyError into a loud, logged ABORT.
        raise KeyError(
            f"primitive module 'friday.l1.{module_name}' cannot be imported: {exc}"
        ) from exc
    if qualified not in REGISTRY:
        raise KeyError(
            f"primitive '{qualified}' has no registered contract; refusing to call it"
        )
    if qualified in EXECUTOR_BLOCKED:
        raise KeyError(
            f"primitive '{qualified}' is in EXECUTOR_BLOCKED; refusing to execute it"
        )
    fn = getattr(mod, fn_name)
    if not hasattr(fn, "__contract__"):
        raise KeyError(
            f"primitive '{qualified}' has a registry entry but no __contract__; refusing"
        )
    return fn


def _resolve_check(check: str) -> Callable:
    import importlib

    if check.startswith("checks."):
        name = check.split(".", 1)[1]
    else:
        name = check
    mod = importlib.import_module("friday.l2.checks")
    fn = getattr(mod, name, None)
    if fn is None:
        raise KeyError(f"unknown L2 check '{check}'")
    return fn


def _apply_refs(value: Any, results: dict[int, Any]) -> Any:
    """Replace $steps.N.result[.path] references with prior step results.
    Deterministic: a reference resolves only against steps already run."""
    if isinstance(value, dict):
        return {k: _apply_refs(v, results) for k, v in value.items()}
    if isinstance(value, list):
        return [_apply_refs(v, results) for v in value]
    if not isinstance(value, str):
        return value
    m = _REF.match(value)
    if not m:
        return value
    idx = int(m.group(1))
    if idx not in results:
        raise FridayError(f"reference {value!r}: step {idx} has not produced a result yet")
    val: Any = results[idx]
    rest = m.group(2)
    if rest and rest[0] not in ".[":
        # Not a real ref path (e.g. a literal "$steps.2.resultX" string) -
        # pass through untouched rather than erroring on the character.
        return value
    for part in _split_ref_path(rest, value):
        if part.isdigit():
            # Integer segment = positional index into a LIST result.
            # Negative indices are NOT accepted ("-1".isdigit() is False,
            # so it falls through to the dict branch and errors cleanly).
            if not isinstance(val, list):
                raise FridayError(
                    f"reference {value!r}: index {part} on a non-list result"
                )
            try:
                val = val[int(part)]
            except IndexError:
                raise FridayError(
                    f"reference {value!r}: list index {part} out of range (len={len(val)})"
                ) from None
        else:
            if not isinstance(val, dict) or part not in val:
                raise FridayError(f"reference {value!r}: no such path segment {part!r}")
            val = val[part]
    return val


def _split_ref_path(rest: str, full_ref: str) -> list[str]:
    """Parse the remainder of a $steps.N.result reference into segments,
    accepting dot ('.0', '.key'), bracket ('[0]', '["key"]', "['key']") and
    mixed forms. Returns [] for an empty remainder (the whole result)."""
    segs: list[str] = []
    i = 0
    n = len(rest)
    while i < n:
        c = rest[i]
        if c == ".":
            nxt_dot = rest.find(".", i + 1)
            nxt_brk = rest.find("[", i + 1)
            ends = [x for x in (nxt_dot, nxt_brk) if x != -1]
            nxt = min(ends) if ends else n
            part = rest[i + 1:nxt]
            if not part:
                raise FridayError(f"reference {full_ref!r}: empty path segment")
            segs.append(part)
            i = nxt
        elif c == "[":
            j = rest.find("]", i)
            if j == -1:
                raise FridayError(f"reference {full_ref!r}: unterminated bracket segment")
            inner = rest[i + 1:j].strip()
            if len(inner) >= 2 and inner[0] in ("\"", "'") and inner[-1] == inner[0]:
                inner = inner[1:-1]
            if not inner:
                raise FridayError(f"reference {full_ref!r}: empty bracket segment")
            segs.append(inner)
            i = j + 1
        else:
            raise FridayError(
                f"reference {full_ref!r}: unexpected character {c!r} after '.result'"
            )
    return segs


# ------------------------------------------------------------ state machine


def _default_retries(qualified: str) -> int | None:
    c = REGISTRY.get(qualified)
    if c is None:
        return None
    if c.idempotency == Idempotency.AT_MOST_ONCE:
        return 0  # never retry a side-effecting primitive by default
    if c.idempotency in (Idempotency.IDEMPOTENT, Idempotency.COMMUTATIVE_SAFE):
        return 2
    return None


def _verify_pass(
    check_fn: Callable,
    verify: VerifySpec,
    step_id: int,
    wait_s: float = DEFAULT_VERIFY_WAIT_S,
) -> tuple[bool, Any]:
    """Poll the L2 check up to wait_s for the expected value.
    Verification is read-only; it never mutates state to pass."""
    deadline = time.monotonic() + wait_s
    last: Any = None
    while time.monotonic() < deadline:
        set_step_id(str(step_id))
        try:
            last = check_fn(**verify.args)
        except (FridayError, TypeError, ValueError) as exc:
            # TypeError/ValueError = caller bug (bad kwarg to the check):
            # surface it as a verify failure through the state machine,
            # never a raw crash - a bad plan must ABORT loudly, not blow
            # a traceback past the executor. A caller bug is deterministic
            # (it cannot self-heal), so do not keep polling it - abort the
            # poll immediately. FridayError keeps polling: the underlying
            # state may still converge (e.g. mpv still starting).
            # NOTE: other exception types are deliberately left to crash
            # raw - an internal primitive bug must stay maximally loud,
            # never masked behind retries.
            last = f"ERROR:{type(exc).__name__}: {exc}"
            emit_event(
                layer="L3",
                primitive=f"step.{step_id}.verify",
                args=verify.args,
                exception=str(exc),
                extra={"check": verify.check},
            )
            if isinstance(exc, (TypeError, ValueError)):
                return False, last
        finally:
            set_step_id(None)
        if last == verify.expect:
            return True, last
        time.sleep(VERIFY_POLL_S)
    return False, last


def _reject_future_refs(value: Any, step_id: int) -> None:
    """Reject any $steps.N.result reference with N > step_id (a future
    step). Runs BEFORE the primitive executes: a bad verify ref must never
    execute a side effect first. Self-refs (N == step_id) and prior-step
    refs pass - they resolve after the primitive runs."""
    if isinstance(value, dict):
        for v in value.values():
            _reject_future_refs(v, step_id)
    elif isinstance(value, list):
        for v in value:
            _reject_future_refs(v, step_id)
    elif isinstance(value, str):
        for m in re.finditer(r"\$steps\.(\d+)\.result", value):
            n = int(m.group(1))
            if n > step_id:
                raise FridayError(
                    f"verify references future step {n} (current step {step_id})"
                )


def _step_emit(step_id: int, **kwargs: Any) -> None:
    """Emit an L3 event bound to a step, attaching step_id so every line of
    a step's lifecycle (PENDING/RUNNING/RETRY/VERIFIED/RETRY_EXHAUSTED) is
    correlated - a trace with null step_ids on verdict lines is exactly the
    correlation failure run_id/step_id exist to prevent."""
    set_step_id(str(step_id))
    try:
        emit_event(**kwargs)
    finally:
        set_step_id(None)


def run_plan(plan: dict[str, Any], *, run_id: str | None = None) -> PlanResult:
    """Execute a plan dict (goal + steps) under the L3 state machine.

    Returns a PlanResult; raises FridayError subclass on ABORT so the
    caller can distinguish a clean abort from an internal error.
    """
    if run_id:
        set_run_id(run_id)

    goal = str(plan.get("goal", ""))
    raw_steps = plan.get("steps", [])
    if not isinstance(raw_steps, list) or not raw_steps:
        raise FridayError("plan must contain a non-empty 'steps' list")

    emit_event(layer="L3", primitive="plan", args={"goal": goal}, result="PENDING")
    result = PlanResult(goal=goal, status="COMPLETED")

    results: dict[int, Any] = {}
    for idx, raw in enumerate(raw_steps, start=1):
        step_id = idx
        try:
            primitive = str(raw["primitive"])
            args = dict(raw.get("args") or {})
            v = raw.get("verify") or {}
            verify = VerifySpec(check=str(v["check"]), expect=v.get("expect"), args=dict(v.get("args") or {}))
            retries = int(raw["retries"]) if raw.get("retries") is not None else _default_retries(primitive)
            # backoff_s, like verify_wait_s below, is read from the step
            # level OR nested inside the verify object - same reasoning: a
            # timing field the planner intended must never be silently
            # ignored.
            backoff = float(
                raw.get("backoff_s", v.get("backoff_s", DEFAULT_BACKOFF_S))
            )
            # verify_wait_s is read from the step level OR nested inside the
            # verify object: LLM-generated plans have emitted it in both
            # places, and a timing field the planner intended must never be
            # silently ignored (that is how a wrong-looking plan can still
            # pass). Same meaning either way.
            verify_wait = float(
                raw.get("verify_wait_s", v.get("verify_wait_s", DEFAULT_VERIFY_WAIT_S))
            )
            # Reject non-positive/non-finite timing values loudly BEFORE any
            # step runs: verify_wait_s=0 would silently skip verification
            # (zero checks -> guaranteed false failure) and a negative
            # backoff_s would crash raw inside time.sleep().
            if backoff <= 0 or not math.isfinite(backoff):
                raise ValueError(f"backoff_s must be a positive finite number, got {backoff!r}")
            if verify_wait <= 0 or not math.isfinite(verify_wait):
                raise ValueError(f"verify_wait_s must be a positive finite number, got {verify_wait!r}")
            step = Step(
                primitive=primitive, args=args, verify=verify, retries=retries,
                backoff_s=backoff, verify_wait_s=verify_wait,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise FridayError(f"step {step_id}: malformed plan step: {exc}") from exc

        # Resolve step-result references in ARGS before the step runs (the
        # primitive needs them to execute), against prior steps' results.
        try:
            step.args = _apply_refs(step.args, results)
        except FridayError as exc:
            raise FridayError(f"step {step_id}: {exc}") from exc

        # Pre-flight VERIFY refs: reject future-step references NOW, before
        # the primitive runs - a typo'd ref must not execute a side effect
        # first. Self and prior refs are fine (resolved post-run).
        try:
            _reject_future_refs(step.verify.args, step_id)
            _reject_future_refs(step.verify.expect, step_id)
        except FridayError as exc:
            raise FridayError(f"step {step_id}: {exc}") from exc

        _step_emit(
            step_id,
            layer="L3",
            primitive=f"step.{step_id}",
            args={**step.args, "verify": {"check": step.verify.check, "expect": step.verify.expect}},
            result="PENDING",
        )

        try:
            set_step_id(str(step_id))
            fn = _resolve_primitive(step.primitive)
            check_fn = _resolve_check(step.verify.check)
        except KeyError as exc:
            set_step_id(None)
            result.steps.append(
                StepResult(step_id=step_id, primitive=step.primitive, status="ABORTED", attempts=0, error=str(exc))
            )
            result.status = "ABORTED"
            _step_emit(
                step_id,
                layer="L3", primitive=f"step.{step_id}",
                result="ABORT", exception=str(exc), extra={"reason": "unresolvable step"},
            )
            raise FridayError(f"plan aborted at step {step_id}: {exc}") from exc

        attempts = 0
        max_attempts = 1 + (step.retries or 0)
        step_status = "FAILED"
        verify_actual: Any = None
        error: str | None = None

        while attempts < max_attempts:
            attempts += 1
            error = None  # attempt-local: a failed attempt must not smear a later VERIFIED
            _step_emit(
                step_id,
                layer="L3",
                primitive=f"step.{step_id}",
                args=step.args,
                result="RUNNING",
                extra={"attempt": attempts, "max_attempts": max_attempts},
            )
            set_step_id(str(step_id))
            try:
                return_value = fn(**step.args)
                results[step_id] = return_value  # available to later steps
            except (FridayError, TypeError, ValueError) as exc:
                # TypeError/ValueError = caller bug (bad kwarg to the
                # primitive): a FAILED step, never a raw crash - the state
                # machine exists so every failure is logged, retried per
                # contract policy, and ABORTs loudly if it persists.
                # Other exception types intentionally still crash raw:
                # an internal primitive bug must stay maximally loud,
                # never silently retried into an endless loop.
                error = f"{type(exc).__name__}: {exc}"
                emit_event(layer="L3", primitive=f"step.{step_id}", exception=error, result="FAILED")
            finally:
                set_step_id(None)

            # Resolve VERIFY references now: the step's own result exists
            # (a send step verifies its returned message_id via
            # "$steps.N.result.message_id" with N == its own number), plus
            # every prior step's. Resolve into a fresh spec each attempt so
            # a retry re-resolves against the new result. A ref that cannot
            # resolve (e.g. the step's primitive failed, so it produced no
            # result) is a verify failure, never a crash.
            try:
                resolved_verify = VerifySpec(
                    check=step.verify.check,
                    expect=_apply_refs(step.verify.expect, results),
                    args=_apply_refs(step.verify.args, results),
                )
                ok, verify_actual = _verify_pass(
                    check_fn, resolved_verify, step_id, wait_s=step.verify_wait_s
                )
            except FridayError as exc:
                ok, verify_actual = False, f"REF_ERROR:{exc}"
                _step_emit(
                    step_id,
                    layer="L3",
                    primitive=f"step.{step_id}.verify",
                    exception=str(exc),
                    extra={"check": step.verify.check},
                )
            if ok:
                step_status = "VERIFIED"
                break
            if attempts >= max_attempts:
                break
            # bounded backoff before the retry
            _step_emit(
                step_id,
                layer="L3",
                primitive=f"step.{step_id}",
                result="RETRY",
                extra={"attempt": attempts, "backoff_s": step.backoff_s, "verify_actual": str(verify_actual)},
            )
            time.sleep(step.backoff_s)

        if step_status == "VERIFIED":
            _step_emit(
                step_id,
                layer="L3",
                primitive=f"step.{step_id}",
                result="VERIFIED",
                extra={"attempts": attempts, "verify_actual": str(verify_actual)},
            )
        else:
            step_status = "RETRY_EXHAUSTED"
            msg = error or f"verify never matched {step.verify.expect!r} (last: {verify_actual!r})"
            _step_emit(
                step_id,
                layer="L3",
                primitive=f"step.{step_id}",
                result="RETRY_EXHAUSTED",
                exception=msg,
                extra={"attempts": attempts},
            )
            _step_emit(
                step_id,
                layer="L3",
                primitive="plan",
                result="ABORT",
                exception=f"step {step_id} exhausted retries: {msg}",
            )
            result.status = "ABORTED"
            result.steps.append(
                StepResult(step_id=step_id, primitive=step.primitive, status="ABORTED", attempts=attempts, verify_actual=verify_actual, error=msg)
            )
            raise FridayError(f"plan aborted at step {step_id}: {msg}")

        result.steps.append(
            StepResult(step_id=step_id, primitive=step.primitive, status=step_status, attempts=attempts, verify_actual=verify_actual, error=error)
        )

    emit_event(layer="L3", primitive="plan", result="COMPLETED", extra={"steps": len(result.steps)})
    return result


def load_plan(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())
