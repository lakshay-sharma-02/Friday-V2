#!/usr/bin/env python
"""Gate 2 - L0 observability proof.

DoD: rerun a Gate-1-grade call per primitive; the log file must now contain
one structured JSON line per call with
    {run_id, primitive, args, result_or_exception, duration_ms}
validated here programmatically - not by eyeballing.

Run:  ./.venv/bin/python gates/gate2_proof.py
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.l1 import browser, dev, media, whatsapp, window  # noqa: E402

LOG = ROOT / "var" / "logs" / "friday.jsonl"
LOG.parent.mkdir(parents=True, exist_ok=True)
if LOG.exists():
    LOG.unlink()

REQUIRED = {"run_id", "primitive", "args", "result", "exception", "duration_ms"}


def check(
    label: str, expected: int, run: "Callable[[], None]"
) -> int:
    """Run a set of primitive calls; return how many log lines they add."""
    before = _count_lines()
    print(f"--- {label} ---")
    run()
    added = _count_lines() - before
    status = "OK" if added == expected else f"FAILED (expected {expected}, saw {added})"
    print(f"  {status}")
    return added


def _count_lines() -> int:
    if not LOG.exists():
        return 0
    return len(LOG.read_text().splitlines())


def main() -> None:
    total = 0

    def w() -> None:
        nonlocal total
        clients = window.list_clients()
        print(f"  window.list_clients() -> {len(clients)} clients")
        total += 1

    total += check("window: list_clients (read-only)", 1, w)

    def m() -> None:
        nonlocal total
        playing = media.is_playing()
        print(f"  media.is_playing() -> {playing}")
        total += 1

    total += check("media: is_playing (no player -> False, read-only)", 1, m)

    def b() -> None:
        nonlocal total
        browser.goto("https://example.com")
        total += 1
        text = browser.read_page_text()
        print(f"  browser.read_page_text() -> {text[:40]!r}...")
        total += 1
        browser.close()
        total += 1

    total += check("browser: goto + read_page_text + close", 3, b)

    def d() -> None:
        nonlocal total
        r = dev.run_shell(str(ROOT), "echo ok", allow_bypass_permissions=True)
        print(f"  dev.run_shell -> exit_code={r.get('exit_code')} stdout={r.get('stdout')!r}")
        total += 1

    total += check("dev: run_shell('echo ok')", 1, d)

    def e() -> None:
        nonlocal total
        try:
            # No credentials configured -> must raise PrimitiveError, and the
            # exception (not a result) must be what lands in the log line.
            whatsapp.send_text(text="probe", to="918396020807")
            print("  whatsapp.send_text -> UNEXPECTED success (creds configured?)")
        except Exception as exc:  # noqa: BLE001 - expected
            print(f"  whatsapp.send_text -> raised {type(exc).__name__} (expected, no creds)")
        finally:
            total += 1

    total += check("whatsapp: exception path (no creds -> PrimitiveError)", 1, e)

    # ---- validation: every line is one structured JSON record ----
    lines = LOG.read_text().splitlines()
    print(f"\n=== raw log file: {LOG} ({len(lines)} lines) ===")
    problems: list[str] = []
    for i, line in enumerate(lines, 1):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            problems.append(f"line {i}: not JSON: {exc}")
            continue
        missing = REQUIRED - set(rec)
        if missing:
            problems.append(f"line {i}: missing {sorted(missing)}")
        # Semantics: a failure line carries a non-null exception (and null
        # result); a success line has exception null - its result may
        # legitimately be null too (e.g. close() returns None).
        if rec.get("exception") is not None and rec.get("result") is not None:
            problems.append(f"line {i}: both result and exception present")
        if not rec.get("run_id") or not rec.get("primitive"):
            problems.append(f"line {i}: empty run_id or primitive")
        if not isinstance(rec.get("duration_ms"), (int, float)):
            problems.append(f"line {i}: duration_ms missing/not numeric")
        print(line)

    # Defensive: skip malformed lines rather than crashing the validator.
    run_ids: set[str] = set()
    for l in lines:
        try:
            rid = json.loads(l).get("run_id")
            if rid:
                run_ids.add(rid)
        except json.JSONDecodeError:
            continue
    print(f"\nrun_id consistency: {len(run_ids)} run id(s) for this process (expect 1)")

    ok = not problems and len(lines) == total and len(run_ids) == 1
    if problems:
        for p in problems:
            print(f"  PROBLEM: {p}")
    print(f"\nGATE 2: {'DONE' if ok else 'FAILED'}  ({len(lines)} lines for {total} expected calls)")


if __name__ == "__main__":
    main()
