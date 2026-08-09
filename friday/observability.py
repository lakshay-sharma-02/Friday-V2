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
  FRIDAY_LOG_MAX_BYTES     - rotate the log at this size (default: 10 MB)
  FRIDAY_LOG_BACKUPS       - rotated files kept (default: 3; 0 disables)
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

# Size-based rotation: when the active log passes FRIDAY_LOG_MAX_BYTES it is
# renamed to <log>.1 (older backups shift up, the oldest is dropped) and a
# fresh file starts. Bounds disk usage - a long-lived watch loop or a heavy
# verify poll must not grow the log without limit.
DEFAULT_LOG_MAX_BYTES = 10 * 1024 * 1024
DEFAULT_LOG_BACKUPS = 3

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


def _log_rotation_config() -> tuple[int, int]:
    """(max_bytes, backups) from env, falling back to the defaults on
    garbage values - a broken env var must never break logging."""
    try:
        max_bytes = int(os.environ.get("FRIDAY_LOG_MAX_BYTES", str(DEFAULT_LOG_MAX_BYTES)))
    except ValueError:
        max_bytes = DEFAULT_LOG_MAX_BYTES
    try:
        backups = int(os.environ.get("FRIDAY_LOG_BACKUPS", str(DEFAULT_LOG_BACKUPS)))
    except ValueError:
        backups = DEFAULT_LOG_BACKUPS
    # Clamp: max_bytes < 1 would rotate on every line and backups < 0 is
    # meaningless - a pathological env value must not turn rotation into a
    # data shredder.
    return max(max_bytes, 1), max(backups, 0)


def _rotate_if_needed(path: Path) -> None:
    """Size-based rotation, best-effort and never raising (observability
    must never break the primitive that triggered it). When the active log
    exceeds FRIDAY_LOG_MAX_BYTES it is renamed to <path>.1, older backups
    shift up, the oldest is dropped, and the next append starts a fresh
    file. Called from _emit under _log_lock, so rotation and append are
    one atomic writer."""
    try:
        max_bytes, backups = _log_rotation_config()
        if backups <= 0 or not path.exists():
            return
        if path.stat().st_size < max_bytes:
            return
        # Shift .N-1 -> .N, oldest first, so path.1 is always the most
        # recent backup and the top backup is overwritten/dropped. (The
        # outer except Exception below is the only guard needed - a shift
        # failure must not abort the whole rotation.)
        for i in range(backups - 1, 0, -1):
            src = Path(f"{path}.{i}")
            dst = Path(f"{path}.{i + 1}")
            if src.exists():
                src.replace(dst)
        path.replace(Path(f"{path}.1"))
    except Exception:
        pass  # rotation failure must not drop the triggering log line


def _log_value(result: Any, log_transform: Callable[[Any], Any] | None) -> Any:
    """The logged form of a successful result: apply log_transform first,
    then the standard clip. log_transform is deliberately NEVER allowed to
    raise - observability must not break the primitive it instruments, and
    a transform bug must not turn a successful call into a spurious
    failure (the primitive's real return value is returned regardless)."""
    try:
        return log_transform(result) if log_transform else result
    except Exception:
        return "<log_transform error>"


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
    back to stderr so a broken log is not silently invisible. Rotates the
    active file first when it has grown past the configured cap."""
    if os.environ.get("FRIDAY_OBSERVABILITY") == "0":
        return
    try:
        path = _log_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(record, default=str, ensure_ascii=False)
        with _log_lock:
            _rotate_if_needed(path)
            with open(path, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
    except Exception as exc:
        try:
            print(f"[friday-observability] log write failed ({exc}); dropping line", file=sys.stderr)
        except Exception:
            pass


def observe(
    layer: str = "L1",
    redact_result: bool = False,
    log_transform: Callable[[Any], Any] | None = None,
) -> Callable[[F], F]:
    """Decorator: emit one structured log line per call, result or
    exception. Preserves the wrapped function's metadata via wraps.

    redact_result=True: the returned value is written as "<redacted>"
    instead of the value itself. Use it for primitives whose RESULT is a
    secret (e.g. credentials() returns the credentials dict) - key-name
    redaction inside _clip is not enough when the whole result is secret.

    log_transform: optional callable applied to the returned value purely
    for the log line - the real return value is untouched. Use it to
    redact selected fields (e.g. gmail.list_unread's sender/subject) or
    project a large result to a compact shape (e.g. window.list_clients,
    whose raw hyprctl client dicts are the log's dominant payload).
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
                    "result": (
                        "<redacted>" if redact_result else _clip(_log_value(result, log_transform))
                    ),
                    "exception": None,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 3),
                    "timestamp": datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                }
            )
            return result

        return wrapper

    return deco
