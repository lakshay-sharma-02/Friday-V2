"""Observability layer — structured JSON logging.

One structured JSON line per call. Redaction, clip, per-primitive
log projection, and size-based rotation. Adapted from V8 with the
event bus integration added.
"""

from __future__ import annotations

import json
import os
import threading
import time
from contextvars import ContextVar
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

# Per-thread run_id and step_id for correlation
_run_id: ContextVar[str | None] = ContextVar("run_id", default=None)
_step_id: ContextVar[str | None] = ContextVar("step_id", default=None)

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LOG_FILE = PROJECT_ROOT / "var" / "logs" / "friday.jsonl"
DEFAULT_MAX_BYTES = 10 * 1024 * 1024  # 10 MB
DEFAULT_BACKUPS = 3

_rotation_lock = threading.Lock()


def set_run_id(run_id: str | None) -> None:
    """Set the current run ID for correlation."""
    _run_id.set(run_id)


def get_run_id() -> str | None:
    """Get the current run ID."""
    return _run_id.get()


def set_step_id(step_id: str | None) -> None:
    """Set the current step ID for correlation."""
    _step_id.set(step_id)


def reset_run_id() -> None:
    """Reset the run ID (e.g., after a trigger completes)."""
    _run_id.set(None)


def _log_file() -> Path:
    return Path(os.environ.get("FRIDAY_LOG_FILE", str(DEFAULT_LOG_FILE)))


def _max_bytes() -> int:
    try:
        return int(os.environ.get("FRIDAY_LOG_MAX_BYTES", str(DEFAULT_MAX_BYTES)))
    except ValueError:
        return DEFAULT_MAX_BYTES


def _max_backups() -> int:
    try:
        return int(os.environ.get("FRIDAY_LOG_BACKUPS", str(DEFAULT_BACKUPS)))
    except ValueError:
        return DEFAULT_BACKUPS


def _rotate_if_needed() -> None:
    """Rotate the log file if it exceeds the size limit."""
    path = _log_file()
    if not path.exists():
        return
    if path.stat().st_size < _max_bytes():
        return
    with _rotation_lock:
        # Double-check after acquiring the lock
        if path.stat().st_size < _max_bytes():
            return
        max_bk = _max_backups()
        # Shift existing backups
        for i in range(max_bk - 1, 0, -1):
            src = path.with_suffix(f".{i}")
            dst = path.with_suffix(f".{i + 1}")
            if src.exists():
                if dst.exists():
                    dst.unlink()
                src.rename(dst)
        # Rotate current
        bak = path.with_suffix(".1")
        if bak.exists():
            bak.unlink()
        path.rename(bak)


def _redact(value: Any) -> Any:
    """Redact sensitive values in log output."""
    if isinstance(value, dict):
        return {k: _redact(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_redact(v) for v in value]
    if isinstance(value, str) and len(value) > 200:
        return value[:200] + "...[clipped]"
    return value


def emit_log(
    *,
    layer: str,
    primitive: str,
    args: dict[str, Any] | None = None,
    result: Any = None,
    duration_ms: float = 0,
    exception: str | None = None,
    extra: dict[str, Any] | None = None,
) -> None:
    """Emit one structured JSON log line."""
    if os.environ.get("FRIDAY_OBSERVABILITY") == "0":
        return

    rec: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(timespec="microseconds"),
        "layer": layer,
        "primitive": primitive,
    }

    run_id = _run_id.get()
    if run_id:
        rec["run_id"] = run_id
    step_id = _step_id.get()
    if step_id:
        rec["step_id"] = step_id

    if args is not None:
        rec["args"] = _redact(args)
    if result is not None:
        rec["result"] = _redact(result)
    if duration_ms > 0:
        rec["duration_ms"] = round(duration_ms, 1)
    if exception:
        rec["exception"] = exception
    if extra:
        rec["extra"] = extra

    _rotate_if_needed()
    path = _log_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")
    except OSError:
        pass  # logging must never crash the caller


def observe(
    layer: str = "",
    redact_result: bool = False,
    log_transform: Callable[[Any], Any] | None = None,
) -> Callable:
    """Decorator that wraps a function with L0 observability.

    One structured JSON line per call — the choke point for all primitives.
    """

    def deco(fn: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            prim_layer = layer or fn.__module__.rsplit(".", 1)[-1]
            prim_name = fn.__name__
            t0 = time.monotonic()
            try:
                result = fn(*args, **kwargs)
                duration_ms = (time.monotonic() - t0) * 1000
                log_result = "<redacted>" if redact_result else result
                if log_transform:
                    try:
                        log_result = log_transform(result)
                    except Exception:
                        pass
                emit_log(
                    layer=prim_layer,
                    primitive=prim_name,
                    result=log_result,
                    duration_ms=duration_ms,
                )
                return result
            except Exception as exc:
                duration_ms = (time.monotonic() - t0) * 1000
                emit_log(
                    layer=prim_layer,
                    primitive=prim_name,
                    exception=f"{type(exc).__name__}: {exc}",
                    duration_ms=duration_ms,
                )
                raise

        wrapper.__name__ = fn.__name__
        wrapper.__doc__ = fn.__doc__
        wrapper.__module__ = fn.__module__
        return wrapper

    return deco
