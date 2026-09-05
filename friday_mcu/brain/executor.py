"""Deterministic plan executor.

Adapted from V8 L3 with:
- Event bus integration (real-time step progress)
- Streaming events for UI
- Adaptive retry from memory

Zero LLM calls. Fully testable against a hardcoded plan.
"""

from __future__ import annotations

import re
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, cast

from friday_mcu.core.contracts import EXECUTOR_BLOCKED, REGISTRY, Idempotency
from friday_mcu.core.errors import FridayError
from friday_mcu.core.events import EventType, emit

DEFAULT_BACKOFF_S = 1.0
_DEFAULT_VERIFY_WAIT_S = 8.0
VERIFY_POLL_S = 0.5

# $steps.N.result reference pattern
_REF = re.compile(r"^\$steps\.(\d+)\.result(.*)$")


# -------------------------------------------------------------- schema


@dataclass
class VerifySpec:
    check: str
    expect: Any
    args: dict[str, Any] = field(default_factory=dict)


@dataclass
class Step:
    primitive: str
    args: dict[str, Any]
    verify: VerifySpec
    retries: int | None = None
    backoff_s: float = DEFAULT_BACKOFF_S
    verify_wait_s: float = _DEFAULT_VERIFY_WAIT_S


@dataclass
class StepResult:
    step_id: int
    primitive: str
    status: str  # VERIFIED | FAILED | RETRY_EXHAUSTED | ABORTED
    attempts: int
    verify_actual: Any = None
    error: str | None = None
    result: Any = None
    retry_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class PlanResult:
    goal: str
    status: str  # COMPLETED | ABORTED
    steps: list[StepResult] = field(default_factory=list)
    confidence: float = 0.0


# ----------------------------------------------------------- resolution


def _resolve_primitive(qualified: str) -> Callable:
    """Resolve a primitive ONLY if it has a registered contract."""
    import importlib

    module_name, _, fn_name = qualified.partition(".")
    try:
        mod = importlib.import_module(f"friday_mcu.adapters.{module_name}")
    except ImportError as exc:
        raise KeyError(
            f"adapter module 'friday_mcu.adapters.{module_name}' cannot be imported: {exc}"
        ) from exc
    if qualified not in REGISTRY:
        raise KeyError(f"primitive '{qualified}' has no registered contract")
    if qualified in EXECUTOR_BLOCKED:
        raise KeyError(f"primitive '{qualified}' is in EXECUTOR_BLOCKED")
    fn = getattr(mod, fn_name)
    if not hasattr(fn, "__contract__"):
        raise KeyError(f"primitive '{qualified}' has no __contract__")
    return cast(Callable[..., Any], fn)


def _resolve_check(check: str) -> Callable:
    """Resolve an L2 check by name."""
    import importlib

    name = check.split(".", 1)[1] if check.startswith("checks.") else check
    try:
        mod = importlib.import_module("friday_mcu.brain.checks")
    except ImportError:
        raise KeyError(f"checks module not available")
    fn = getattr(mod, name, None)
    if fn is None:
        raise KeyError(f"unknown L2 check '{check}'")
    return cast(Callable[..., Any], fn)


def _apply_refs(value: Any, results: dict[int, Any]) -> Any:
    """Replace $steps.N.result references with prior step results."""
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
    if not rest:
        return val
    # Parse path segments
    for part in _split_path(rest):
        if part.isdigit():
            if not isinstance(val, list):
                raise FridayError(f"reference {value!r}: index {part} on a non-list")
            try:
                val = val[int(part)]
            except IndexError:
                raise FridayError(f"reference {value!r}: index out of range")
        else:
            if not isinstance(val, dict) or part not in val:
                raise FridayError(f"reference {value!r}: no such key {part!r}")
            val = val[part]
    return val


def _split_path(rest: str) -> list[str]:
    """Parse a reference path into segments."""
    segs: list[str] = []
    i = 0
    n = len(rest)
    while i < n:
        c = rest[i]
        if c == ".":
            nxt = rest.find(".", i + 1)
            nxt_brk = rest.find("[", i + 1)
            ends = [x for x in (nxt, nxt_brk) if x != -1]
            end = min(ends) if ends else n
            part = rest[i + 1 : end]
            if part:
                segs.append(part)
            i = end
        elif c == "[":
            j = rest.find("]", i)
            if j == -1:
                raise FridayError(f"unterminated bracket in path")
            inner = rest[i + 1 : j].strip()
            if len(inner) >= 2 and inner[0] in ('"', "'") and inner[-1] == inner[0]:
                inner = inner[1:-1]
            if inner:
                segs.append(inner)
            i = j + 1
        else:
            i += 1
    return segs


# -------------------------------------------------------- retry policy


def _default_retries(qualified: str) -> int | None:
    """Derive retry count from the contract's idempotency class."""
    c = REGISTRY.get(qualified)
    if c is None:
        return None
    if c.idempotency == Idempotency.AT_MOST_ONCE:
        return 0
    if c.idempotency in (Idempotency.IDEMPOTENT, Idempotency.COMMUTATIVE_SAFE):
        return 2
    return None


# -------------------------------------------------------- verification


def _verify_pass(
    check_fn: Callable,
    verify: VerifySpec,
    step_id: int,
    wait_s: float = _DEFAULT_VERIFY_WAIT_S,
) -> tuple[bool, Any]:
    """Poll the L2 check up to wait_s for the expected value."""
    deadline = time.monotonic() + wait_s
    last: Any = None
    while time.monotonic() < deadline:
        try:
            last = check_fn(**verify.args)
        except (FridayError, TypeError, ValueError) as exc:
            last = f"ERROR:{type(exc).__name__}: {exc}"
            if isinstance(exc, (TypeError, ValueError)):
                return False, last
        if last == verify.expect:
            return True, last
        time.sleep(VERIFY_POLL_S)
    return False, last


# -------------------------------------------------------- state machine


def run_plan(
    plan_dict: dict[str, Any],
    *,
    run_id: str | None = None,
    confidence: float = 0.0,
) -> PlanResult:
    """Execute a plan dict under the L3 state machine.

    Returns a PlanResult; raises FridayError on ABORT.
    """
    goal = str(plan_dict.get("goal", ""))
    raw_steps = plan_dict.get("steps", [])
    if not isinstance(raw_steps, list) or not raw_steps:
        raise FridayError("plan must contain a non-empty 'steps' list")

    emit(
        EventType.GOAL_START,
        source="executor",
        data={"goal": goal, "steps": len(raw_steps)},
        correlation_id=run_id,
    )

    result = PlanResult(goal=goal, status="COMPLETED", confidence=confidence)
    results: dict[int, Any] = {}

    for idx, raw in enumerate(raw_steps, start=1):
        step_id = idx
        try:
            primitive = str(raw["primitive"])
            args = dict(raw.get("args") or {})
            v = raw.get("verify") or {}
            verify = VerifySpec(
                check=str(v["check"]),
                expect=v.get("expect"),
                args=dict(v.get("args") or {}),
            )
            retries = (
                int(raw["retries"])
                if raw.get("retries") is not None
                else _default_retries(primitive)
            )
            backoff = float(raw.get("backoff_s", DEFAULT_BACKOFF_S))
            verify_wait = float(raw.get("verify_wait_s", v.get("verify_wait_s", _DEFAULT_VERIFY_WAIT_S)))
            step = Step(
                primitive=primitive,
                args=args,
                verify=verify,
                retries=retries,
                backoff_s=backoff,
                verify_wait_s=verify_wait,
            )
        except (KeyError, TypeError, ValueError) as exc:
            raise FridayError(f"step {step_id}: malformed: {exc}") from exc

        # Resolve step-result references in ARGS
        try:
            step.args = _apply_refs(step.args, results)
        except FridayError as exc:
            # A step whose inputs cannot be produced (e.g. an earlier gather
            # returned nothing) is a LOUD failure, never a silent skip: a plan
            # that "summarize the latest email" on an empty inbox must not be
            # reported COMPLETED with no summary. The plan aborts here so the
            # caller records an honest FAIL.
            emit(
                EventType.STEP_FAILED,
                source="executor",
                data={"step_id": step_id, "status": "ABORTED", "error": str(exc)},
                correlation_id=run_id,
            )
            result.steps.append(
                StepResult(
                    step_id=step_id,
                    primitive=step.primitive,
                    status="ABORTED",
                    attempts=0,
                    error=str(exc),
                )
            )
            result.status = "ABORTED"
            raise FridayError(f"plan aborted at step {step_id}: {exc}") from exc

        # Emit step start
        emit(
            EventType.STEP_START,
            source="executor",
            data={"step_id": step_id, "primitive": step.primitive, "args": step.args},
            correlation_id=run_id,
        )

        # Resolve primitive
        try:
            fn = _resolve_primitive(step.primitive)
        except KeyError as exc:
            emit(
                EventType.STEP_FAILED,
                source="executor",
                data={"step_id": step_id, "error": str(exc)},
                correlation_id=run_id,
            )
            result.steps.append(
                StepResult(
                    step_id=step_id,
                    primitive=step.primitive,
                    status="ABORTED",
                    attempts=0,
                    error=str(exc),
                )
            )
            result.status = "ABORTED"
            raise FridayError(f"plan aborted at step {step_id}: {exc}") from exc

        # Resolve check
        try:
            check_fn = _resolve_check(step.verify.check)
        except KeyError as exc:
            result.steps.append(
                StepResult(
                    step_id=step_id,
                    primitive=step.primitive,
                    status="ABORTED",
                    attempts=0,
                    error=str(exc),
                )
            )
            result.status = "ABORTED"
            raise FridayError(f"plan aborted at step {step_id}: {exc}") from exc

        # Execute with retry
        attempts = 0
        max_attempts = 1 + (step.retries or 0)
        step_status = "FAILED"
        verify_actual: Any = None
        error: str | None = None
        retry_history: list[dict[str, Any]] = []
        return_value: Any = None

        while attempts < max_attempts:
            attempts += 1
            error = None
            t_attempt = time.monotonic()

            try:
                t0 = time.monotonic()
                return_value = fn(**step.args)
                duration_ms = (time.monotonic() - t0) * 1000
                results[step_id] = return_value
                emit(
                    EventType.PRIMITIVE_RESULT,
                    source="executor",
                    data={"step_id": step_id, "primitive": step.primitive, "duration_ms": duration_ms},
                    correlation_id=run_id,
                )
            except (FridayError, TypeError, ValueError) as exc:
                error = f"{type(exc).__name__}: {exc}"
                emit(
                    EventType.PRIMITIVE_ERROR,
                    source="executor",
                    data={"step_id": step_id, "error": error},
                    correlation_id=run_id,
                )

            # Verify
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

            # Verification is the ONLY proof a step succeeded. A primitive's
            # own return value is never trusted: a "write file" step whose
            # checks.file_exists stays False must fail loudly, not complete.
            # Plans that should tolerate empty data express that in the check
            # (e.g. checks.call_succeeded with expect True), never by bypassing
            # verification here.

            # L0: one structured line per attempt when running under a
            # correlated run (CLI/watcher/API all pass run_id).
            if run_id:
                from friday_mcu.core.observability import emit_log
                emit_log(
                    layer="executor",
                    primitive=step.primitive,
                    duration_ms=round((time.monotonic() - t_attempt) * 1000, 1),
                    exception=error,
                    extra={
                        "run_id": run_id,
                        "step_id": step_id,
                        "attempt": attempts,
                        "verified": bool(ok),
                        "outcome": "verified" if ok else ("primitive_error" if error else "verify_failed"),
                    },
                )

            if ok:
                step_status = "VERIFIED"
                break

            if attempts >= max_attempts:
                break

            # Retry
            retry_history.append({
                "attempt": attempts,
                "error": error or f"verify failed: {verify_actual}",
                "backoff_s": step.backoff_s,
                "timestamp": datetime.now(UTC).isoformat(timespec="seconds"),
            })
            emit(
                EventType.STEP_RETRY,
                source="executor",
                data={"step_id": step_id, "attempt": attempts, "backoff_s": step.backoff_s},
                correlation_id=run_id,
            )
            time.sleep(step.backoff_s)

        # Record step result
        if step_status == "VERIFIED":
            emit(
                EventType.STEP_COMPLETE,
                source="executor",
                data={"step_id": step_id, "status": step_status, "attempts": attempts},
                correlation_id=run_id,
            )
        else:
            step_status = "RETRY_EXHAUSTED"
            msg = error or f"verify never matched (last: {verify_actual!r})"
            emit(
                EventType.STEP_FAILED,
                source="executor",
                data={"step_id": step_id, "status": "RETRY_EXHAUSTED", "error": msg},
                correlation_id=run_id,
            )
            result.status = "ABORTED"
            result.steps.append(
                StepResult(
                    step_id=step_id,
                    primitive=step.primitive,
                    status="ABORTED",
                    attempts=attempts,
                    verify_actual=verify_actual,
                    error=msg,
                    retry_history=retry_history,
                )
            )
            raise FridayError(f"plan aborted at step {step_id}: {msg}")

        result.steps.append(
            StepResult(
                step_id=step_id,
                primitive=step.primitive,
                status=step_status,
                attempts=attempts,
                verify_actual=verify_actual,
                error=error,
                result=return_value,
                retry_history=retry_history,
            )
        )

    emit(
        EventType.GOAL_COMPLETE,
        source="executor",
        data={"goal": goal, "steps": len(result.steps)},
        correlation_id=run_id,
    )
    return result
