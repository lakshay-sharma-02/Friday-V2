"""MCU Friday — End-to-End Demo

Runs a goal through the full pipeline:
  context → reasoning → planner → executor → memory → observer

Usage:
    python -m friday_mcu.demo                     # interactive mode
    python -m friday_mcu.demo "check my email"    # one-shot goal
    python -m friday_mcu.demo --status            # system health check
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any


def print_header(text: str) -> None:
    import sys
    # Force UTF-8 on Windows
    if sys.platform == 'win32':
        sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    print(f"\n{'='*60}")
    print(f"  {text}")
    print(f"{'='*60}\n")


def print_step(step: str, detail: str = "") -> None:
    print(f"  -> {step}")
    if detail:
        print(f"    {detail}")


def show_status() -> None:
    """Show system health and status."""
    print_header("MCU Friday — System Status")

    # Core
    from friday_mcu.core.contracts import REGISTRY
    from friday_mcu.core.registry import ensure_registry, discover_modules
    ensure_registry()
    modules = discover_modules()
    print_step("Core", f"{len(REGISTRY)} primitives registered from {len(modules)} adapter modules")

    # Adapters
    from friday_mcu.adapters import list_adapters
    adapters = list_adapters()
    healthy = sum(1 for a in adapters.values() if a.health_check())
    print_step("Adapters", f"{len(adapters)} registered, {healthy} healthy")
    for name, adapter in adapters.items():
        status = "✓" if adapter.health_check() else "✗"
        print(f"      {status} {name}: {', '.join(adapter.capabilities[:3])}...")

    # Memory
    from friday_mcu.memory.store import MemoryManager
    mgr = MemoryManager()
    episodic_count = len(mgr.episodic.recent(1000))
    semantic_count = len(mgr.semantic.list_all())
    print_step("Memory", f"{episodic_count} episodic, {semantic_count} semantic entries")

    # Observer
    print_step("Observer", "Pattern detection ready")

    # Comms
    from friday_mcu.comms.adaptive import AdaptiveComms
    ac = AdaptiveComms()
    stats = ac.get_stats()
    print_step("Comms", f"{stats['total_sends']} sends recorded")

    print()


def run_goal(goal: str) -> None:
    """Run a goal through the full MCU Friday pipeline."""
    run_id = f"demo-{int(time.time())}"
    print_header(f"MCU Friday — Goal: {goal}")
    print_step("Run ID", run_id)

    # ── Step 1: Build Context
    print_step("Context", "Building working + goal + environmental context...")
    t0 = time.time()
    from friday_mcu.brain.context import ContextManager
    ctx = ContextManager()
    ctx.set_goal(goal)
    context_text = ctx.build_full_context()
    print(f"    ┌─ Working: {len(ctx.working.to_text())} chars")
    print(f"    ├─ Goal: {ctx.goal.goal}")
    print(f"    └─ Environment: {ctx.environment.platform or 'unknown'}")
    print(f"    Context built in {(time.time()-t0)*1000:.0f}ms")

    # ── Step 2: Reason
    print_step("Reasoning", "Assessing goal feasibility...")
    t0 = time.time()
    from friday_mcu.brain.reasoning import Reasoner
    from friday_mcu.core.registry import build_catalog
    from friday_mcu.memory.store import MemoryManager as _MemMgr
    _mem = _MemMgr()
    reasoner = Reasoner()
    catalog = build_catalog()
    assessment = reasoner.assess_goal(
        goal,
        available_primitives=list(REGISTRY.keys()) if REGISTRY else [],
        memory_context=_mem.build_context(goal),
    )
    print(f"    Decision: {assessment.decision}")
    print(f"    Confidence: {assessment.confidence:.0%}")
    if assessment.warnings:
        for w in assessment.warnings:
            print(f"    ⚠ {w}")
    print(f"    Reasoning: {assessment.reasoning}")
    print(f"    Assessed in {(time.time()-t0)*1000:.0f}ms")

    if assessment.decision == "skip":
        print("\n  ✗ Goal skipped — most required primitives are unavailable.")
        return

    # ── Step 3: Plan
    print_step("Planning", "Generating plan via LLM (Claude CLI)...")
    t0 = time.time()
    from friday_mcu.brain.planner import plan, Plan
    try:
        p = plan(goal, run_id=run_id, context=context_text)
        print(f"    Steps: {len(p.steps)}")
        print(f"    Confidence: {p.confidence:.0%}")
        for i, step in enumerate(p.steps, 1):
            prim = step.get("primitive", "?")
            check = step.get("verify", {}).get("check", "?")
            print(f"    {i}. {prim} → verify: {check}")
        print(f"    Planned in {(time.time()-t0)*1000:.0f}ms")
    except Exception as exc:
        print(f"    ✗ Planning failed: {exc}")
        print(f"    Falling back to context-only execution")
        return

    # ── Step 4: Execute
    print_step("Execution", "Running plan through L3 executor...")
    t0 = time.time()
    from friday_mcu.brain.executor import run_plan
    try:
        result = run_plan(
            {"goal": p.goal, "steps": p.steps},
            run_id=run_id,
            confidence=p.confidence,
        )
        print(f"    Status: {result.status}")
        for sr in result.steps:
            icon = "✓" if sr.status == "VERIFIED" else "✗"
            retries = f" ({len(sr.retry_history)} retries)" if sr.retry_history else ""
            print(f"    {icon} Step {sr.step_id}: {sr.primitive} [{sr.status}]{retries}")
            if sr.error:
                print(f"      Error: {sr.error[:80]}")
        print(f"    Executed in {(time.time()-t0)*1000:.0f}ms")
    except Exception as exc:
        print(f"    ✗ Execution failed: {exc}")
        return

    # ── Step 5: Store in Memory
    print_step("Memory", "Storing outcome for future reference...")
    from friday_mcu.memory.store import MemoryManager
    mgr = MemoryManager()
    mgr.store(
        key=f"goal_{run_id}",
        content=f"Goal: {goal} → {result.status} ({len(result.steps)} steps)",
        memory_type="episodic",
        tags=["demo", result.status.lower()],
    )
    mgr.procedural.store_pattern(
        goal,
        [{"primitive": s.primitive, "status": s.status} for s in result.steps],
        success=result.status == "COMPLETED",
        confidence=p.confidence,
    )
    print(f"    Stored: episodic + procedural memory updated")

    # ── Step 6: Observe
    print_step("Observer", "Analyzing patterns...")
    from friday_mcu.observer.patterns import PatternDetector
    detector = PatternDetector()
    # Build a mini task history from recent memory
    recent = mgr.episodic.recent(20)
    mini_tasks = [
        {"goal": m.content.split("→")[0].replace("Goal:", "").strip(), "gate6_passed": "completed" in m.content.lower(), "timestamp": m.created_at}
        for m in recent
    ]
    patterns = detector.analyze(mini_tasks, min_occurrences=1)
    if patterns:
        print(f"    Detected {len(patterns)} pattern(s):")
        for p in patterns[:3]:
            print(f"      [{p.type}] {p.description[:60]}")
    else:
        print(f"    No patterns detected yet (need more data)")

    # ── Summary
    print_header("Result")
    print(f"  Goal: {goal}")
    print(f"  Status: {result.status}")
    print(f"  Steps: {len(result.steps)}")
    print(f"  Confidence: {p.confidence:.0%}")
    print(f"  Memory: stored")
    print(f"  Patterns: {len(patterns)} detected")
    print()


def interactive_mode() -> None:
    """Interactive REPL mode."""
    print_header("MCU Friday — Interactive Mode")
    print("  Type a goal to execute, or 'status' for health check.")
    print("  Type 'quit' to exit.\n")

    while True:
        try:
            goal = input("friday> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n  Goodbye!")
            break

        if not goal:
            continue
        if goal in ("quit", "exit", "q"):
            print("  Goodbye!")
            break
        if goal == "status":
            show_status()
            continue
        if goal == "help":
            print("  Commands: status, help, quit")
            print("  Or type a natural language goal to execute.")
            continue

        run_goal(goal)


def main() -> None:
    """Entry point."""
    args = sys.argv[1:]

    if not args or args[0] == "repl":
        interactive_mode()
    elif args[0] == "--status" or args[0] == "status":
        show_status()
    elif args[0] == "--help" or args[0] == "help":
        print(__doc__)
    else:
        goal = " ".join(args)
        run_goal(goal)


if __name__ == "__main__":
    main()
