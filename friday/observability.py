"""L0 - Observability.

One structured JSON log line per primitive call:
    {run_id, step_id, layer, primitive, args, result, exception,
     duration_ms, timestamp}

This is infrastructure, not a pipeline stage: every layer writes through it.
The @observe decorator is applied automatically inside the @contract
decorator (friday/contracts.py), so every contract-registered primitive is
instrumented with zero call-site edits - Gate 2's explicit requirement.

Config (env vars):
  FRIDAY_LOG_FILE          - log path (default: var/logs/friday.jsonl)
  FRIDAY_RUN_ID            - fixed run id for a whole batch (default: random)
  FRIDAY_OBSERVABILITY=0   - disable logging (never breaks the primitive)
"""

from __future__ import annotations

import contextvars
import functools
import inspect
import json
import os
import sys
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LOG_FILE = PROJECT_ROOT / "var" / "logs" / "friday.jsonl"

_log_lock = threading.Lock()
# run_id is the trace link for one logical run. Default: one id per process.
# L3 (the executor) calls set_run_id() at the start of each plan execution so
# that multiple goals run inside one process still produce per-goal traces -
# a process-frozen id would make every goal's lines share one id, which is
# exactly the correlation failure run_id exists to prevent.
_RUN_ID: str = os.environ.get("FRIDAY_RUN_ID") or uuid.uuid4().hex[:12]

# Current logical step within a run. L3 sets this before invoking a primitive
# or check so every line emitted for that step carries the same step_id -
# otherwise step correlation would be impossible to recover from the log.
_step_ctx: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "friday_step_id", default=None
)


def set_step_id(step_id: str | None) -> None:
    _step_ctx.set(step_id)


def current_step_id() -> str | None:
    return _step_ctx.get()


def set_run_id(run_id: str) -> None:
    """Set the run_id for the current logical run (thread-safe). Called by
    L3 at the start of each plan execution."""
    global _RUN_ID
    with _log_lock:
        _RUN_ID = run_id or uuid.uuid4().hex[:12]

# Keys whose values are never written to the log, even in args/results.
# 'pass' is deliberately absent - it would over-match harmless keys like
# allow_bypass_permissions.
_SENSITIVE_KEYS = (
    "password", "passwd", "pwd", "token", "secret", "api_key", "apikey", "authorization",
)

_MAX_STR = 500
_MAX_COLLECTION = 20


def _redact(key: str, value: Any) -> Any:
    if any(s in key.lower() for s in _SENSITIVE_KEYS):
        return "<redacted>"
    return value


def _clip(value: Any, depth: int = 0) -> Any:
    """Cap log payload size: clip long strings, bound list/dict sizes."""
    if depth > 3:
        return "<too deep>"
    if isinstance(value, str):
        if len(value) > _MAX_STR:
            return value[:_MAX_STR] + f"...<+{len(value) - _MAX_STR} chars>"
        return value
    if isinstance(value, dict):
        return {
            k: _clip(_redact(str(k), v), depth + 1)
            for k, v in list(value.items())[:_MAX_COLLECTION]
        }
    if isinstance(value, (list, tuple)):
        return [_clip(v, depth + 1) for v in list(value)[:_MAX_COLLECTION]]
    return value


def _bind_args(fn: Callable, args: tuple, kwargs: dict) -> dict[str, Any]:
    try:
        bound = inspect.signature(fn).bind(*args, **kwargs)
        # Redact by argument NAME too - a kwarg literally named `password`
        # must never reach the log, even though it is not a nested key.
        return {k: _clip(_redact(k, v)) for k, v in bound.arguments.items()}
    except (TypeError, ValueError):
        # Unknown signature (e.g., a builtin) - fall back to raw positional.
        return {
            "args": [repr(a) for a in args][:_MAX_COLLECTION],
            **{k: _clip(_redact(k, v)) for k, v in kwargs.items()},
        }


def _qualified_name(fn: Callable) -> str:
    """module.function, e.g. 'telegram.send_text' - so logs disambiguate
    primitives that share a bare name across modules (whatsapp/telegram/
    discord all have send_text)."""
    module = fn.__module__.rsplit(".", 1)[-1]
    return f"{module}.{fn.__name__}"


def _run_id() -> str:
    return _RUN_ID


def _log_file() -> Path:
    return Path(os.environ.get("FRIDAY_LOG_FILE", str(DEFAULT_LOG_FILE)))


def emit_event(
    *,
    layer: str,
    primitive: str,
    args: Any = None,
    result: Any = None,
    exception: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Public: write one structured line for a non-primitive event (L3 state
    transitions, L2 verdicts, etc.). step_id comes from the current step
    context if set, else None."""
    rec: dict[str, Any] = {
        "run_id": _run_id(),
        "step_id": current_step_id(),
        "layer": layer,
        "primitive": primitive,
        "args": _clip(args) if args is not None else None,
        "result": result,
        "exception": exception,
        "duration_ms": 0.0,
        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
    }
    if extra:
        rec["extra"] = extra
    _emit(rec)


def _emit(record: dict[str, Any]) -> None:
    """Append one JSON line. Never raises - observability must not break
    the primitive that triggered it. If the log file cannot be written, fall
    back to stderr so a broken log is not silently invisible."""
    if os.environ.get("FRIDAY_OBSERVABILITY") == "0":
        return
    try:
        path = _log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, default=str, ensure_ascii=False)
        with _log_lock:
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception as exc:
        try:
            print(f"[friday-observability] log write failed ({exc}); dropping line", file=sys.stderr)
        except Exception:
            pass


def observe(layer: str = "L1", redact_result: bool = False) -> Callable[[F], F]:
    """Decorator: emit one structured log line per call, result or
    exception. Preserves the wrapped function's metadata via wraps.

    redact_result=True: the returned value is written as "<redacted>"
    instead of the value itself. Use it for primitives whose RESULT is a
    secret (e.g. credentials() returns the credentials dict) - key-name
    redaction inside _clip is not enough when the whole result is secret.
    """

    def deco(fn: F) -> F:
        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            if os.environ.get("FRIDAY_OBSERVABILITY") == "0":
                return fn(*args, **kwargs)
            started = time.perf_counter()
            try:
                result = fn(*args, **kwargs)
            except BaseException as exc:  # log the exception, then re-raise
                _emit(
                    {
                        "run_id": _run_id(),
                        "step_id": current_step_id(),
                        "layer": layer,
                        "primitive": _qualified_name(fn),
                        "args": _bind_args(fn, args, kwargs),
                        "result": None,
                        "exception": f"{type(exc).__name__}: {exc}",
                        "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                        "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    }
                )
                raise
            _emit(
                {
                    "run_id": _run_id(),
                    "step_id": current_step_id(),
                    "layer": layer,
                    "primitive": _qualified_name(fn),
                    "args": _bind_args(fn, args, kwargs),
                    "result": "<redacted>" if redact_result else _clip(result),
                    "exception": None,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                }
            )
            return result

        return wrapper

    return deco
