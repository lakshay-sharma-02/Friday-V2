"""MCU Friday CLI — proper entry point.

Usage:
    python -m friday_mcu                     # interactive REPL
    python -m friday_mcu run \"goal\"           # one-shot goal execution
    python -m friday_mcu status              # system health
    python -m friday_mcu triggers            # list configured triggers
    python -m friday_mcu primitives          # list registered primitives
    python -m friday_mcu logs                # recent log entries
    python -m friday_mcu memory search \"x\"   # search memories
    python -m friday_mcu memory summary      # memory overview
    python -m friday_mcu patterns            # detected patterns
    python -m friday_mcu adapters            # adapter status
    python -m friday_mcu api                 # start API server
    python -m friday_mcu watcher             # run ambient watcher daemon
    python -m friday_mcu watcher --once      # fire due triggers once
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _ensure_path() -> None:
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


# ── Commands


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a single goal through the full pipeline."""
    _ensure_path()
    from friday_mcu.brain.context import ContextManager
    from friday_mcu.brain.executor import run_plan
    from friday_mcu.brain.planner import plan
    from friday_mcu.brain.reasoning import Reasoner
    from friday_mcu.core.contracts import REGISTRY
    from friday_mcu.core.observability import set_run_id
    from friday_mcu.core.registry import ensure_registry
    from friday_mcu.memory.store import MemoryManager

    ensure_registry()  # load all adapters first

    goal = args.goal
    run_id = f"cli-{int(time.time())}"
    set_run_id(run_id)

    print(f"\n  Goal: {goal}")
    print(f"  Run ID: {run_id}")

    # Context
    print("\n--- Context ---")
    ctx = ContextManager()
    ctx.set_goal(goal)
    context_text = ctx.build_full_context()
    print(f"  Context built ({len(context_text)} chars)")

    # Reasoning
    print("\n--- Reasoning ---")
    reasoner = Reasoner()
    assessment = reasoner.assess_goal(
        goal,
        available_primitives=list(REGISTRY.keys()),
    )
    print(f"  Decision: {assessment.decision} ({assessment.confidence:.0%})")
    if assessment.warnings:
        for w in assessment.warnings:
            print(f"  Warning: {w}")

    if assessment.decision == "skip":
        print("  Skipping — most required primitives unavailable.")
        return 1

    # Plan
    print("\n--- Planning (L4) ---")
    mgr = MemoryManager()
    memory_ctx = mgr.build_context(goal)
    try:
        t0 = time.monotonic()
        p = plan(goal, run_id=run_id, attempts=args.attempts, context=context_text, memory_context=memory_ctx)
        plan_time = time.monotonic() - t0
        print(f"  Plan accepted in {plan_time:.1f}s ({len(p.steps)} steps, confidence={p.confidence:.0%})")
        if args.show_plan:
            for i, step in enumerate(p.steps, 1):
                print(f"  {i}. {step.get('primitive', '?')}")
    except Exception as exc:
        print(f"  Planning failed: {exc}")
        return 1

    # Execute — failures (run_plan raises FridayError on ABORT) must still be
    # recorded to the learning loop, or every failure mode is invisible to it.
    print("\n--- Execution (L3) ---")
    exec_error: str | None = None
    result = None
    t0 = time.monotonic()
    try:
        result = run_plan(
            {"goal": p.goal, "steps": p.steps},
            run_id=run_id,
            confidence=p.confidence,
        )
        exec_time = time.monotonic() - t0
        icon = "+" if result.status == "COMPLETED" else "x"
        print(f"  [{icon}] {result.status} in {exec_time:.1f}s")

        for sr in result.steps:
            s_icon = "+" if sr.status == "VERIFIED" else "x"
            retries = f", {len(sr.retry_history)} retries" if sr.retry_history else ""
            print(f"    Step {sr.step_id}: [{s_icon}] {sr.status} ({sr.primitive}, {sr.attempts} attempts{retries})")
            if sr.error:
                print(f"      Error: {sr.error[:80]}")
    except Exception as exc:
        exec_time = time.monotonic() - t0
        exec_error = str(exc)
        print(f"  Execution failed: {exc}")
    else:
        # Store in memory and record learning (success path)
        if result.status == "COMPLETED":
            try:
                mgr.store(
                    key=f"goal_{run_id}",
                    content=f"Goal: {goal} -> {result.status} ({len(result.steps)} steps)",
                    memory_type="episodic",
                    tags=["cli", "success"],
                )
                mgr.procedural.store_pattern(
                    goal,
                    [{"primitive": s.primitive, "status": s.status} for s in result.steps],
                    success=True,
                    confidence=p.confidence,
                )
            except Exception:
                pass

    # Record learning outcome for BOTH success and failure paths
    steps_data = []
    if result is not None:
        steps_data = [{"primitive": s.primitive, "status": s.status} for s in result.steps]
    success = result is not None and result.status == "COMPLETED"
    try:
        from friday_mcu.memory.learning import MemoryLearner
        learner = MemoryLearner()
        learner.record_outcome(
            goal=goal,
            success=success,
            duration_s=exec_time,
            steps=steps_data,
            error=exec_error or ("" if success else ((result.steps[-1].error if result and result.steps else "") or "unknown")),
        )
    except Exception:
        pass

    return 0 if success else 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show system health and status."""
    _ensure_path()
    from friday_mcu.adapters import list_adapters
    from friday_mcu.core.contracts import REGISTRY
    from friday_mcu.core.registry import discover_modules, ensure_registry
    from friday_mcu.memory.store import MemoryManager

    ensure_registry()
    modules = discover_modules()

    print("\n  MCU Friday Status")
    print("  " + "=" * 40)
    print(f"  Version: 1.0.0")
    print(f"  Primitives: {len(REGISTRY)} registered")
    print(f"  Adapter modules: {len(modules)}")

    # Adapters
    adapters = list_adapters()
    healthy = sum(1 for a in adapters.values() if a.health_check())
    print(f"  Adapters: {len(adapters)} registered ({healthy} healthy)")

    # Memory
    mgr = MemoryManager()
    episodic_count = len(mgr.episodic.recent(1000))
    semantic_count = len(mgr.semantic.list_all())
    print(f"  Memory: {episodic_count} episodic, {semantic_count} semantic")

    # Log file
    log_file = Path(os.environ.get("FRIDAY_LOG_FILE", str(PROJECT_ROOT / "var" / "logs" / "friday.jsonl")))
    if log_file.exists():
        lines = log_file.read_text(encoding="utf-8").strip().splitlines()
        print(f"  Log entries: {len(lines)}")
    else:
        print(f"  Log entries: none")

    print()
    return 0


def cmd_primitives(args: argparse.Namespace) -> int:
    """List registered primitives."""
    _ensure_path()
    from friday_mcu.core.contracts import EXECUTOR_BLOCKED, REGISTRY
    from friday_mcu.core.registry import build_catalog, ensure_registry

    ensure_registry()

    if args.catalog:
        print(build_catalog())
        return 0

    print(f"\n  Registered Primitives ({len(REGISTRY)} total)\n")
    current_module = ""
    for q in sorted(REGISTRY):
        mod = q.split(".")[0]
        if mod != current_module:
            current_module = mod
            print(f"\n  [{mod}]")
        c = REGISTRY[q]
        blocked = " [BLOCKED]" if q in EXECUTOR_BLOCKED else ""
        print(f"    {q} [{c.idempotency.value}]{blocked}")
    print()
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    """Show recent log entries."""
    log_file = Path(os.environ.get("FRIDAY_LOG_FILE", str(PROJECT_ROOT / "var" / "logs" / "friday.jsonl")))
    if not log_file.exists():
        print(f"  No log file at {log_file}")
        return 1

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-args.count:]

    print(f"\n  Recent log entries ({len(recent)} of {len(lines)})\n")
    for line in recent:
        try:
            rec = json.loads(line)
            ts = rec.get("timestamp", "?")[:19]
            layer = rec.get("layer", "?")
            prim = rec.get("primitive", "?")
            result = rec.get("result", "")
            exc = rec.get("exception", "")
            dur = rec.get("duration_ms", 0)
            icon = "x" if exc else "+"
            print(f"  {ts} [{icon}] {layer:6s} {prim:30s} {str(result)[:40]:40s} ({dur:.0f}ms)")
            if exc:
                print(f"           Error: {exc[:80]}")
        except (json.JSONDecodeError, ValueError):
            print(f"  (malformed line)")
    print()
    return 0


def cmd_memory(args: argparse.Namespace) -> int:
    """Query the memory store."""
    _ensure_path()
    from friday_mcu.memory.store import MemoryManager

    mgr = MemoryManager()

    if args.subcmd == "summary":
        s = mgr.episodic.recent(1000)
        semantic = mgr.semantic.list_all()
        print(f"\n  Memory Summary\n")
        print(f"  Episodic: {len(s)} entries")
        print(f"  Semantic: {len(semantic)} entries")
        print(f"  Procedural patterns: {len(mgr.procedural.all_patterns())}")
        recent = mgr.episodic.recent(5)
        if recent:
            print(f"\n  Recent episodic:")
            for m in recent:
                print(f"    [{m.category}] {m.content[:60]}")
        print()
        return 0

    elif args.subcmd == "search":
        results = mgr.search_all(args.query, limit=args.limit)
        print(f"\n  Memory search: '{args.query}' ({len(results)} results)\n")
        for r in results:
            print(f"  [{r.category}] {r.key} (strength={r.strength:.2f})")
            print(f"    {r.content[:80]}")
        print()
        return 0

    elif args.subcmd == "store":
        entry = mgr.store(args.key, args.value, memory_type=args.memory_type or "episodic")
        print(f"  Stored: {entry.key} ({entry.category})")
        return 0

    elif args.subcmd == "forget":
        found = mgr.semantic.forget(args.key)
        if found:
            print(f"  Forgotten: {args.key}")
        else:
            print(f"  Not found: {args.key}")
        return 0

    print("  Usage: memory [summary|search|store|forget] ...")
    return 1


def cmd_patterns(args: argparse.Namespace) -> int:
    """Show detected patterns."""
    _ensure_path()
    from friday_mcu.memory.store import MemoryManager
    from friday_mcu.observer.patterns import PatternDetector

    mgr = MemoryManager()
    recent = mgr.episodic.recent(100)
    tasks = [
        {"goal": m.content.split("->")[0].replace("Goal:", "").strip(), "gate6_passed": "success" in m.content.lower(), "timestamp": m.created_at}
        for m in recent
    ]

    detector = PatternDetector()
    patterns = detector.analyze(tasks, min_occurrences=1)

    print(f"\n  Detected Patterns ({len(patterns)} total)\n")
    for p in patterns:
        print(f"  [{p.type}] {p.description}")
        print(f"    Frequency: {p.frequency}, Confidence: {p.confidence:.0%}")
    print()
    return 0


def cmd_adapters(args: argparse.Namespace) -> int:
    """Show adapter status."""
    _ensure_path()
    from friday_mcu.core.registry import ensure_registry
    ensure_registry()  # triggers adapter imports
    from friday_mcu.adapters import list_adapters

    adapters = list_adapters()
    print(f"\n  Registered Adapters ({len(adapters)} total)\n")
    for name, adapter in sorted(adapters.items()):
        status = "+" if adapter.health_check() else "x"
        caps = ", ".join(adapter.capabilities[:5])
        print(f"  [{status}] {name}: {caps}")
    print()
    return 0


def cmd_api(args: argparse.Namespace) -> int:
    """Start the API server."""
    _ensure_path()
    from friday_mcu.api.server import _auth_token, _is_loopback, create_app
    import uvicorn

    if not _is_loopback(args.host) and not _auth_token():
        print(
            "  Refusing to bind non-loopback host without auth. "
            "Set FRIDAY_API_TOKEN and call with `Authorization: Bearer <token>`,"
            " or bind 127.0.0.1."
        )
        return 1

    app = create_app()
    port = args.port
    host = args.host

    print(f"\n  MCU Friday API starting on {host}:{port}")
    print(f"  Docs:   http://{host}:{port}/docs")
    print(f"  Health: http://{host}:{port}/health")
    print(f"  WS:     ws://{host}:{port}/ws/events\n")

    uvicorn.run(app, host=host, port=port)
    return 0


def cmd_watcher(args: argparse.Namespace) -> int:
    """Run the MCU watcher daemon."""
    _ensure_path()
    from friday_mcu.watcher import run_watcher

    print(f"\n  MCU Friday Watcher starting")
    if args.once:
        print("  Mode: once (fire due triggers, then exit)")
    else:
        print(f"  Mode: daemon (poll every {args.poll}s)")
    print()

    run_watcher(
        args.config,
        once=args.once,
        poll_s=args.poll,
        heartbeat_s=args.heartbeat,
    )
    return 0


def cmd_triggers(args: argparse.Namespace) -> int:
    """List configured triggers."""
    _ensure_path()
    from friday_mcu.watcher import load_config

    try:
        triggers = load_config(args.config)
    except Exception as exc:
        print(f"  Error loading config: {exc}")
        return 1

    print(f"\n  Configured Triggers ({len(triggers)} total)\n")
    for t in triggers:
        enabled = "[ON]" if t.get("enabled", True) else "[OFF]"
        tid = t["id"]
        sch = t.get("schedule", {})
        sch_type = sch.get("type", "?")
        if sch_type == "time":
            sched = f"{sch.get('at', '?')}" 
            days = sch.get("days")
            if days:
                sched += f" ({','.join(days)})"
        elif sch_type == "file":
            sched = f"file:{sch.get('directory', '?')}/*.{sch.get('name', '?')}"
        else:
            sched = sch_type
        goal = t.get("goal", "(deterministic plan)")[:50]
        allow = t.get("allow")
        allow_str = f" allow=[{','.join(allow[:3])}]" if allow else ""
        print(f"  {enabled} {tid}")
        print(f"    schedule: {sched}")
        print(f"    goal: {goal}{allow_str}")
    print()
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Show version."""
    print("  MCU Friday v1.0.0")
    return 0


# ── REPL


def _run_repl() -> int:
    """Interactive REPL mode."""
    _ensure_path()
    print(f"\n  MCU Friday v1.0.0 - Interactive Mode")
    print("  Type a goal in natural language, or 'help' for commands.\n")

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
        if goal == "help":
            print("""  Commands:
    <natural language goal>  - Execute a goal
    status                  - System health check
    primitives              - List registered primitives
    adapters                - Adapter status
    logs                    - Recent log entries
    memory summary          - Memory overview
    memory search <query>   - Search memories
    patterns                - Detected patterns
    api                     - Start API server
    help                    - This help
    quit / exit             - Exit
""")
            continue
        if goal == "status":
            cmd_status(argparse.Namespace())
            continue
        if goal == "primitives":
            cmd_primitives(argparse.Namespace(catalog=False))
            continue
        if goal == "adapters":
            cmd_adapters(argparse.Namespace())
            continue
        if goal == "logs":
            cmd_logs(argparse.Namespace(count=20))
            continue
        if goal == "patterns":
            cmd_patterns(argparse.Namespace())
            continue
        if goal.startswith("memory "):
            parts = goal.split(None, 2)
            if len(parts) >= 3 and parts[1] == "search":
                cmd_memory(argparse.Namespace(subcmd="search", query=parts[2], limit=5))
            elif len(parts) >= 2 and parts[1] == "summary":
                cmd_memory(argparse.Namespace(subcmd="summary"))
            else:
                print("  Usage: memory search <query> | memory summary")
            continue

        # Default: treat as a goal
        cmd_run(argparse.Namespace(goal=goal, attempts=3, show_plan=False))

    return 0


# ── Main


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="friday",
        description="MCU Friday — An AI that observes, infers, acts, learns, and communicates",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # run
    p_run = sub.add_parser("run", help="Execute a goal")
    p_run.add_argument("goal", help="Natural-language goal to execute")
    p_run.add_argument("--attempts", type=int, default=3, help="Max planning attempts")
    p_run.add_argument("--show-plan", action="store_true", help="Print the plan")

    # status
    sub.add_parser("status", help="Show system health")

    # primitives
    p_prim = sub.add_parser("primitives", help="List registered primitives")
    p_prim.add_argument("--catalog", action="store_true", help="Show full catalog (for LLM)")

    # logs
    p_logs = sub.add_parser("logs", help="Show recent log entries")
    p_logs.add_argument("-n", "--count", type=int, default=20, help="Number of entries")

    # memory
    p_mem = sub.add_parser("memory", help="Query memory store")
    mem_sub = p_mem.add_subparsers(dest="subcmd")
    mem_sub.add_parser("summary", help="Show memory summary")
    p_mem_search = mem_sub.add_parser("search", help="Search memories")
    p_mem_search.add_argument("query", help="Search query")
    p_mem_search.add_argument("--limit", type=int, default=5)
    p_mem_store = mem_sub.add_parser("store", help="Store a memory")
    p_mem_store.add_argument("key", help="Memory key")
    p_mem_store.add_argument("value", help="Memory value")
    p_mem_store.add_argument("--memory-type", help="Type (episodic/semantic)")
    p_mem_forget = mem_sub.add_parser("forget", help="Delete a memory")
    p_mem_forget.add_argument("key", help="Key to forget")

    # patterns
    sub.add_parser("patterns", help="Show detected patterns")

    # adapters
    sub.add_parser("adapters", help="Adapter status")

    # api
    p_api = sub.add_parser("api", help="Start API server")
    p_api.add_argument("--port", type=int, default=8080)
    p_api.add_argument("--host", default="127.0.0.1")

    # watcher
    p_watch = sub.add_parser("watcher", help="Run the watcher daemon")
    p_watch.add_argument("--config", default="config/watcher_mcu.json", help="Watcher config JSON (default: config/watcher_mcu.json)")
    p_watch.add_argument("--once", action="store_true", help="Fire due triggers once, then exit")
    p_watch.add_argument("--poll", type=float, default=30.0, help="Poll interval seconds")
    p_watch.add_argument("--heartbeat", type=float, default=120.0, help="Heartbeat interval seconds")

    # triggers
    p_trig = sub.add_parser("triggers", help="List configured triggers")
    p_trig.add_argument("--config", default="config/watcher_mcu.json", help="Watcher config JSON")

    # version
    sub.add_parser("version", help="Show version")

    args = parser.parse_args(argv)

    if args.command is None:
        return _run_repl()

    cmds = {
        "run": cmd_run,
        "status": cmd_status,
        "primitives": cmd_primitives,
        "logs": cmd_logs,
        "memory": cmd_memory,
        "patterns": cmd_patterns,
        "adapters": cmd_adapters,
        "api": cmd_api,
        "watcher": cmd_watcher,
        "triggers": cmd_triggers,
        "version": cmd_version,
    }
    return cmds[args.command](args)


if __name__ == "__main__":
    raise SystemExit(main())
