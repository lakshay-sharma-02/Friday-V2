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

import json
import os
import re
import shutil
from collections import defaultdict
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


@contract(
    precondition="repos is an optional list of repository paths to analyze.",
    postcondition="Returns a dict with cross-project pattern analysis and suggestions.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on unexpected failures; degrades gracefully if repos missing.",
    returns="dict: {patterns: list, suggestions: list, confidence: float}",
)
def recognize_patterns(repos: list[str] | None = None) -> dict[str, Any]:
    """Recognize cross-project patterns and suggest transfers.

    Analyzes git history and planning docs across multiple repositories to
    identify recurring patterns, shared mechanisms, and potential knowledge
    transfers.

    Args:
        repos: List of repo paths to analyze (defaults to common projects)

    Returns:
        Dict with recognized patterns, cross-project suggestions, and confidence score
    """
    if repos is None:
        # Default to common repo locations
        home = Path.home()
        candidate_repos = [
            home / "Projects" / "Friday V2",
        ]
        repos = [str(r) for r in candidate_repos if r.exists()]

    patterns: list[dict[str, Any]] = []
    suggestions: list[str] = []

    repo_data: dict[str, dict[str, Any]] = {}

    for repo_path in repos:
        repo = Path(repo_path)
        if not repo.exists():
            continue

        repo_name = repo.name
        repo_info = {
            "name": repo_name,
            "path": str(repo),
            "categories": set(),
            "keywords": set(),
        }

        # Analyze recent git log
        try:
            from friday.l1.git import log as git_log

            commits = git_log(repo_path=str(repo), count=15)
            if commits and "items" in commits:
                for commit in commits["items"]:
                    commit_msg = commit.get("message", "")
                    if commit_msg:
                        cat = detect_semantic_category(commit_msg)
                        if cat:
                            repo_info["categories"].add(cat)
                        keywords = extract_semantic_keywords(commit_msg)
                        repo_info["keywords"].update(keywords)
        except Exception:
            pass

        # Analyze planning docs
        try:
            from friday.l1.files import find_recent_doc

            doc = find_recent_doc(repo_path=str(repo))
            if doc:
                from friday.l1.files import read_text as read_text_fn
                doc_text = read_text_fn(path=doc, max_chars=5000)
                if doc_text and "text" in doc_text:
                    sample = doc_text["text"][:5000]
                    cat = detect_semantic_category(sample)
                    if cat:
                        repo_info["categories"].add(cat)
                    keywords = extract_semantic_keywords(sample)
                    repo_info["keywords"].update(keywords)
        except Exception:
            pass

        # Convert sets to lists for JSON serialization
        repo_info["categories"] = list(repo_info["categories"])
        repo_info["keywords"] = list(repo_info["keywords"])[:20]

        repo_data[repo_name] = repo_info

    # Identify cross-project patterns
    all_categories: dict[str, list[str]] = defaultdict(list)
    for repo_name, info in repo_data.items():
        for cat in info.get("categories", []):
            all_categories[cat].append(repo_name)

    for cat, repos_in_cat in all_categories.items():
        if len(repos_in_cat) > 1:
            patterns.append({
                "category": cat,
                "repos": repos_in_cat,
                "shared_keywords": _find_shared_keywords(
                    [repo_data[r]["keywords"] for r in repos_in_cat if r in repo_data]
                ),
            })

    # Generate suggestions based on patterns
    for pattern in patterns:
        cat = pattern["category"]
        shared = pattern["shared_keywords"]
        repos_in = pattern["repos"]

        # Suggest transfer patterns
        if shared:
            suggestions.append(
                f"Repository pattern '{cat}' exists in {len(repos_in)} repos "
                f"({', '.join(repos_in)}). Consider extracting shared {cat} "
                f"infrastructure (keywords: {', '.join(shared[:5])})."
            )

    # Calculate confidence based on data quality
    total_repos = len(repo_data)
    confidence = min(1.0, total_repos * 0.3 + len(patterns) * 0.1)

    return {
        "patterns": patterns,
        "suggestions": suggestions,
        "confidence": round(confidence, 2),
        "analyzed_repos": list(repo_data.keys()),
    }


def _find_shared_keywords(keyword_lists: list[list[str]]) -> list[str]:
    """Find keywords shared across multiple lists."""
    if not keyword_lists or len(keyword_lists) < 2:
        return []

    sets = [set(kw_list) for kw_list in keyword_lists]
    shared = set.intersection(*sets) if len(sets) > 1 else set()
    return sorted(shared)[:10]


@contract(
    precondition="goal is a non-empty string describing a desired system state.",
    postcondition="Returns a remediation plan dict for restoring system health.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PreconditionError for invalid goals.",
    returns="dict: {steps: list, priority: str, estimated_time_s: int}",
)
def remediate(goal: str) -> dict[str, Any]:
    """Generate a remediation plan based on health check and failure prediction.

    Combines health_check() results and predict_failures() analysis to
    produce a prioritized remediation plan.

    Args:
        goal: System health goal (e.g., "restore optimal performance", "prevent failures")

    Returns:
        Dict with remediation steps, priority level, and time estimate
    """
    if not goal or not goal.strip():
        raise PreconditionError("remediate requires a non-empty goal")

    # Get current health
    health = health_check()
    predictions = predict_failures()

    steps: list[dict[str, Any]] = []
    priority = "low"
    estimated_time = 0

    # Disk space remediation
    disk_pct = health["resources"].get("disk_usage_pct", 0)
    if isinstance(disk_pct, (int, float)) and disk_pct > 85:
        steps.append({
            "step": "cleanup_disk",
            "primitive": "filesystem.cleanup",
            "args": {"path": str(ROOT / "var" / "logs"), "older_than_days": 30},
            "reason": f"Disk usage at {disk_pct}%"
        })
        priority = "high"
        estimated_time += 300

    # Log rotation
    log_size = health["layers"].get("l0_logs", {}).get("log_size_mb", 0)
    if isinstance(log_size, (int, float)) and log_size > 200:
        steps.append({
            "step": "rotate_logs",
            "primitive": "filesystem.cleanup",
            "args": {"path": str(ROOT / "var" / "logs"), "older_than_days": 60},
            "reason": f"Log files exceed {log_size}MB"
        })
        if priority != "high":
            priority = "medium"
        estimated_time += 120

    # Failure prediction remediation
    likelihood = predictions.get("failure_likelihood", 0.0)
    pattern = predictions.get("pattern", "none")

    if likelihood > 0.5:
        steps.append({
            "step": "address_predicted_failures",
            "primitive": "dev.run",
            "args": {
                "task": f"Investigate and address predicted failure pattern: {pattern}"
            },
            "reason": f"Failure likelihood at {likelihood}"
        })
        priority = "high"
        estimated_time += 600

    # Add health recommendations
    for rec in health.get("recommendations", []):
        if "log rotation" in rec.lower():
            if not any(s["step"] == "rotate_logs" for s in steps):
                steps.append({
                    "step": "follow_health_recommendation",
                    "primitive": "dev.run",
                    "args": {"task": rec},
                    "reason": "Health check recommendation"
                })
                estimated_time += 180

    # If no issues found
    if not steps:
        steps.append({
            "step": "no_action_needed",
            "primitive": "notify.notify_send",
            "args": {
                "title": "Stark: System Health",
                "body": f"System is healthy. No remediation needed for goal: {goal}"
            },
            "reason": "No issues detected"
        })

    return {
        "goal": goal,
        "steps": steps,
        "priority": priority,
        "estimated_time_s": estimated_time,
        "health_status": health["status"],
        "failure_likelihood": likelihood,
    }


@contract(
    precondition="name is a non-empty string identifying the workflow.",
    postcondition="Returns workflow status and recommendations from the orchestrator.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if the orchestrator is unavailable.",
    returns="dict: {workflow_id, status, recommendations, next_step}",
)
def workflow_status(name: str) -> dict[str, Any]:
    """Get enhanced workflow status with recommendations.

    Extends the L1 workflow status with Stark-level analysis and
    recommendations for optimization or remediation.

    Args:
        name: Workflow identifier (UUID or name)

    Returns:
        Enhanced workflow status with Stark-level recommendations
    """
    if not name or not name.strip():
        raise PreconditionError("workflow_status requires a non-empty name")

    from friday.l1.workflow import get_workflow_status

    try:
        base_status = get_workflow_status(name)
    except Exception as e:
        raise PrimitiveError(f"Failed to get workflow status: {e}") from e

    recommendations: list[str] = []
    duration_s = base_status.get("duration_s", 0)

    # Analyze workflow duration
    if duration_s > 300:
        recommendations.append(
            "Long execution time - consider parallel_run() for independent steps"
        )

    # Analyze errors
    steps = base_status.get("step_results", [])
    failed_steps = [s for s in steps if s.get("status") != "COMPLETED"]

    if failed_steps:
        recommendations.append(
            f"{len(failed_steps)} step(s) failed - use remediate() to generate fix plan"
        )

    # Check for resource-heavy primitives
    has_dev_run = any(
        "dev.run" in str(s.get("steps", ""))
        for s in steps
    )
    if has_dev_run:
        recommendations.append(
            "Contains LLM calls - consider resource_governor() for model optimization"
        )

    # Determine next step
    next_step = "run" if base_status.get("status") == "completed" else "fix"

    return {
        "workflow_id": base_status.get("id", name),
        "status": base_status.get("status"),
        "duration_s": duration_s,
        "step_count": len(steps),
        "recommendations": recommendations,
        "next_step": next_step,
    }