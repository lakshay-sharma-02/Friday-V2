"""LLM Planner — goal string in, plan JSON out.

Adapted from V8 L4 with:
- Context-aware planning (uses memory + observer data)
- Confidence scoring
- Deduplicated template system
- Headless-first (no compositor dependency)
- Plan caching (skip LLM on repeat goals)
- Template matching (skip LLM for common goals)
- Haiku model (2-3s vs 12s for planning)
"""

from __future__ import annotations

import copy
import hashlib
import importlib
import inspect
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from friday_mcu.core.contracts import EXECUTOR_BLOCKED, REGISTRY
from friday_mcu.core.errors import FridayError, PlanError
from friday_mcu.core.events import EventType, emit
from friday_mcu.core.registry import build_catalog, build_checks_catalog, ensure_registry

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ATTEMPTS = 3
DEFAULT_TIMEOUT_S = 300

# Planning model — Haiku for speed (2-3s vs 12s for Sonnet/Opus)
PLANNING_MODEL = os.environ.get("FRIDAY_PLANNING_MODEL", "haiku")

# ── Plan Cache
# Hash(goal) → {plan, timestamp, hits}
_PLAN_CACHE: dict[str, dict[str, Any]] = {}
CACHE_MAX_ENTRIES = 256
CACHE_TTL_S = 3600 * 24  # 24 hours

# $steps.N.result reference pattern
_REF = re.compile(r"^\$steps\.(\d+)\.result(.*)$")


@dataclass
class Plan:
    """A validated plan ready for execution."""

    goal: str
    steps: list[dict[str, Any]]
    confidence: float = 0.0
    context_used: list[str] = field(default_factory=list)
    source: str = "llm"  # "llm" | "template" | "procedural"


@dataclass
class PlanResult:
    """Result of the planning process."""

    plan: Plan | None
    error: str | None = None
    attempts: int = 0
    validation_errors: list[str] = field(default_factory=list)


# -------------------------------------------------------------- validation


def _check_step_args(qualified: str, args: dict[str, Any], step_no: int) -> list[str]:
    """Validate step arg names against the primitive's real signature.

    Catches template/LLM typos (git.log(max_count=...) instead of count=...)
    at plan time rather than as a TypeError mid-execution.
    """
    module_name, _, fn_name = qualified.partition(".")
    try:
        mod = importlib.import_module(f"friday_mcu.adapters.{module_name}")
        fn = getattr(mod, fn_name)
        sig = inspect.signature(fn)
    except (ImportError, AttributeError, TypeError, ValueError):
        return []  # cannot inspect — skip
    params = sig.parameters
    allowed = {
        p.name
        for p in params.values()
        if p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    }
    var_kw = any(p.kind == p.VAR_KEYWORD for p in params.values())
    errors: list[str] = []
    if not var_kw:
        for key in sorted(args):
            if key not in allowed:
                errors.append(f"step {step_no}: unknown arg {key!r} for {qualified}")
    required = {
        p.name
        for p in params.values()
        if p.default is p.empty and p.kind in (p.POSITIONAL_OR_KEYWORD, p.KEYWORD_ONLY)
    }
    for name in sorted(required):
        if name not in args:
            errors.append(f"step {step_no}: missing required arg {name!r} for {qualified}")
    return errors


def validate_plan(plan: dict[str, Any]) -> tuple[bool, list[str]]:
    """Check the plan against the schema the executor accepts.

    Returns (ok, error_messages). Catches malformed plans BEFORE
    the executor ever sees them.
    """
    ensure_registry()
    errors: list[str] = []

    if not isinstance(plan, dict):
        return False, ["plan is not a JSON object"]

    goal = plan.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        errors.append("missing non-empty 'goal' string")

    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        errors.append("missing non-empty 'steps' list")
        return False, errors

    for i, raw in enumerate(steps, start=1):
        if not isinstance(raw, dict):
            errors.append(f"step {i}: not an object")
            continue

        primitive = raw.get("primitive")
        if not isinstance(primitive, str) or primitive not in REGISTRY:
            errors.append(f"step {i}: unknown or unregistered primitive {primitive!r}")
            continue

        if primitive in EXECUTOR_BLOCKED:
            errors.append(f"step {i}: primitive {primitive!r} is blocked")
            continue

        args = raw.get("args")
        if args is not None and not isinstance(args, dict):
            errors.append(f"step {i}: 'args' must be an object")
        elif isinstance(args, dict):
            errors.extend(_check_step_args(primitive, args, i))

        v = raw.get("verify")
        if not isinstance(v, dict):
            errors.append(f"step {i}: missing 'verify' object")
            continue

        check = v.get("check")
        if not isinstance(check, str):
            errors.append(f"step {i}: verify needs a 'check' string")
        elif not check.startswith("checks.") and "checks." in check:
            errors.append(f"step {i}: check must start with 'checks.'")

        if "expect" not in v:
            errors.append(f"step {i}: verify needs an 'expect' value")

    return len(errors) == 0, errors


# --------------------------------------------------------------- prompt


def _build_observer_context(goal: str) -> str:
    """Build observer context from user model, predictions, and anomalies."""
    sections: list[str] = []

    try:
        from friday_mcu.observer.user_model import UserModel
        model = UserModel()
        user_ctx = model.build_context()
        if user_ctx:
            sections.append(f"USER MODEL:\n{user_ctx}")
    except Exception:
        pass

    try:
        from friday_mcu.observer.predictions import PredictionEngine
        engine = PredictionEngine()
        # We need tasks for predictions — get from memory
        from friday_mcu.memory.store import MemoryManager
        mgr = MemoryManager()
        recent = mgr.episodic.recent(50)
        tasks = [
            {
                "goal": m.content.split("->")[0].replace("Goal:", "").strip(),
                "gate6_passed": "success" in m.content.lower() or "completed" in m.content.lower(),
                "timestamp": m.created_at,
            }
            for m in recent
        ]
        if tasks:
            predictions = engine.generate_predictions(tasks)
            high_conf = [p for p in predictions if p.confidence >= 0.5]
            if high_conf:
                pred_lines = [f"  - {p.description} (confidence={p.confidence:.0%})" for p in high_conf[:3]]
                sections.append("PREDICTIONS:\n" + "\n".join(pred_lines))
    except Exception:
        pass

    try:
        from friday_mcu.observer.anomalies import AnomalyDetector
        detector = AnomalyDetector()
        from friday_mcu.memory.store import MemoryManager
        mgr = MemoryManager()
        recent = mgr.episodic.recent(50)
        tasks = [
            {
                "goal": m.content.split("->")[0].replace("Goal:", "").strip(),
                "gate6_passed": "success" in m.content.lower() or "completed" in m.content.lower(),
                "timestamp": m.created_at,
            }
            for m in recent
        ]
        if tasks:
            anomalies = detector.detect(tasks)
            if anomalies:
                anom_lines = [f"  - [{a.severity}] {a.description}" for a in anomalies[:3]]
                sections.append("ANOMALIES:\n" + "\n".join(anom_lines))
    except Exception:
        pass

    return "\n\n".join(sections)


def build_prompt(
    goal: str,
    catalog: str,
    context: str = "",
    last_error: str | None = None,
    memory_context: str = "",
) -> str:
    """Assemble the full planning prompt."""
    retry_note = (
        f"\nYOUR PREVIOUS PLAN WAS REJECTED:\n    {last_error}\n"
        "Fix the plan so it passes the schema.\n"
        if last_error
        else ""
    )

    context_block = f"\nCONTEXT:\n{context}\n" if context else ""
    memory_block = f"\nMEMORY:\n{memory_context}\n" if memory_context else ""
    observer_block = _build_observer_context(goal)
    observer_text = f"\nOBSERVER INSIGHTS:\n{observer_block}\n" if observer_block else ""
    # Learning context from past outcomes
    learning_block = ""
    try:
        from friday_mcu.memory.learning import MemoryLearner
        learner = MemoryLearner()
        learning_ctx = learner.build_learning_context(goal)
        if learning_ctx:
            learning_block = f"\nLEARNING:\n{learning_ctx}\n"
    except Exception:
        pass
    checks_catalog = build_checks_catalog()

    return f"""You are the planning layer of 'Friday', an intelligent desktop
automation agent. Convert the GOAL into a machine-readable plan.

CRITICAL DISTINCTION:
- PRIMITIVES are ACTIONS (side effects: send messages, read emails, etc.)
- CHECKS are VERIFICATIONS (read-only: did the action succeed?)
- You use primitives in 'primitive' fields, checks in 'verify.check' fields.
- NEVER use a primitive as a check. NEVER use a check as a primitive.

SCHEMA - the output must match EXACTLY:
{{
  "goal": "<the goal string, copied verbatim>",
  "confidence": <0.0 to 1.0>,
  "steps": [
    {{
      "primitive": "module.function",
      "args": {{ ... }},
      "verify": {{
        "check": "checks.name",
        "args": {{ ... }},
        "expect": <exact JSON value>
      }}
    }}
  ]
}}

EXAMPLES of correct verify blocks:
- After sending a message: {{"check": "checks.message_sent", "args": {{"platform": "telegram", "message_id": "$steps.1.result.message_id"}}, "expect": true}}
- After listing emails (check goal — empty is OK): {{"check": "checks.call_succeeded", "args": {{"value": "$steps.1.result"}}, "expect": true}}
- After listing emails (must have results): {{"check": "checks.list_nonempty", "args": {{"value": "$steps.1.result"}}, "expect": true}}
- After fetching a message: {{"check": "checks.text_nonempty", "args": {{"value": "$steps.1.result.body"}}, "expect": true}}
- After checking file existence: {{"check": "checks.file_exists", "args": {{"path": "/some/path"}}, "expect": true}}

IMPORTANT: For read-only "check" goals (check emails, list files, get status),
use checks.call_succeeded — empty results are valid. Only use checks.list_nonempty
when the goal IMPLIES results must exist ("find emails from X", "get my messages").

RULES:
1. Use ONLY the primitives listed below. Never invent names.
2. Use ONLY the checks listed below for verification. Never invent check names.
3. EVERY step MUST carry a "verify" that reads real state.
4. Primitives marked [at-most-once] have side effects — call each at most once.
5. "expect" must be the exact JSON type the check returns.
6. A step may reference earlier step results via "$steps.N.result.key" where N is 1-BASED (first step is $steps.1, second is $steps.2, etc.).
7. Keep the plan minimal — do not invent unnecessary steps.
8. Output ONLY the JSON plan object. No markdown, no commentary.
9. Set "confidence" to your honest assessment of plan success probability.
{context_block}{memory_block}{observer_text}{learning_block}
{checks_catalog}
{catalog}
{retry_note}
GOAL: {goal}
Output the plan JSON now."""


# -------------------------------------------------------------- parsing


def _extract_json(text: str) -> dict[str, Any] | None:
    """Parse the model's output as a single JSON object.

    Tolerates stray markdown fences.
    """
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            value = json.loads(text[start : end + 1])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None
    return None


# ---------------------------------------------------------- cache + match


def _cache_key(goal: str) -> str:
    """Deterministic hash of a normalized goal string."""
    normalized = goal.lower().strip()
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def _get_cached_plan(goal: str) -> Plan | None:
    """Look up a cached plan for this goal. Returns None on miss."""
    key = _cache_key(goal)
    entry = _PLAN_CACHE.get(key)
    if entry is None:
        return None
    # Check TTL
    if time.time() - entry["timestamp"] > CACHE_TTL_S:
        del _PLAN_CACHE[key]
        return None
    entry["hits"] += 1
    # Deep-copy on read: the cached plan is shared state and callers must
    # never be able to mutate it (goal updates, executor arg rewriting...).
    plan_data = copy.deepcopy(entry["plan"])
    plan_data["goal"] = goal  # update to actual goal
    return Plan(
        goal=goal,
        steps=plan_data["steps"],
        confidence=plan_data.get("confidence", 0.9),
        source="cache",
    )


def _store_cached_plan(goal: str, plan_dict: dict[str, Any]) -> None:
    """Store a plan in the cache."""
    key = _cache_key(goal)
    # Evict oldest if full
    if len(_PLAN_CACHE) >= CACHE_MAX_ENTRIES:
        oldest_key = min(_PLAN_CACHE, key=lambda k: _PLAN_CACHE[k]["timestamp"])
        del _PLAN_CACHE[oldest_key]
    _PLAN_CACHE[key] = {
        "plan": plan_dict,
        "timestamp": time.time(),
        "hits": 0,
    }


def _get_template_plan(goal: str) -> Plan | None:
    """Try to match a goal against known templates."""
    from friday_mcu.brain.templates import match_template
    plan_dict = match_template(goal)
    if plan_dict is None:
        return None
    # Validate the template plan
    ok, errors = validate_plan(plan_dict)
    if not ok:
        return None  # template broken, fall through to LLM
    return Plan(
        goal=plan_dict.get("goal", goal),
        steps=plan_dict.get("steps", []),
        confidence=plan_dict.get("confidence", 0.95),
        source="template",
    )


# ------------------------------------------------------------- planning


def plan(
    goal: str,
    *,
    run_id: str | None = None,
    attempts: int = DEFAULT_ATTEMPTS,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    context: str = "",
    memory_context: str = "",
) -> Plan:
    """Goal string in, validated Plan out.

    Fast path: template match (0s) → cache hit (0s) → LLM (2-3s with Haiku).
    Bounded retries on unparseable/invalid output.
    """
    if not goal or not goal.strip():
        raise FridayError("plan() requires a non-empty goal")
    if attempts < 1:
        raise FridayError("plan() requires attempts >= 1")

    ensure_registry()

    emit(
        EventType.GOAL_PLANNED,
        source="planner",
        data={"goal": goal, "attempts": attempts},
        correlation_id=run_id,
    )

    # ── Fast path 1: Template match (0ms)
    t0 = time.monotonic()
    template_plan = _get_template_plan(goal)
    if template_plan is not None:
        elapsed = time.monotonic() - t0
        emit(
            EventType.GOAL_PLANNED,
            source="planner",
            data={"goal": goal, "source": "template", "elapsed_s": round(elapsed, 2)},
            correlation_id=run_id,
        )
        return template_plan

    # ── Fast path 2: Cache hit (0ms)
    cached = _get_cached_plan(goal)
    if cached is not None:
        elapsed = time.monotonic() - t0
        emit(
            EventType.GOAL_PLANNED,
            source="planner",
            data={"goal": goal, "source": "cache", "elapsed_s": round(elapsed, 2)},
            correlation_id=run_id,
        )
        return cached

    # ── Slow path: LLM planning
    catalog = build_catalog() + "\n\n" + build_checks_catalog()
    last_error: str | None = None
    validation_errors: list[str] = []

    for i in range(1, attempts + 1):
        try:
            prompt = build_prompt(
                goal,
                catalog,
                context=context,
                last_error=last_error,
                memory_context=memory_context,
            )
            from friday_mcu.adapters.dev import run as dev_run
            response = dev_run(
                prompt,
                cwd=str(PROJECT_ROOT),
                timeout_s=timeout_s,
                model=PLANNING_MODEL,
            )
            if response.get("is_error"):
                last_error = f"LLM error: {response['result'][:200]}"
                continue

            # Parse the response
            raw_result = response.get("result", "")
            if isinstance(raw_result, dict):
                plan_dict = raw_result
            elif isinstance(raw_result, str):
                plan_dict = _extract_json(raw_result)
            else:
                last_error = f"Unexpected LLM response type: {type(raw_result)}"
                continue

            if plan_dict is None:
                last_error = "LLM output is not valid JSON"
                continue

            # Validate
            ok, errors = validate_plan(plan_dict)
            if not ok:
                last_error = "; ".join(errors)
                validation_errors = errors
                continue

            # Build Plan object
            p = Plan(
                goal=plan_dict.get("goal", goal),
                steps=plan_dict.get("steps", []),
                confidence=plan_dict.get("confidence", 0.5),
                source="llm",
            )

            # Cache the successful plan
            _store_cached_plan(goal, plan_dict)

            elapsed = time.monotonic() - t0
            emit(
                EventType.GOAL_PLANNED,
                source="planner",
                data={"goal": goal, "steps": len(p.steps), "confidence": p.confidence, "elapsed_s": round(elapsed, 2)},
                correlation_id=run_id,
            )
            return p

        except subprocess.TimeoutExpired:
            last_error = f"LLM call timed out after {timeout_s}s"
            continue
        except Exception as exc:
            last_error = f"Planning error: {exc}"
            continue

    raise PlanError(
        f"Planning failed after {attempts} attempts: {last_error}",
    )
