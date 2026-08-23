"""L1 primitive: system info (CPU, RAM, disk, battery, uptime).

Read-only system monitoring via fastfetch (JSON output). Each primitive
returns a structured dict with the relevant metrics.

Requires fastfetch to be installed (winget install Fastfetch-cli.Fastfetch).
"""

from __future__ import annotations

import json
import os
import subprocess
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError

FASTFETCH_TIMEOUT_S = 15


def _run_fastfetch(*structure: str) -> list[dict[str, Any]]:
    """Run fastfetch with JSON output and return parsed results."""
    cmd = ["fastfetch", "--format", "json"]
    if structure:
        cmd += ["--structure", ":".join(structure)]
    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=FASTFETCH_TIMEOUT_S,
        )
    except FileNotFoundError as exc:
        raise PrimitiveError(
            "fastfetch is not installed: winget install Fastfetch-cli.Fastfetch",
            state="fastfetch binary missing",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveError(
            f"fastfetch timed out after {FASTFETCH_TIMEOUT_S}s"
        ) from exc
    if proc.returncode != 0:
        raise PrimitiveError(
            f"fastfetch failed (rc={proc.returncode}): {proc.stderr.strip()[:200]}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise PrimitiveError(f"fastfetch returned invalid JSON: {exc}") from exc


def _find_section(data: list[dict], section_type: str) -> dict[str, Any]:
    """Find a section by type in fastfetch JSON output."""
    for item in data:
        if item.get("type") == section_type:
            return item.get("result", {})
    return {}


def _bytes_to_human(n: int) -> str:
    """Convert bytes to human-readable string."""
    if n < 1024:
        return f"{n} B"
    if n < 1024 * 1024:
        return f"{n / 1024:.1f} KB"
    if n < 1024 * 1024 * 1024:
        return f"{n / (1024 * 1024):.1f} MB"
    return f"{n / (1024 * 1024 * 1024):.1f} GB"


@contract(
    precondition="fastfetch is installed.",
    postcondition="Returns CPU info: model, cores, frequency. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if fastfetch is missing or fails.",
    returns="dict: {model, cores_physical, cores_logical, frequency_mhz, temperature}.",
)
def cpu_info() -> dict[str, Any]:
    """Get CPU information."""
    data = _run_fastfetch("CPU")
    cpu = _find_section(data, "CPU")
    cores = cpu.get("cores", {})
    freq = cpu.get("frequency", {})
    return {
        "model": cpu.get("cpu", "unknown"),
        "cores_physical": cores.get("physical", 0),
        "cores_logical": cores.get("logical", 0),
        "frequency_mhz": freq.get("base", 0),
        "temperature": cpu.get("temperature"),
    }


@contract(
    precondition="fastfetch is installed.",
    postcondition="Returns RAM info: total, used, available, usage_percent. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if fastfetch is missing or fails.",
    returns="dict: {total_bytes, used_bytes, available_bytes, usage_percent, total_human, used_human}.",
)
def memory_info() -> dict[str, Any]:
    """Get memory (RAM) information."""
    data = _run_fastfetch("Memory")
    mem = _find_section(data, "Memory")
    total = mem.get("total", 0)
    used = mem.get("used", 0)
    available = total - used
    pct = round((used / total) * 100, 1) if total > 0 else 0
    return {
        "total_bytes": total,
        "used_bytes": used,
        "available_bytes": available,
        "usage_percent": pct,
        "total_human": _bytes_to_human(total),
        "used_human": _bytes_to_human(used),
    }


@contract(
    precondition="fastfetch is installed.",
    postcondition="Returns disk info for all mounted volumes. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if fastfetch is missing or fails.",
    returns="list[dict]: [{mountpoint, filesystem, total_bytes, used_bytes, free_bytes, usage_percent, total_human}].",
)
def disk_info() -> list[dict[str, Any]]:
    """Get disk information for all mounted volumes."""
    data = _run_fastfetch("Disk")
    disks_raw = _find_section(data, "Disk")
    # fastfetch returns a list for Disk
    if isinstance(disks_raw, list):
        disks = disks_raw
    elif isinstance(disks_raw, dict):
        disks = [disks_raw]
    else:
        disks = []
    result = []
    for d in disks:
        bytes_info = d.get("bytes", {})
        total = bytes_info.get("total", 0)
        used = bytes_info.get("used", 0)
        free = bytes_info.get("free", 0)
        pct = round((used / total) * 100, 1) if total > 0 else 0
        result.append({
            "mountpoint": d.get("mountpoint", ""),
            "filesystem": d.get("filesystem", ""),
            "total_bytes": total,
            "used_bytes": used,
            "free_bytes": free,
            "usage_percent": pct,
            "total_human": _bytes_to_human(total),
        })
    return result


@contract(
    precondition="fastfetch is installed.",
    postcondition="Returns battery info if available. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if fastfetch is missing or fails.",
    returns="dict or None: {percent, charging, time_remaining_s} or None if no battery.",
)
def battery_info() -> dict[str, Any] | None:
    """Get battery information. Returns None if no battery is present."""
    data = _run_fastfetch("Battery")
    batt = _find_section(data, "Battery")
    if not batt or batt.get("status") == "No battery":
        return None
    return {
        "percent": batt.get("percentage", 0),
        "charging": batt.get("chargingStatus", "discharging") == "Charging",
        "time_remaining_s": batt.get("timeToFull"),
    }


@contract(
    precondition="fastfetch is installed.",
    postcondition="Returns system uptime. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if fastfetch is missing or fails.",
    returns="dict: {uptime_seconds, uptime_human, boot_time}.",
)
def uptime_info() -> dict[str, Any]:
    """Get system uptime."""
    data = _run_fastfetch("Uptime")
    ut = _find_section(data, "Uptime")
    secs = ut.get("uptime", 0)
    # Format human-readable uptime
    days = secs // 86400
    hours = (secs % 86400) // 3600
    mins = (secs % 3600) // 60
    parts = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    parts.append(f"{mins}m")
    return {
        "uptime_seconds": secs,
        "uptime_human": " ".join(parts),
        "boot_time": ut.get("bootTime", ""),
    }


@contract(
    precondition="fastfetch is installed.",
    postcondition="Returns a full system summary. Read-only.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if fastfetch is missing or fails.",
    returns="dict: {os, cpu, memory, disks, battery, uptime}.",
)
def system_summary() -> dict[str, Any]:
    """Get a complete system summary: OS, CPU, memory, disk, battery, uptime."""
    data = _run_fastfetch("OS", "CPU", "Memory", "Disk", "Battery", "Uptime")
    os_info = _find_section(data, "OS")
    cpu = cpu_info()
    mem = memory_info()
    disks = disk_info()
    batt = battery_info()
    up = uptime_info()
    return {
        "os": os_info.get("prettyName", "unknown"),
        "cpu": cpu,
        "memory": mem,
        "disks": disks,
        "battery": batt,
        "uptime": up,
    }
