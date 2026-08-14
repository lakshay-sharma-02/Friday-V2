#!/usr/bin/env python
"""Generate gates/CAPABILITIES.md from the LIVE registry.

The capability inventory is DERIVED from the running code - the registry,
the L2 checks, the watcher triggers and the gate-registered markers - so
the doc can never drift out of sync with reality the way a hand-maintained
inventory would. Read-only with respect to the system: nothing is
executed, sent, or launched; the only write is the generated markdown.

Run:  ./.venv/bin/python -u gates/generate_capabilities.py
"""
from __future__ import annotations

import inspect
import sys
from datetime import datetime, timezone
from pathlib import Path

# Date-only status line: a regeneration within the same day must produce an
# IDENTICAL file (the README/PLAN_STATUS entries call the generator
# idempotent - a seconds-precision timestamp would break that claim).
STATUS_DATE = datetime.now(timezone.utc).date().isoformat()

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.contracts import EXECUTOR_BLOCKED, REGISTRY  # noqa: E402
from friday.l4.planner import _checks, _ensure_registry, _sig  # noqa: E402
from friday.watcher import load_config  # noqa: E402

OUT = ROOT / "gates" / "CAPABILITIES.md"

# Presentation order for the primitive sections (anything not listed sorts last).
MODULE_ORDER = [
    "window", "media", "browser", "dev", "files", "git",
    "gmail", "whatsapp", "telegram", "discord", "notify", "digestcheck",
]


def _first_sentence(doc: str) -> str:
    return ((doc or "").strip().replace("\n", " ").split(".")[0].strip() or "bool")


def _trunc(text: str, n: int = 80) -> str:
    text = (text or "").strip().replace("\n", " ")
    return text if len(text) <= n else text[: n - 1] + "…"


def _gate_registered() -> list[str]:
    """Every '# ---- gate-registered <name>' marker in friday/l1/*.py -
    the primitives that entered the codebase through the capability-gap
    loop rather than by hand."""
    found: list[str] = []
    for py in sorted(ROOT.glob("friday/l1/*.py")):
        for line in py.read_text(encoding="utf-8").splitlines():
            if "# ---- gate-registered" in line:
                name = line.split("gate-registered", 1)[1].split("(", 1)[0].strip()
                found.append(name)
    return sorted(found)


def main() -> int:
    _ensure_registry()
    checks = _checks()
    triggers = sorted(load_config(str(ROOT / "config" / "watcher.json")), key=lambda t: t["id"])

    add = (lines := []).append

    add("# CAPABILITIES - what Friday can do (generated from the live registry)")
    add("")
    add(f"Status date: {STATUS_DATE}.")
    add("")
    add("**This document is GENERATED from the running code, not hand-maintained** -")
    add("regenerate it after any primitive/check/trigger change:")
    add("")
    add("```sh")
    add("./.venv/bin/python -u gates/generate_capabilities.py   # rewrites gates/CAPABILITIES.md")
    add("```")
    add("")
    add("The pipeline: L4 LLM planner -> L3 deterministic executor (retry policy derived")
    add("from each primitive's contract) -> L2 read-only verification -> L1 contract-")
    add("registered primitives -> L0 structured logs. An ambient watcher daemon fires")
    add("triggers on schedule with per-trigger primitive allowlists, and a closed")
    add("capability-gap loop lets human-approved new primitives register themselves.")
    add("")
    add(f"## L1 primitives ({len(REGISTRY)} registered)")
    add("")
    add("Retry semantics come from each contract's idempotency class: `idempotent` = safe")
    add("to blind-retry (read-only); `at-most-once` = never blindly retried (side effect);")
    add("`commutative-safe` = safe to re-run once the target state already matches.")
    add("")

    mods = sorted(
        {name.split(".")[0] for name in REGISTRY},
        key=lambda m: (MODULE_ORDER.index(m) if m in MODULE_ORDER else 99, m),
    )
    for mod in mods:
        add(f"### `{mod}`")
        add("")
        add("| primitive | idempotency | returns | failure mode |")
        add("|---|---|---|---|")
        for name in sorted(n for n in REGISTRY if n.startswith(mod + ".")):
            c = REGISTRY[name]
            fn_name = name.split(".")[1]
            fn = getattr(__import__(f"friday.l1.{mod}", fromlist=[fn_name]), fn_name, None)
            add(f"| `{name}{_sig(fn)}` | `{c.idempotency.value}` | {_trunc(c.returns, 70)} | {_trunc(c.failure_mode, 85)} |")
        add("")

    add(f"## L2 verification checks ({len(checks)})")
    add("")
    add("Every check is side-effect-free: it reads current real-world state and returns")
    add("True/False (or a scalar) against a specific claim. A step is VERIFIED only when")
    add("its check agrees with the world - absence of an exception is never enough.")
    add("")
    add("| check | claim |")
    add("|---|---|")
    for cname in sorted(checks):
        add(f"| `checks.{cname}` | {_first_sentence(inspect.getdoc(checks[cname]))} |")
    add("")

    add("## Executor-blocked primitives")
    add("")
    add("Registered but NEVER reachable from a plan or the planner catalog - the LLM")
    add("never sees them and L3 refuses them:")
    add("")
    add("```")
    for b in sorted(EXECUTOR_BLOCKED):
        add(f"  {b}")
    add("```")
    add("")

    add("## Ambient watcher triggers (config/watcher.json)")
    add("")
    add("| id | enabled | schedule | notify | allow |")
    add("|---|---|---|---|---|")
    for t in triggers:
        sch = t.get("schedule") or {}
        days = ",".join(sch.get("days") or []) or "daily"
        when = f"{sch.get('type', '?')} {sch.get('at', '-')} [{days}]"
        allow = ", ".join(t.get("allow") or []) or "-"
        add(f"| `{t['id']}` | {str(t.get('enabled', True)).lower()} | {when} | {str(t.get('notify', True)).lower()} | {_trunc(allow, 60)} |")
    add("")

    add("## Capability-gap loop (self-improvement)")
    add("")
    add("A refused/unknown primitive step becomes a structured `capability_gap` record;")
    add("triage LLM-drafts a proposal (contract + impl + test); the automated gate (AST")
    add("checks + sandboxed test run + build-verify where applicable) filters it before")
    add("a human signature; on approval the primitive registers into L1 and the planner")
    add("auto-discovers it - the originally-refused goal then re-runs and must pass.")
    add("")
    gr = _gate_registered()
    add(f"Gate-registered primitives ({len(gr)}):")
    add("")
    for name in gr:
        add(f"- `{name}`")
    add("")

    add("## Ambient learning (lessons + goal proposals)")
    add("")
    add("- **Lessons loop**: approved 'known mistakes' are injected into future")
    add("  synthesis (e.g. the digest's attribution lesson) so past defects shape")
    add("  later output instead of recurring.")
    add("- **Goal proposals**: mines the failure history (var/logs/tasks.jsonl) into")
    add("  candidate NEW triggers - inert until a human grants scope and allowlist.")
    add("")

    add("## The ambient digest (Phase C)")
    add("")
    add("Weekly (Sundays 10:00): `git.log` across the configured repos, each repo's most")
    add("recently modified status/planning doc (`files.find_recent_doc`), `dev.digest`")
    add("synthesis, `digestcheck.verify_attribution` (the provenance guard - no repo may")
    add("be credited with a mechanism not in its own gathered content) and a desktop")
    add("`notify`. The suggestions are human-judged in `gates/DIGEST_TRACKING.md`.")
    add("")

    content = "\n".join(lines) + "\n"
    prev = OUT.read_text(encoding="utf-8") if OUT.is_file() else None
    OUT.write_text(content, encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)}")
    print(f"  {len(REGISTRY)} primitives | {len(checks)} checks | {len(triggers)} triggers | {len(gr)} gate-registered")
    print(f"  idempotent (unchanged): {prev == content}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
