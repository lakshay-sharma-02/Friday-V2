"""Friday CLI — interactive entry point.

Run:  python -m friday              (interactive REPL)
      python -m friday run "goal"   (one-shot goal execution)
      python -m friday status       (system health check)
      python -m friday triggers     (list configured triggers)
      python -m friday primitives   (list registered primitives)
      python -m friday logs         (recent log entries)
      friday                        (console_scripts entry point)

The REPL accepts natural-language goals and runs them through the
full L4→L3→L2→L1 pipeline, printing the plan and execution trace.
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


def _ensure_project_root() -> None:
    """Make sure the project root is on sys.path."""
    root = str(PROJECT_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def cmd_run(args: argparse.Namespace) -> int:
    """Execute a single goal through the full pipeline."""
    _ensure_project_root()
    from friday.l4.planner import plan
    from friday.l3.executor import run_plan
    from friday.observability import set_run_id

    goal = args.goal
    run_id = f"cli-{int(time.time())}"
    set_run_id(run_id)

    print(f"\n🎯 Goal: {goal}")
    print(f"📋 Run ID: {run_id}")
    print("\n--- Planning (L4) ---")

    try:
        t0 = time.monotonic()
        p = plan(goal, run_id=run_id, attempts=args.attempts)
        plan_time = time.monotonic() - t0
        print(f"✅ Plan accepted in {plan_time:.1f}s ({len(p['steps'])} steps)")
        if args.show_plan:
            print(json.dumps(p, indent=2, default=str))
    except Exception as exc:
        print(f"❌ Planning failed: {exc}")
        return 1

    print("\n--- Execution (L3) ---")
    try:
        t0 = time.monotonic()
        result = run_plan(p, run_id=run_id)
        exec_time = time.monotonic() - t0
        status_icon = "✅" if result.status == "COMPLETED" else "❌"
        print(f"{status_icon} {result.status} in {exec_time:.1f}s")

        for sr in result.steps:
            icon = {"VERIFIED": "✅", "FAILED": "❌", "RETRY_EXHAUSTED": "🚫", "ABORTED": "⛔"}.get(sr.status, "❓")
            print(f"  Step {sr.step_id}: {icon} {sr.status} ({sr.primitive}, {sr.attempts} attempts)")
            if sr.error:
                print(f"    Error: {sr.error}")

        # Record success in memory for future reference.
        # Best-effort: a memory failure must never break the CLI.
        if result.status == "COMPLETED":
            try:
                from friday.l1.memory import record_success
                step_summary = ", ".join(
                    s.primitive for s in result.steps if s.status == "VERIFIED"
                )
                record_success(
                    goal=goal,
                    outcome=f"plan completed: {step_summary}",
                    tags=["source:cli"],
                )
            except Exception:
                pass

        return 0 if result.status == "COMPLETED" else 1
    except Exception as exc:
        print(f"❌ Execution failed: {exc}")
        return 1


def cmd_status(args: argparse.Namespace) -> int:
    """Show system health and status."""
    _ensure_project_root()

    print("\n📊 Friday Status")
    print("=" * 50)

    # Version
    from friday import __version__
    print(f"  Version: {__version__}")

    # Registry
    try:
        from friday.l4.planner import _ensure_registry
        from friday.contracts import REGISTRY, EXECUTOR_BLOCKED
        _ensure_registry()
        total = len(REGISTRY)
        blocked = len(EXECUTOR_BLOCKED)
        print(f"  Primitives: {total} registered ({blocked} blocked)")
    except Exception as e:
        print(f"  Primitives: error - {e}")

    # Checks
    try:
        from friday.l2 import checks
        check_count = len([n for n in dir(checks) if not n.startswith("_") and callable(getattr(checks, n))])
        print(f"  L2 checks: {check_count}")
    except Exception as e:
        print(f"  L2 checks: error - {e}")

    # Triggers
    try:
        config_path = PROJECT_ROOT / "config" / "watcher.json"
        if config_path.exists():
            data = json.loads(config_path.read_text())
            triggers = data.get("triggers", [])
            enabled = [t for t in triggers if t.get("enabled", False)]
            print(f"  Triggers: {len(enabled)} enabled / {len(triggers)} total")
        else:
            print("  Triggers: config not found")
    except Exception as e:
        print(f"  Triggers: error - {e}")

    # Tasks
    tasks_file = PROJECT_ROOT / "var" / "logs" / "tasks.jsonl"
    if tasks_file.exists():
        try:
            lines = tasks_file.read_text().strip().splitlines()
            passing = sum(1 for l in lines if "gate6_passed\": true" in l.lower())
            print(f"  Tasks: {passing} passing / {len(lines)} total")
        except Exception:
            print("  Tasks: (parse error)")
    else:
        print("  Tasks: no task log found")

    # Gaps
    gaps_file = PROJECT_ROOT / "var" / "logs" / "capability_gaps.jsonl"
    if gaps_file.exists():
        try:
            lines = gaps_file.read_text().strip().splitlines()
            pending = sum(1 for l in lines if "processed\": false" in l.lower())
            print(f"  Gap records: {len(lines)} total ({pending} pending)")
        except Exception:
            print("  Gap records: (parse error)")
    else:
        print("  Gap records: none")

    # Watcher daemon
    try:
        result = os.popen("systemctl --user is-active friday-watcher.service 2>/dev/null").read().strip()
        print(f"  Watcher daemon: {result}")
    except Exception:
        print("  Watcher daemon: unknown")

    # Memory
    try:
        from friday.l1.memory import summary as mem_summary
        s = mem_summary()
        print(f"  Memory: {s.get('total', 0)} entries")
    except Exception:
        print("  Memory: unavailable")

    print()
    return 0


def cmd_triggers(args: argparse.Namespace) -> int:
    """List configured triggers."""
    config_path = PROJECT_ROOT / "config" / "watcher.json"
    if not config_path.exists():
        print("No watcher config found at config/watcher.json")
        return 1

    data = json.loads(config_path.read_text())
    triggers = data.get("triggers", [])

    print(f"\n📋 Triggers ({len(triggers)} total)\n")
    for t in triggers:
        status = "🟢" if t.get("enabled") else "🔴"
        tid = t.get("id", "unknown")
        schedule = t.get("schedule", {})
        sched_type = schedule.get("type", "?")
        if sched_type == "time":
            sched_str = f"{schedule.get('at', '?')} ({', '.join(schedule.get('days', ['daily']))})"
        elif sched_type == "file":
            sched_str = f"file: {schedule.get('directory', '?')}/{schedule.get('name', '?')}"
        else:
            sched_str = str(schedule)
        allow = t.get("allow", [])
        allow_str = f" [{len(allow)} allowed]" if allow else ""
        print(f"  {status} {tid}")
        print(f"     Schedule: {sched_str}{allow_str}")
        goal = t.get("goal", "")
        if goal:
            print(f"     Goal: {goal[:80]}")
        print()
    return 0


def cmd_primitives(args: argparse.Namespace) -> int:
    """List registered primitives."""
    _ensure_project_root()
    from friday.l4.planner import _ensure_registry, build_catalog
    from friday.contracts import REGISTRY, EXECUTOR_BLOCKED
    _ensure_registry()

    if args.catalog:
        print(build_catalog())
        return 0

    print(f"\n🔧 Registered Primitives ({len(REGISTRY)} total)\n")
    current_module = ""
    for q in sorted(REGISTRY):
        mod = q.split(".")[0]
        if mod != current_module:
            current_module = mod
            blocked_count = sum(1 for k in REGISTRY if k.startswith(mod + ".") and k in EXECUTOR_BLOCKED)
            suffix = f" ({blocked_count} blocked)" if blocked_count else ""
            print(f"\n  [{mod}]{suffix}")
        c = REGISTRY[q]
        blocked = " ⛔" if q in EXECUTOR_BLOCKED else ""
        print(f"    {q} [{c.idempotency.value}]{blocked}")
    print()
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    """Show recent log entries."""
    log_file = Path(os.environ.get("FRIDAY_LOG_FILE", str(PROJECT_ROOT / "var" / "logs" / "friday.jsonl")))
    if not log_file.exists():
        print(f"No log file found at {log_file}")
        return 1

    lines = log_file.read_text(encoding="utf-8").strip().splitlines()
    recent = lines[-args.count:]

    print(f"\n📜 Recent log entries ({len(recent)} of {len(lines)})\n")
    for line in recent:
        try:
            rec = json.loads(line)
            ts = rec.get("timestamp", "?")[:19]
            layer = rec.get("layer", "?")
            prim = rec.get("primitive", "?")
            result = rec.get("result", "")
            exc = rec.get("exception", "")
            dur = rec.get("duration_ms", 0)
            status = "❌" if exc else "✅"
            print(f"  {ts} {status} {layer:6s} {prim:30s} {str(result)[:40]:40s} ({dur:.0f}ms)")
            if exc:
                print(f"           Error: {exc[:80]}")
        except (json.JSONDecodeError, ValueError):
            print(f"  (malformed line)")
    print()
    return 0


def cmd_memory(args: argparse.Namespace) -> int:
    """Query the memory store."""
    _ensure_project_root()
    from friday.l1.memory import retrieve, summary as mem_summary, store, forget

    if args.subcmd == "summary":
        s = mem_summary()
        print(f"\n🧠 Memory Summary\n")
        print(f"  Total entries: {s.get('total', 0)}")
        for cat, count in s.get("categories", {}).items():
            print(f"    {cat}: {count}")
        recent = s.get("recent_keys", [])
        if recent:
            print(f"  Recent: {', '.join(recent[:5])}")
        print()
        return 0

    elif args.subcmd == "search":
        results = retrieve(args.query, category=args.category, limit=args.limit)
        print(f"\n🔍 Memory search: '{args.query}' ({len(results)} results)\n")
        for r in results:
            print(f"  [{r['category']}] {r['key']} (relevance: {r['relevance']:.2f})")
            print(f"    {r['value'][:100]}")
        print()
        return 0

    elif args.subcmd == "store":
        result = store(args.key, args.value, category=args.category or "facts")
        print(f"✅ Stored: {result['key']} ({result['status']})")
        return 0

    elif args.subcmd == "forget":
        result = forget(args.key)
        if result["found"]:
            print(f"✅ Forgotten: {args.key}")
        else:
            print(f"❌ Not found: {args.key}")
        return 0

    print("Usage: friday memory [summary|search|store|forget] ...")
    return 1


def cmd_lessons(args: argparse.Namespace) -> int:
    """Show lessons loop status."""
    _ensure_project_root()
    from friday.lessons import approved_lessons, list_events

    approved = approved_lessons()
    events = list_events()

    print(f"\n📚 Lessons Loop\n")
    print(f"  Approved lessons: {len(approved)}")
    for l in approved[:10]:
        print(f"    [{l.get('category', '?')}] {l.get('statement', '?')[:80]}")
    print(f"  Recorded events: {len(events)}")
    print()
    return 0


def cmd_gaps(args: argparse.Namespace) -> int:
    """Show capability gap status."""
    gaps_file = PROJECT_ROOT / "var" / "logs" / "capability_gaps.jsonl"
    if not gaps_file.exists():
        print("No capability gaps recorded.")
        return 0

    lines = gaps_file.read_text().strip().splitlines()
    pending = []
    processed = []
    for line in lines:
        try:
            rec = json.loads(line)
            if rec.get("processed", False):
                processed.append(rec)
            else:
                pending.append(rec)
        except (json.JSONDecodeError, ValueError):
            pass

    print(f"\n🔧 Capability Gaps\n")
    print(f"  Total: {len(lines)}")
    print(f"  Pending: {len(pending)}")
    print(f"  Processed: {len(processed)}")
    if pending:
        print(f"\n  Pending gaps:")
        for g in pending[:10]:
            prim = g.get("attempted_primitive", "?")
            reason = g.get("refusal_reason", "?")[:60]
            print(f"    {prim}: {reason}")
    print()
    return 0


def cmd_version(args: argparse.Namespace) -> int:
    """Show version info."""
    from friday import __version__
    print(f"Friday v{__version__}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="friday",
        description="Friday V8 - layered desktop automation",
    )
    sub = parser.add_subparsers(dest="command", help="Available commands")

    # run
    p_run = sub.add_parser("run", help="Execute a goal")
    p_run.add_argument("goal", help="Natural-language goal to execute")
    p_run.add_argument("--attempts", type=int, default=3, help="Max planning attempts")
    p_run.add_argument("--show-plan", action="store_true", help="Print the plan JSON")

    # status
    sub.add_parser("status", help="Show system health")

    # triggers
    sub.add_parser("triggers", help="List configured triggers")

    # primitives
    p_prim = sub.add_parser("primitives", help="List registered primitives")
    p_prim.add_argument("--catalog", action="store_true", help="Show full catalog (for LLM)")

    # logs
    p_logs = sub.add_parser("logs", help="Show recent log entries")
    p_logs.add_argument("-n", "--count", type=int, default=20, help="Number of recent entries")

    # memory
    p_mem = sub.add_parser("memory", help="Query the memory store")
    mem_sub = p_mem.add_subparsers(dest="subcmd")
    mem_sub.add_parser("summary", help="Show memory summary")
    p_mem_search = mem_sub.add_parser("search", help="Search memories")
    p_mem_search.add_argument("query", help="Search query")
    p_mem_search.add_argument("--category", help="Filter by category")
    p_mem_search.add_argument("--limit", type=int, default=5)
    p_mem_store = mem_sub.add_parser("store", help="Store a memory")
    p_mem_store.add_argument("key", help="Memory key")
    p_mem_store.add_argument("value", help="Memory value")
    p_mem_store.add_argument("--category", help="Category (default: facts)")
    p_mem_forget = mem_sub.add_parser("forget", help="Delete a memory")
    p_mem_forget.add_argument("key", help="Memory key to forget")

    # lessons
    sub.add_parser("lessons", help="Show lessons loop status")

    # gaps
    sub.add_parser("gaps", help="Show capability gap status")

    # version
    sub.add_parser("version", help="Show version")

    # repl (default)
    sub.add_parser("repl", help="Interactive REPL mode")

    args = parser.parse_args(argv)

    if args.command is None or args.command == "repl":
        return _run_repl()

    cmds = {
        "run": cmd_run,
        "status": cmd_status,
        "triggers": cmd_triggers,
        "primitives": cmd_primitives,
        "logs": cmd_logs,
        "memory": cmd_memory,
        "lessons": cmd_lessons,
        "gaps": cmd_gaps,
        "version": cmd_version,
    }
    return cmds[args.command](args)


def _run_repl() -> int:
    """Interactive REPL mode."""
    _ensure_project_root()
    from friday import __version__

    print(f"\n🤖 Friday v{__version__} — Interactive Mode")
    print("   Type a goal in natural language, or 'help' for commands.\n")

    while True:
        try:
            goal = input("friday> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n👋 Goodbye!")
            break

        if not goal:
            continue

        if goal in ("quit", "exit", "q"):
            print("👋 Goodbye!")
            break

        if goal == "help":
            print("""\nCommands:
  <natural language goal>  - Execute a goal
  status                   - System health check
  triggers                 - List configured triggers
  primitives               - List registered primitives
  logs                     - Recent log entries
  memory search <query>    - Search memories
  memory summary           - Memory store summary
  lessons                  - Show lessons status
  gaps                     - Show capability gaps
  help                     - This help
  quit / exit              - Exit\n""")
            continue

        if goal == "status":
            cmd_status(argparse.Namespace())
            continue

        if goal == "triggers":
            cmd_triggers(argparse.Namespace())
            continue

        if goal == "primitives":
            cmd_primitives(argparse.Namespace(catalog=False))
            continue

        if goal == "logs":
            cmd_logs(argparse.Namespace(count=20))
            continue

        if goal.startswith("memory "):
            parts = goal.split(None, 2)
            if len(parts) >= 3 and parts[1] == "search":
                cmd_memory(argparse.Namespace(subcmd="search", query=parts[2], category=None, limit=5))
            elif len(parts) >= 2 and parts[1] == "summary":
                cmd_memory(argparse.Namespace(subcmd="summary"))
            else:
                print("Usage: memory search <query> | memory summary")
            continue

        if goal == "lessons":
            cmd_lessons(argparse.Namespace())
            continue

        if goal == "gaps":
            cmd_gaps(argparse.Namespace())
            continue

        # Default: treat as a goal
        cmd_run(argparse.Namespace(goal=goal, attempts=3, show_plan=False))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
