"""System adapter — system information via fastfetch or fallback."""

from __future__ import annotations

import subprocess
import platform
from typing import Any

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PrimitiveError


@contract(
    precondition="None.",
    postcondition="Returns CPU information.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if system info unavailable.",
    returns="dict: {model, cores, usage}.",
)
def cpu_info() -> dict[str, Any]:
    """Get CPU information."""
    try:
        import os
        model = platform.processor() or "Unknown"
        cores = os.cpu_count() or 0
        return {"model": model, "cores": cores}
    except Exception as exc:
        raise PrimitiveError(f"CPU info unavailable: {exc}") from exc


@contract(
    precondition="None.",
    postcondition="Returns memory information.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if memory info unavailable.",
    returns="dict: {total_gb, available_gb, used_percent}.",
)
def memory_info() -> dict[str, Any]:
    """Get memory information."""
    try:
        import os
        if hasattr(os, "sysconf"):
            total = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
            available = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_AVPHYS_PAGES")
            return {
                "total_gb": round(total / (1024**3), 1),
                "available_gb": round(available / (1024**3), 1),
                "used_percent": round((1 - available / total) * 100, 1),
            }
    except Exception:
        pass
    return {"total_gb": 0, "available_gb": 0, "used_percent": 0}


class SystemAdapter(Adapter):
    @property
    def name(self) -> str:
        return "system"

    @property
    def capabilities(self) -> list[str]:
        return ["cpu_info", "memory_info"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        if action == "cpu_info":
            return cpu_info(**kwargs)
        elif action == "memory_info":
            return memory_info(**kwargs)
        raise PrimitiveError(f"Unknown system action: {action}")

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return True


try:
    register_adapter(SystemAdapter())
except Exception:
    pass
