#!/usr/bin/env python
"""Gate 3 - L2 verification proof.

DoD (from the master plan): change real state by hand between calls - open
an app, then check the count went up; close it, count returns down. Shown,
not assumed. Also enforces the L2 import discipline: verification modules
may import only read-only (idempotent) primitive accessors.

Run:  ./.venv/bin/python gates/gate3_proof.py
"""

from __future__ import annotations

import ast
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.contracts import REGISTRY  # noqa: E402
from friday.l1 import window  # noqa: E402
import friday.l2.checks as checks  # noqa: E402

MUTATOR_NAMES = {
    k.split(".")[-1] for k, c in REGISTRY.items() if c.idempotency.value != "idempotent"
}


def discipline_check() -> list[str]:
    """Every primitive referenced by an L2 module must be idempotent
    (read-only). Two independent checks, both must pass:

    1. Runtime: walk the checks module's namespace - any contract-registered
       callable that landed there via import must be idempotent.
    2. Static: parse L2 source with AST and collect every imported name and
       attribute access; none may resolve to a registered mutator name.
    """
    violations: list[str] = []

    # (1) Runtime namespace walk - catches `from x import mutator`.
    for mod in (checks,):
        for name, obj in vars(mod).items():
            contract = getattr(obj, "__contract__", None)
            if contract is None:
                continue
            if contract.idempotency.value != "idempotent":
                violations.append(f"{mod.__name__}.{name} -> {contract.name} ({contract.idempotency.value})")

    # (2) Static AST analysis - catches `import x` then `x.mutator()` too.
    for l2_file in (ROOT / "friday" / "l2").glob("*.py"):
        if l2_file.name.startswith("__"):
            continue
        try:
            tree = ast.parse(l2_file.read_text())
        except SyntaxError as exc:
            violations.append(f"{l2_file.name}: parse error {exc}")
            continue
        referenced: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Attribute):
                referenced.add(node.attr)
            elif isinstance(node, ast.ImportFrom):
                for alias in node.names:
                    referenced.add(alias.asname or alias.name)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    referenced.add((alias.asname or alias.name).split(".")[-1])
        for bad in sorted(referenced & MUTATOR_NAMES):
            violations.append(f"{l2_file.name} references mutator '{bad}'")
    return violations


def main() -> None:
    print("=" * 72)
    print("GATE 3 / L2 VERIFICATION")
    print("=" * 72)

    print("\n[1] import discipline (L2 imports read-only accessors only)")
    violations = discipline_check()
    for v in violations:
        print(f"  VIOLATION: {v}")
    print(f"  violations: {len(violations)}")
    print(f"  DISCIPLINE: {'OK' if not violations else 'FAILED'}")

    print("\n[2] window: open_app -> count goes UP -> close -> count returns DOWN")
    before = checks.window_client_count()
    print(f"  count before: {before}")
    print(f"  window_has_class('firefox') before: {checks.window_has_class('firefox')}")
    win = window.open_app("firefox")
    print(f"  opened: {win['address']} (class={win.get('class')})")
    mid = checks.window_client_count()
    has_after_open = checks.window_has_class("firefox")
    print(f"  count after open: {mid}  (delta +{mid - before})")
    print(f"  window_has_class('firefox') after open: {has_after_open}")
    window.close_window(win["address"])
    after = checks.window_client_count()
    has_after_close = checks.window_has_class("firefox")
    print(f"  count after close: {after}  (delta {after - before})")
    print(f"  window_has_class('firefox') after close: {has_after_close}")
    ok_window = mid > before and has_after_open and after < mid and not has_after_close
    print(f"  WINDOW CHECK: {'PASS' if ok_window else 'FAILED'}")

    print("\n[3] media: play_for(1) -> media_playing True -> stop -> False")
    from friday.l1 import media

    tone = ROOT / "assets" / "test_tone.mp3"
    media.play_for(1, str(tone))
    playing = False
    for _ in range(10):
        playing = checks.media_playing()
        if playing:
            break
        time.sleep(0.5)
    print(f"  media_playing() after start: {playing}")
    media.stop()
    time.sleep(0.3)
    stopped = checks.media_playing()
    print(f"  media_playing() after stop: {stopped}")
    ok_media = playing and not stopped
    print(f"  MEDIA CHECK: {'PASS' if ok_media else 'FAILED'}")

    print("\n[4] browser: goto -> browser_has_text True -> close -> False")
    from friday.l1 import browser

    browser.goto("https://example.com")
    has = checks.browser_has_text("Example Domain")
    print(f"  browser_has_text('Example Domain') after goto: {has}")
    browser.close()
    has_after = checks.browser_has_text("Example Domain")
    print(f"  browser_has_text('Example Domain') after close: {has_after}")
    ok_browser = has and not has_after
    print(f"  BROWSER CHECK: {'PASS' if ok_browser else 'FAILED'}")

    print("\n[5] file check (pure, no side effects)")
    print(f"  file_exists(README): {checks.file_exists(str(ROOT / 'README.md'))}")
    print(f"  file_exists(/nonexistent): {checks.file_exists('/nonexistent/nope')}")

    print("\n[6] whatsapp identity (read-only API check)")
    try:
        ident = checks.whatsapp_identity_ok()
        print(f"  whatsapp_identity_ok: {ident}")
    except Exception as exc:  # noqa: BLE001 - creds may be absent on a fresh box
        print(f"  whatsapp_identity_ok: error -> {type(exc).__name__}")

    print("\n=== raw L2 log lines (layer=L2) from this run ===")
    log = ROOT / "var" / "logs" / "friday.jsonl"
    if log.exists():
        for line in log.read_text().splitlines():
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("layer") == "L2":
                print(json.dumps(rec))

    all_ok = not violations and ok_window and ok_media and ok_browser
    print(f"\nGATE 3: {'DONE' if all_ok else 'FAILED'}")
    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
