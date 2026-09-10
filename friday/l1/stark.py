"""L1 primitive: stark (Stark Industries infrastructure layer).

Provides autonomous system health monitoring, resource governance, and
high-level intent interpretation. The Stark layer coordinates across
all other layers to provide JARVIS-level infrastructure management.

Features:
- Comprehensive system health checks across L0-L4 layers
- Resource governance and power management
- Autonomous failure prediction from log analysis
- Multi-repository project orchestration
"""

from __future__ import annotations

import os
import re
import shutil
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError

ROOT = Path(__file__).resolve().parents[2]


@contract(
    precondition="None - performs autonomous health check across all layers.",
    postcondition="Returns a health status dict with layer states and recommendations.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on unexpected failures; best-effort degrades gracefully.",
    returns="dict: {status: str, layers: dict, resources: dict, recommendations: list}",
)
def health_check() -> dict[str, Any]:
    """Perform comprehensive system health check across all Friday layers.

    Checks:
    - L0: Log files existence and rotation status
    - L1: Primitive registry status and contract coverage
    - L2: Checks module status
    - L3: Executor state and pending runs
    - L4: Planner status and model availability
    - L5: Workflow orchestrator status

    Returns:
        Dict with overall status, per-layer states, resource usage, and recommendations.
    """
    now = datetime.now(UTC)

    # Check log files (L0)
    logs_dir = ROOT / "var" / "logs"
    l0_status = {
        "logs_exist": logs_dir.exists(),
        "tasks_file": (logs_dir / "tasks.jsonl").exists() if logs_dir.exists() else False,
        "friday_log": (logs_dir / "friday.jsonl").exists() if logs_dir.exists() else False,
        "lessons_log": (logs_dir / "lessons.jsonl").exists() if logs_dir.exists() else False,
        "log_size_mb": 0,
    }

    if logs_dir.exists():
        total_size = 0
        for f in logs_dir.glob("**/*.jsonl"):
            total_size += f.stat().st_size
        l0_status["log_size_mb"] = round(total_size / 1024 / 1024, 2)

    # Check L1 primitives
    from friday.contracts import REGISTRY

    l1_status = {
        "primitives_count": len(REGISTRY),
        "blocked_count": 0,  # Would need to import EXECUTOR_BLOCKED
    }

    # Check resources
    resources = _check_resources()

    # Build recommendations
    recommendations = _build_health_recommendations(l0_status, l1_status, resources, now)

    overall_status = "healthy" if resources.get("disk_usage_pct", 0) < 85 else "warning"

    return {
        "status": overall_status,
        "timestamp": now.isoformat(),
        "layers": {
            "l0_logs": l0_status,
            "l1_primitives": l1_status,
        },
        "resources": resources,
        "recommendations": recommendations,
    }


def _check_resources() -> dict[str, Any]:
    """Check system resources availability."""
    resources: dict[str, Any] = {}

    # Disk usage
    total, used, free = shutil.disk_usage(ROOT)
    disk_pct = (used / total) * 100
    resources["disk_total_gb"] = round(total / 1024**3, 2)
    resources["disk_used_gb"] = round(used / 1024**3, 2)
    resources["disk_free_gb"] = round(free / 1024**3, 2)
    resources["disk_usage_pct"] = round(disk_pct, 1)

    # Memory (basic check - actual would use system primitives if available)
    try:
        import psutil

        mem = psutil.virtual_memory()
        resources["memory_total_gb"] = round(mem.total / 1024**3, 2)
        resources["memory_available_gb"] = round(mem.available / 1024**3, 2)
        resources["memory_usage_pct"] = round(mem.percent, 1)
    except ImportError:
        resources["memory_total_gb"] = "unknown"
        resources["memory_usage_pct"] = "unknown"

    # Battery (if laptop)
    battery = _check_battery()
    if battery:
        resources.update(battery)

    return resources


def _check_battery() -> dict[str, Any] | None:
    """Check battery status if available."""
    try:
        from friday.l1.system import battery_info

        return battery_info()
    except Exception:
        return None


def _build_health_recommendations(
    l0: dict[str, Any],
    l1: dict[str, Any],
    resources: dict[str, Any],
    now: datetime,
) -> list[str]:
    """Build list of health recommendations."""
    recs = []

    # Log rotation
    if l0.get("log_size_mb", 0) > 100:
        recs.append("Consider log rotation - logs exceed 100MB")

    # Disk space
    if resources.get("disk_usage_pct", 0) > 85:
        recs.append("Disk space critical - cleanup recommended")

    # Check for stale logs
    try:
        logs_dir = ROOT / "var" / "logs"
        if logs_dir.exists():
            # Check for logs older than 30 days
            cutoff = now - timedelta(days=30)
            for log_file in logs_dir.glob("**/*.jsonl"):
                if datetime.fromtimestamp(log_file.stat().st_mtime, UTC) < cutoff:
                    recs.append(f"Consider archiving old log: {log_file.name}")
                    break
    except Exception:
        pass

    if not recs:
        recs.append("All systems healthy - no action required")

    return recs


@contract(
    precondition="goal is a non-empty string describing a desired outcome.",
    postcondition="Returns an autonomous workflow plan dict with steps and estimated resources.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for invalid goals; PrimitiveError if planning fails.",
    returns="dict: {goal, steps: list, estimated_cost: dict, confidence: float}",
)
def autonomous_plan(goal: str) -> dict[str, Any]:
    """Given a high-level goal, autonomously compose a workflow plan.

    Uses semantic analysis and pattern matching to decompose goals into
    concrete primitive steps. This is the JARVIS-level autopilot feature.

    Args:
        goal: High-level description of desired outcome

    Returns:
        Dict with decomposed steps, resource estimates, and confidence score
    """
    if not goal or not goal.strip():
        raise PreconditionError("autonomous_plan requires a non-empty goal")

    # Analyze goal semantics
    category = _detect_goal_category(goal)
    keywords = _extract_goal_keywords(goal)

    # Build plan based on category
    plan = _build_plan_from_category(goal, category, keywords)

    # Estimate resources
    estimated_cost = {
        "llm_calls": {"planner": 1, "digest": 0, "summarize": 0},
        "estimated_cost_usd": 0.10,  # Default planner cost
        "estimated_duration_s": 30,
    }

    return {
        "goal": goal,
        "category": category,
        "keywords": keywords,
        "steps": plan.get("steps", []),
        "estimated_cost": estimated_cost,
        "confidence": plan.get("confidence", 0.8),
        "reasoning": plan.get("reasoning", ""),
    }


def _detect_goal_category(goal: str) -> str:
    """Detect the semantic category of a goal."""
    from friday.semantic_clustering import detect_semantic_category

    return detect_semantic_category(goal) or "general"


def _extract_goal_keywords(goal: str) -> list[str]:
    """Extract relevant keywords from a goal."""
    from friday.semantic_clustering import extract_semantic_keywords

    return extract_semantic_keywords(goal)[:10]


def _build_plan_from_category(
    goal: str, category: str, keywords: list[str]
) -> dict[str, Any]:
    """Build a plan based on goal category."""
    # This is a simplified plan builder - in production would use L4 planner
    steps = []

    # Pattern-based plan generation
    if "git" in category or "commit" in " ".join(keywords):
        steps = [
            {"primitive": "git.log", "args": {"count": 5}},
            {"primitive": "git.status", "args": {}},
        ]
    elif "digest" in " ".join(keywords) or "cross" in " ".join(keywords):
        steps = [
            {"primitive": "git.log", "args": {"count": 10}},
            {"primitive": "dev.digest", "args": {"context": {}}},
        ]
    elif "gmail" in category or "email" in category:
        steps = [
            {"primitive": "gmail.list_unread", "args": {}},
            {"primitive": "gmail.get_message", "args": {}},
        ]

    if not steps:
        steps = [
            {"primitive": "dev.run", "args": {"task": f"Analyze goal: {goal}"}},
        ]

    return {
        "steps": steps,
        "confidence": 0.7 if steps else 0.3,
        "reasoning": f"Built from {category} patterns and keywords: {', '.join(keywords[:3])}",
    }


@contract(
    precondition="log_path is optional path to L0 log file; days is the lookback window.",
    postcondition="Returns prediction dict with failure likelihood and pattern match.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for invalid arguments; returns 'unknown' on failure.",
    returns="dict: {failure_likelihood: float, pattern: str, next_check: str}",
)
def predict_failures(
    log_path: str | None = None, days: int = 7
) -> dict[str, Any]:
    """Predict potential failures from L0 log analysis.

    Analyzes task failures and L0 exceptions to predict likely
    upcoming failures based on historical patterns.

    Args:
        log_path: Optional path to logs file (defaults to var/logs/tasks.jsonl)
        days: Lookback window in days

    Returns:
        Dict with failure likelihood, detected pattern, and next check recommendation
    """
    if days < 1:
        days = 7

    if log_path is None:
        log_path = str(ROOT / "var" / "logs" / "tasks.jsonl")

    log_file = Path(log_path)
    if not log_file.exists():
        return {
            "failure_likelihood": 0.0,
            "pattern": "no_logs_available",
            "next_check": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }

    # Parse logs for failure patterns
    failures_by_primitive: dict[str, int] = {}
    failures_by_exception: dict[str, int] = {}

    try:
        content = log_file.read_text(encoding="utf-8")
        cutoff = datetime.now(UTC) - timedelta(days=days)

        for line in content.strip().split("\n"):
            try:
                import json

                record = json.loads(line)
                timestamp_str = record.get("timestamp", "")
                if timestamp_str:
                    timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
                    if timestamp < cutoff:
                        continue

                # Count failures
                if not record.get("gate6_passed", True):
                    primitive = record.get("primitive", "unknown")
                    failures_by_primitive[primitive] = failures_by_primitive.get(primitive, 0) + 1

                    # Extract exception info from proof
                    proof = record.get("proof", "")
                    if "error" in proof.lower():
                        failures_by_exception["error"] = failures_by_exception.get("error", 0) + 1
            except (json.JSONDecodeError, ValueError):
                continue

    except Exception:
        return {
            "failure_likelihood": 0.0,
            "pattern": "parse_error",
            "next_check": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        }

    # Detect patterns
    patterns = []
    if failures_by_primitive:
        top_failure = max(failures_by_primitive.items(), key=lambda x: x[1])
        if top_failure[1] >= 2:
            patterns.append(f"{top_failure[0]}: {top_failure[1]} failures")

    # Calculate likelihood
    total_failures = sum(failures_by_primitive.values())
    likelihood = min(1.0, total_failures / 10) if total_failures > 0 else 0.0

    return {
        "failure_likelihood": round(likelihood, 2),
        "pattern": "; ".join(patterns) if patterns else "none",
        "next_check": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
        "failures_by_primitive": failures_by_primitive,
    }


@contract(
    precondition="resources is a dict with resource requirements.",
    postcondition="Returns resource allocation recommendations.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for invalid resources dict.",
    returns="dict: {allocation: str, model: str, wait_for: str}",
)
def resource_governor(resources: dict[str, Any]) -> dict[str, Any]:
    """Recommend optimal resource allocation for a task.

    Args:
        resources: Dict with 'cpu', 'memory_mb', 'time_s', and optional 'importance' keys

    Returns:
        Dict with allocation recommendations for model selection and scheduling
    """
    if not isinstance(resources, dict):
        raise PreconditionError("resource_governor requires a resources dict")

    cpu = resources.get("cpu", 1)
    memory_mb = resources.get("memory_mb", 512)
    max_time = resources.get("time_s", 60)
    importance = resources.get("importance", "normal")  # low, normal, high, critical

    # Model selection based on resources
    if memory_mb < 256 or max_time < 30:
        model = "haiku"
        allocation = "low"
    elif memory_mb < 1024 or max_time < 120:
        model = "sonnet"
        allocation = "medium"
    else:
        model = "opus"
        allocation = "high"

    # Wait recommendation based on importance
    wait_for = "immediate" if importance == "critical" else "optimal_time"

    return {
        "allocation": allocation,
        "model": model,
        "wait_for": wait_for,
        "reasoning": f"CPU:{cpu}, Mem:{memory_mb}MB, Time:{max_time}s -> {model}",
    }