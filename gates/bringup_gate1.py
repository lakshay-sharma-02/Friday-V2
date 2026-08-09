#!/usr/bin/env python
"""Gate 1 - L1 primitive bring-up.

Each Definition-of-Done line prints RAW evidence (actual stdout / returned
values), not "it worked". This is the contract of the whole plan: no layer
is "probably fine".

Run:  ./.venv/bin/python gates/bringup_gate1.py all
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.contracts import REGISTRY  # noqa: E402
import friday.l1.window as window  # noqa: E402
import friday.l1.media as media  # noqa: E402
import friday.l1.browser as browser  # noqa: E402
import friday.l1.dev as dev  # noqa: E402

ASSETS = ROOT / "assets"
TEST_TONE = ASSETS / "test_tone.mp3"


def _sh(*args: str) -> str:
    return subprocess.run(list(args), capture_output=True, text=True).stdout.strip()


def print_contracts(module_prefix: str) -> None:
    for name, c in sorted(REGISTRY.items()):
        if name.startswith(module_prefix):
            print(f"  {name:<22} idempotency={c.idempotency.value}")
            print(f"      pre : {c.precondition}")
            print(f"      post: {c.postcondition}")
            print(f"      fail: {c.failure_mode}")


def cmd_window() -> None:
    print("=" * 72)
    print("GATE 1 / PRIMITIVE 1: window (hyprctl IPC)")
    print("=" * 72)
    print("-- contracts --")
    print_contracts("")
    print("\n[1a] baseline: window.list_clients()")
    before = window.list_clients()
    print(f"  client count before: {len(before)}")
    print("\n[1b] window.open_app('firefox')")
    win = window.open_app("firefox")
    print(f"  open_app returned client: {json.dumps(win)}")
    print("\n[1c] raw proof: hyprctl clients -j (firefox entry)")
    raw = _sh("hyprctl", "clients", "-j")
    clients = json.loads(raw)
    fx = [
        c
        for c in clients
        if "firefox" in str(c.get("class", "")).lower()
        or "firefox" in str(c.get("title", "")).lower()
    ]
    print(json.dumps(fx, indent=2))
    print(f"  client count after: {len(clients)} (delta +{len(clients) - len(before)})")
    print("\n[1d] close it again (leave the desktop tidy)")
    window.close_window(win["address"])
    after = len(window.list_clients())
    print(f"  count after close: {after}")
    ok = len(fx) >= 1 and after <= len(before) + 1
    print(f"  WINDOW: {'DONE' if ok else 'FAILED'}")


def cmd_media() -> None:
    print("=" * 72)
    print("GATE 1 / PRIMITIVE 2: media (mpv IPC socket)")
    print("=" * 72)
    print(f"  test asset: {TEST_TONE} ({TEST_TONE.stat().st_size} bytes)")
    print("\n[2a] media.play_for(1, test_tone.mp3)  -> 1 minute")
    r = media.play_for(1, str(TEST_TONE))
    print(f"  play_for -> {json.dumps(r)}")
    print(f"  raw: socket exists -> {os.path.exists(media.SOCKET_PATH)}")
    mpv_before = _sh("pgrep", "-af", "mpv")
    print(f"  raw: pgrep mpv -> {mpv_before or '(none)'}")
    print("\n[2b] media.is_playing() right after start (expect True)")
    playing = False
    for _ in range(10):  # mpv needs a beat to start demux/ao
        playing = media.is_playing()
        if playing:
            break
        time.sleep(0.5)
    print(f"  is_playing -> {playing}")
    if not playing:
        print("  MEDIA: FAILED (never started playing)")
        return
    print("\n  ... sampling playback for 70s (mpv --length=60 must stop it) ...")
    saw_playing = playing
    for tick in range(1, 15):
        time.sleep(5)
        value = media.is_playing()
        saw_playing = saw_playing or value
        print(f"    t+{tick * 5:>3}s is_playing -> {value}")
    print("\n[2c] final: media.is_playing() (expect False)")
    final = media.is_playing()
    print(f"  is_playing -> {final}")
    mpv_after = _sh("pgrep", "-af", "mpv")
    print(f"  raw: pgrep mpv after -> {mpv_after or '(none)'}")
    ok = saw_playing and not final
    print(f"  MEDIA: {'DONE' if ok else 'FAILED (True->False curve not verified)'}")


def cmd_browser() -> None:
    print("=" * 72)
    print("GATE 1 / PRIMITIVE 3: browser (Playwright persistent context)")
    print("=" * 72)
    print(f"  profile: {browser.PROFILE_DIR}")
    print("\n[3a] browser.goto('https://example.com')")
    nav = browser.goto("https://example.com")
    print(f"  goto -> {json.dumps(nav)}")
    print("\n[3b] browser.read_page_text()  (raw, first 400 chars)")
    text = browser.read_page_text()
    print("  " + text[:400].replace("\n", " | "))
    ok = "Example Domain" in text
    print(f"  BROWSER: {'DONE' if ok else 'FAILED'}")
    browser.close()


def cmd_dev() -> None:
    print("=" * 72)
    print("GATE 1 / PRIMITIVE 4: dev (claude -p subprocess)")
    print("=" * 72)
    print("\n[4a] dev.run_shell(<project root>, 'echo ok', allow_bypass_permissions=True)")
    r = dev.run_shell(str(ROOT), "echo ok", allow_bypass_permissions=True)
    print(f"  run_shell -> {json.dumps(r, indent=2)}")
    ok = r.get("exit_code") == 0 and r.get("stdout", "").strip() == "ok"
    print(f"  DEV: {'DONE' if ok else 'FAILED'}")


def cmd_all() -> None:
    for fn in (cmd_window, cmd_media, cmd_browser, cmd_dev):
        fn()
        print()


def main() -> None:
    ap = argparse.ArgumentParser(description="Gate 1 bring-up")
    ap.add_argument(
        "step", nargs="?", default="all", choices=["window", "media", "browser", "dev", "all"]
    )
    args = ap.parse_args()
    {
        "window": cmd_window,
        "media": cmd_media,
        "browser": cmd_browser,
        "dev": cmd_dev,
        "all": cmd_all,
    }[args.step]()


if __name__ == "__main__":
    main()
