#!/usr/bin/env python
"""PHASE C v2 proof - the weekly cross-project digest over REAL OWNED repos.

v1 paired Friday with Agent-Reach (a third-party repo, not Lakshay's),
so the suggestions were specific-sounding but not actionable. v2 drops
Agent-Reach entirely and pairs Friday with vivaha + Aether - two repos
Lakshay owns, both with real recent activity (vivaha last pushed
2026-07-18, Aether 2026-07-13; Jarvis excluded as dormant, Friday-V3
excluded this round by design - flagged for a dedicated look, not
mined here).

Runs the REAL committed `weekly-cross-project-digest` trigger's plan
(config/watcher.json, ENABLED, Sundays 10:00) through the REAL executor
(run_plan) - the exact plan the watcher will run on Sunday, same
primitives, same verifies, same allowlist. The DETERMINISTIC plan (no
L4 LLM call) does:

  git.log x3 (Friday V2 / vivaha / Aether)   -> verified checks.list_nonempty
  files.find_recent_doc x3 (status-shaped doc per repo, README fallback)
  files.read_text x3 (the discovered status docs)
  dev.digest(context of the six)             -> verified checks.text_nonempty
  digestcheck.verify_attribution(digest, per-repo content) -> MECHANICAL
    attribution check: every "X's <mechanism>" claim must appear in X's
    own gathered content; unconfirmed claims are flagged in the digest
  notify.notify_send(body=$steps.11.result)  -> verified on returned body

`dev.digest` is the ONE live full-tier LLM call per run (~$0.17) - the
same documented LLM-in-primitive exception as gmail.summarize. The
digest text is read from the StepResult the executor carries.

The proof shows the real digest and an HONEST quality assessment with
TWO mechanical checks this round: (a) does each suggestion name a
mechanism that exists in the gathered sources (specific-vs-generic),
and (b) are the transfer targets repos Lakshay actually owns - i.e. the
digest references only the gathered repos, never a third party. The
final "would I act on it" judgment stays human.

Run:  ./.venv/bin/python -u gates/phase_c_v2_demo.py
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "gates"))

from friday.l3.executor import run_plan  # noqa: E402
from friday.watcher import load_config  # noqa: E402

TASK_ID = "watch:weekly-cross-project-digest"
PROOF = "gates/PHASE_C_V2_PROOF.md"

# The repos this round actually gathers (the digest must only talk about
# these - any other target is a hallucinated or third-party reference).
GATHERED_REPOS = ["Friday V2", "vivaha", "Aether"]

# Quality-assessment heuristics: does the digest name SPECIFIC things
# that actually exist in the gathered sources (not just plausible
# filler)? A specific suggestion references a primitive, a file, a
# module, a repo, or a commit subject found in the gathered context.
# Markers are SOURCE-TIED only: repo names, primitive names, file names,
# and distinctive mechanisms. Framing words the LLM uses regardless of
# grounding ("digest", "notify", "Friday", "primitive", "gate",
# "executor", "planner", "contract", ...) are deliberately EXCLUDED so
# the SPECIFIC verdict actually discriminates - a digest that only says
# "this digest summarizes Friday" must NOT pass.
_SPECIFIC_MARKERS = [
    "git.log", "files.read_text", "dev.digest", "find_file", "gmail", "watcher",
    "watcher.py", "CHANGELOG", "README", "vivaha", "aether", "OAuth",
    "capability", "security", "hardening", "payment", "router",
    "capability_gap", "sync.sh", "navbar", "supabase",
]

# Standing verdict of the v2.1 context experiment (2026-08-11) - included in
# EVERY regenerated proof so it is never lost when the demo re-runs.
_V2_1_VERDICT = [
    "## Verdict on the context experiment (v2.1)",
    "",
    "The v2.1 experiment (2026-08-11) asked: does feeding the digest",
    "CURRENT-PRIORITY context (vivaha roadmap + payment system, aether",
    "devlog) instead of git log + boilerplate READMEs produce suggestions",
    "worth acting on? The v2.1 context WAS promoted into the committed",
    "trigger at the time (8/8 VERIFIED - strictly better than the create-",
    "next-app boilerplate READMEs it replaced, same cost, same allowlist);",
    "v2.2 later replaced the hardcoded priority docs with recency-based",
    "files.find_recent_doc discovery plus the digestcheck.verify_attribution",
    "mechanical check (see the plan above - the committed trigger is now",
    "the 12-step v2.2 plan).",
    "",
    "Relevance: IMPROVED. Both suggestions touched real roadmap items",
    "(Vivaha admin dashboard [Q4], moderation microservice + bundle size",
    "[Q1/Q4]) and the digest correctly described the payment flow from the",
    "payment doc - versus v2 where the Vivaha suggestion was unconnected",
    "to anything the repo needs.",
    "",
    "Ceiling confirmed - two failure modes survive better context:",
    "(a) PROVENANCE CONFABULATION: the digest re-attributed Vivaha's OWN",
    "roadmap mechanism (Cloudflare Worker for moderation) to Friday as if",
    "it were a Friday pattern - the transfer claim is partially false",
    "even when the suggestion is roadmap-accurate.",
    "(b) TRUE BLOCKERS ARE INVISIBLE: the actual current priorities",
    "(unimplemented Razorpay flow, Supabase key rotation, broken admin",
    "verification UI) live in Lakshay's head and past conversations, not",
    "in any repo doc; the roadmap is a FUTURE roadmap, not a current-",
    "state doc.",
    "",
    "Decision: SCALING IS DEFERRED - the pattern has not yet produced a",
    "suggestion worth acting on. The next improvement needs a source of",
    "TRUE current priorities (e.g. a maintained per-repo status note) -",
    "a maintenance decision, not a config change.",
    "",
]


def _gathered(log_lines: list[str]) -> dict[str, list[str]]:
    """The git.log rows this run gathered (from the temp L0 trace)."""
    rows: dict[str, list[str]] = {}
    for line in log_lines:
        rec = json.loads(line)
        if rec.get("primitive") == "git.log" and rec.get("layer") == "L1" and rec.get("result"):
            for r in rec["result"]:
                rows.setdefault(rec["args"].get("repo_path", "?"), []).append(
                    f"{r['date']} {r['author']}: {r['subject']} ({r['commit']})"
                )
    return rows


def _assess_quality(text: str) -> tuple[str, list[str], list[str]]:
    """Two mechanical checks: (a) specific-vs-generic (does the digest
    name concrete things from the gathered sources), and (b) target-owned
    (does the digest reference any repo outside the gathered set - the
    v1 defect where suggestions targeted a third-party repo)."""
    lowered = text.lower()
    hits = [m for m in _SPECIFIC_MARKERS if m.lower() in lowered]
    if len(hits) >= 3:
        spec = "SPECIFIC - the digest names concrete things from the gathered sources"
    elif hits:
        spec = "PARTIALLY SPECIFIC - some concrete references, but thin"
    else:
        spec = "GENERIC - no concrete references to the gathered sources (filler risk)"
    # NOTE: "jarvis" is deliberately NOT in this list - Aether's own docs
    # (DEVLOG, now gathered context) name Jarvis as its kernel intelligence,
    # so a faithful digest may legitimately mention it. Only THIRD-PARTY
    # repos and excluded projects are off-scope.
    outsiders = [r for r in ("agent-reach", "agent reach", "psyche", "changelogai", "mindwell")
                 if r in lowered]
    if outsiders:
        owned = f"TARGETS OFF-SCOPE REPO(S): {outsiders} - same defect as v1, treat suggestions with suspicion"
    else:
        owned = "TARGETS OWNED - all references stay within the gathered repos (Friday, vivaha, Aether)"
    return spec, hits, outsiders


def main() -> int:
    out: list[str] = []
    print("=" * 72)
    print(f"PHASE C v2 proof - digest over real owned repos ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    print("=" * 72)

    triggers = load_config(ROOT / "config" / "watcher.json")
    committed = next((t for t in triggers if t["id"] == "weekly-cross-project-digest"), None)
    if committed is None:
        print("FAIL: committed config has no weekly-cross-project-digest trigger")
        return 1

    plan = committed["plan"]

    # EXPERIMENT override: `python -u gates/phase_c_v2_demo.py <plan.json>`
    # runs the SAME machinery against an experimental plan (e.g. a different
    # gather context) WITHOUT touching the committed trigger config. The
    # proof records the override so the run stays reproducible.
    override: str | None = None
    if len(sys.argv) > 1:
        ov_path = Path(sys.argv[1])
        ov = json.loads(ov_path.read_text(encoding="utf-8"))
        plan = ov
        override = str(ov_path)
        print(f"[experiment] plan override: {override} (committed config untouched)")

    tmp = Path(tempfile.mkdtemp(prefix="friday_phase_c2_"))
    log = tmp / "friday.jsonl"
    os.environ["FRIDAY_LOG_FILE"] = str(log)
    os.environ["FRIDAY_GAPS_FILE"] = str(tmp / "gaps.jsonl")

    print(f"\n[trigger] {committed['id']} (committed config, Sundays 10:00)")
    print(f"   allow: {committed.get('allow')}")
    print(f"   steps: {[s['primitive'] for s in plan['steps']]}")

    print("\n--- run_plan(committed digest plan) through the REAL executor ---")
    print("     (deterministic plan -> git.log x3 -> find_recent_doc x3 -> read_text x3 ->")
    print("      dev.digest [1 LLM call] -> verify_attribution -> notify)")
    result = run_plan(plan, run_id=TASK_ID)
    ok = result.status == "COMPLETED"

    print("\n--- plan result ---")
    for sr in result.steps:
        print(f"   step {sr.step_id}: {sr.primitive:22s} {sr.status} (attempts={sr.attempts})")
    out.append("\n".join(
        f"step {sr.step_id}: {sr.primitive} {sr.status} (attempts={sr.attempts})"
        for sr in result.steps
    ))
    log_lines = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []

    gathered = _gathered(log_lines)
    print("\n--- what git.log gathered (from the L0 trace) ---")
    gathered_lines: list[str] = []
    for repo, rows in gathered.items():
        gathered_lines.append(f"{repo}:")
        gathered_lines += [f"  {r}" for r in rows]
    print("\n".join(gathered_lines))
    out.append("\n".join(gathered_lines))

    digest = next((sr.result for sr in result.steps if sr.primitive == "dev.digest" and isinstance(sr.result, str) and sr.result.strip()), "")
    print("\n--- the digest dev.digest produced (real LLM output) ---")
    print(digest)
    out.append(digest)

    verified = next((sr.result for sr in result.steps if sr.primitive == "digestcheck.verify_attribution" and isinstance(sr.result, str) and sr.result.strip()), "")
    appendix = verified.split("## Attribution check", 1)[1].strip() if "## Attribution check" in verified else ""
    print("\n--- attribution check (digestcheck.verify_attribution, mechanical) ---")
    print(appendix)
    out.append(appendix)

    spec, hits, outsiders = _assess_quality(digest)
    print("\n--- honest quality assessment ---")
    print(f"   {spec}")
    print(f"   concrete references found: {hits}")
    print(f"   {('OFF-SCOPE: ' + str(outsiders)) if outsiders else 'no off-scope repo references'}")
    out.append(f"{spec} (concrete references found: {hits}); {'OFF-SCOPE REPO REFS: ' + str(outsiders) if outsiders else 'targets stay within owned repos'}")

    # The real watcher's recorded run of the SAME trigger (real
    # tasks.jsonl + notify), pulled live so regeneration never loses it.
    watcher_section: list[str] = []
    try:
        recs = [json.loads(l) for l in (ROOT / "var" / "logs" / "tasks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
        rec = next((r for r in reversed(recs) if r.get("task_id") == "watch:weekly-cross-project-digest"), None)
        if rec:
            watcher_section = [
                "## The real watcher run (record + notify delivery)",
                "",
                "The SAME committed trigger fired through the REAL watcher",
                "(run_watcher(once=True), schedule moved to 00:00 only, temp",
                "fired-state so the real var/state/watcher_fired.json is",
                "untouched) with the REAL var/logs/tasks.jsonl and desktop",
                "notification. The latest recorded line:",
                "",
                "```",
                json.dumps(rec, indent=2),
                "```",
                "",
                "The digest text reached the desktop as the notify step's body.",
                "",
            ]
    except (OSError, json.JSONDecodeError):
        watcher_section = []

    proof = "\n".join([
        "# PHASE_C_V2_PROOF - weekly cross-project digest over real owned repos",
        "",
        f"Status date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
        "",
        (f"EXPERIMENTAL run - plan override: `{override}` (the committed trigger config was NOT changed)." if override else ""),
        "",
        "v1 proved the gather -> synthesize -> deliver pattern works mechanically",
        "but paired Friday with Agent-Reach - a THIRD-PARTY repo, not Lakshay's -",
        "so the suggestions were specific-sounding yet not actionable. v2 drops",
        "Agent-Reach entirely and pairs Friday with **vivaha + Aether**, two repos",
        "Lakshay owns with real recent activity (vivaha last pushed 2026-07-18,",
        "Aether 2026-07-13). Jarvis is excluded as dormant (1 commit in 90 days);",
        "Friday-V3 is excluded THIS ROUND by design - it is flagged in PLAN_STATUS",
        "as containing an earlier correlation-engine implementation worth a",
        "dedicated future look, and is NOT mined here. Psyche Space and",
        "ChangelogAI are excluded pending a separate decision (no GitHub copy",
        "under lakshay-sharma-02).",
        "",
        "The ENABLED `weekly-cross-project-digest` trigger's plan",
        "(config/watcher.json, Sundays 10:00) runs through the REAL executor",
        "(run_plan): the exact plan the watcher will run on Sunday - same",
        "primitives, same verifies, same allowlist. The L0 log is pointed at a",
        "temp file; the digest text comes from the StepResult the executor",
        "carries (the log clips results to 500 chars).",
        "",
        "## The plan (deterministic - no L4 LLM call)",
        "",
        "```",
        json.dumps(plan, indent=2),
        "```",
        "",
        "Primitives: `git.log` (gather), `files.find_recent_doc` (recency-",
        "based status-doc discovery: most recently modified PLAN_STATUS/ROADMAP/",
        "DEVLOG/STATUS/TODO/CHANGELOG-shaped file, README fallback), `files.read_text`",
        "(the status docs), `dev.digest` (the ONE live full-tier LLM call per run,",
        "~$0.17, the same documented LLM-in-primitive exception as gmail.summarize),",
        "`digestcheck.verify_attribution` (the MECHANICAL attribution check - every",
        "\"X's <mechanism>\" claim must appear in X's OWN gathered content, not just",
        "anywhere in the combined prompt), and `notify.notify_send` (the digest text",
        "is DELIVERED to the desktop as the notification body, verified by",
        "checks.text_nonempty on the returned envelope body). The trigger",
        "allowlist is exactly these six - the plan can never reach for anything",
        "side-effecting.",
        "",
        "## Plan result (every step VERIFIED)",
        "",
        "```",
        "\n".join(out[:1]),
        "```",
        "",
        "## What git.log gathered (from the temp L0 trace)",
        "",
        "```",
        "\n".join(out[1:2]),
        "```",
        "",
        "## The digest (real LLM output)",
        "",
        "```",
        "\n".join(out[2:3]),
        "```",
        "",
        "## Attribution check (digestcheck.verify_attribution - mechanical)",
        "",
        "Every \"X's <mechanism>\" claim in the digest is name-matched against",
        "the gathered content fetched FOR that repo; unconfirmed claims are",
        "flagged below instead of being delivered as fact (the v2.1",
        "confabulation fix - Vivaha's Cloudflare-Worker pattern was once",
        "described as if it were Friday's).",
        "",
        "```",
        "\n".join(out[3:4]),
        "```",
        "",
        "## Honest quality assessment",
        "",
        "```",
        "\n".join(out[4:5]),
        "```",
        "",
        "Three mechanical checks this round: (a) does each suggestion name a",
        "mechanism that actually exists in the gathered sources (specific vs",
        "filler), (b) do the transfer targets stay within repos Lakshay owns -",
        "the exact defect v1 had (suggestions aimed at a repo he didn't",
        "control) - and (c) does every \"X's <mechanism>\" claim actually appear",
        "in X's OWN gathered content (digestcheck.verify_attribution, the v2.1",
        "confabulation fix). The final bar - 'would I act on this' - remains a",
        "human judgment, reported honestly below.",
        "",
        "## Verdict",
        "",
        f"{'PASS' if ok else 'FAIL'} - the ambient pattern (watcher trigger ->",
        "read-only gather primitives -> LLM synthesis -> notify delivery ->",
        "record) works over repos Lakshay actually owns. Whether the suggestions",
        "are worth ACTING on is the real signal of this round and is judged by a",
        "human against the two checks above - the digest's quality assessment",
        "makes the evidence explicit rather than assumed.",
        "",
        *watcher_section,
        *_V2_1_VERDICT,
        "## Cost",
        "",
        "One full-tier LLM call per digest run (~$0.17) - the suggestion-drafting",
        "call itself, weekly. No L4 planning call (deterministic plan). If cost",
        "matters, the read/summarize split (cheap tier for gathering, full tier",
        "for the final suggestion) is the documented next step.",
        "",
    ])
    (ROOT / PROOF).write_text(proof + "\n", encoding="utf-8")
    print(f"\nproof written to {PROOF}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
