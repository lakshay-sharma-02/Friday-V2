"""Module registry and adapter management.

Auto-discovers L1 modules, manages adapter lifecycle, and provides
the capability catalog for the planner.
"""

from __future__ import annotations

import importlib
import inspect
import os
from pathlib import Path
from typing import Any

from friday_mcu.core.contracts import EXECUTOR_BLOCKED, REGISTRY, Contract


def discover_modules(base_dir: str | Path | None = None) -> list[str]:
    """Discover all L1 module names in the given directory.

    Falls back to the adapter directory if not specified.
    """
    if base_dir is None:
        base_dir = Path(__file__).resolve().parents[1] / "adapters"
    base = Path(base_dir)
    try:
        return sorted(p.stem for p in base.glob("*.py") if p.stem != "__init__")
    except OSError:
        return []


def ensure_registry(module_names: list[str] | None = None) -> None:
    """Import every L1 module so REGISTRY is complete.

    Also the one startup choke point every entry path already passes through:
    it loads the local credential file into env (so adapters and channels see
    TELEGRAM_BOT_TOKEN etc.) and registers messaging Channels for platforms
    whose credentials are present (so ProactiveEngine can actually send).
    """
    from friday_mcu.env import load_credentials
    load_credentials()

    if module_names is None:
        module_names = discover_modules()
    for name in module_names:
        try:
            importlib.import_module(f"friday_mcu.adapters.{name}")
        except ImportError:
            pass  # adapter not available — skip silently

    try:
        from friday_mcu.comms.builtin_channels import register_builtin_channels
        register_builtin_channels()
    except Exception:
        pass  # channel registration must never break the registry


def build_catalog(
    module_names: list[str] | None = None,
    include_blocked: bool = False,
) -> str:
    """Compact text catalog of every contract-registered primitive.

    Derived from the registry at call time so it can never drift from
    what the executor will actually resolve.
    """
    ensure_registry(module_names)
    lines: list[str] = ["PRIMITIVES:"]
    for qualified in sorted(REGISTRY):
        if not include_blocked and qualified in EXECUTOR_BLOCKED:
            continue
        c = REGISTRY[qualified]
        mod_name, _, fn_name = qualified.partition(".")
        try:
            mod = importlib.import_module(f"friday_mcu.adapters.{mod_name}")
            fn = getattr(mod, fn_name)
            sig = str(inspect.signature(fn))
        except (ImportError, AttributeError, TypeError):
            sig = "(...?)"
        doc = ""
        try:
            fn = getattr(importlib.import_module(f"friday_mcu.adapters.{mod_name}"), fn_name)
            doc = inspect.getdoc(fn) or ""
        except (ImportError, AttributeError):
            pass
        summary = doc.split(".")[0].strip() if doc else ""
        lines.append(f"- {qualified}{sig}  [idempotency={c.idempotency.value}]")
        if summary:
            lines.append(f"    {summary}.")
        if c.returns:
            lines.append(f"    returns: {c.returns}")
    return "\n".join(lines)


def build_checks_catalog() -> str:
    """Compact text catalog of every L2 verification check.

    These are side-effect-free read-only functions used in the 'verify'
    block of each plan step. They must be called as 'checks.<name>'.
    """
    import friday_mcu.brain.checks as checks_mod
    import types as _types
    lines: list[str] = ["CHECKS (use as 'checks.<name>' in verify blocks, NEVER as primitives):"]
    for name in sorted(dir(checks_mod)):
        if name.startswith("_"):
            continue
        fn = getattr(checks_mod, name)
        if not callable(fn):
            continue
        # Skip imported types (Any, Path, etc.) — only include functions
        if isinstance(fn, type) or isinstance(fn, _types.ModuleType):
            continue
        try:
            sig = str(inspect.signature(fn))
        except (TypeError, ValueError):
            sig = "(...?)"
        doc = (inspect.getdoc(fn) or "").split("\n")[0].strip()
        lines.append(f"- checks.{name}{sig}")
        if doc:
            lines.append(f"    {doc}")
    return "\n".join(lines)


def get_registry() -> dict[str, Contract]:
    """Get the current contract registry."""
    ensure_registry()
    return dict(REGISTRY)


def get_blocked() -> frozenset[str]:
    """Get the set of executor-blocked primitives."""
    return EXECUTOR_BLOCKED
