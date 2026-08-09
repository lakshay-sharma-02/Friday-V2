#!/usr/bin/env python
"""Bring-up for the LAST unproven L1 primitives (V8 plan, Section 1).

Proves, standalone (hand-invoked, no executor, no LLM):

  A. media.pause / media.resume     (audio only - zero window interaction)
  B. browser.upload_file            (throwaway local page + test file)
  C. window.focus_window,
     window.move_to_workspace,
     window.close_all               (ONLY against a test window opened by
                                     this script; the user's real windows are
                                     the protected control group)

SAFETY (non-negotiable, this run is unattended):
  - The user's currently-open windows are snapshotted first and treated as
    untouchable. close_all runs with EVERY pre-existing class excluded, so
    the only client it can close is the test window opened in step C.
  - window.shutdown is NEVER called (destructive - ends the session).
  - Focus is restored to the originally-active window at the end.
  - Cleanup runs in a finally block: kill the throwaway HTTP server, close
    the Playwright browser, close any test window still open, refocus the
    original window.

DoD (honest, read from raw state + the L0 trace for this run_id):
  A: play -> is_playing True -> pause -> False -> resume -> True -> stop -> False
  B: upload_file returns input_count >= 1 and the page reports the
     uploaded filename (via its JS change handler) - read_page_text is the
     state proof, browser_has_text is the L2 check.
  C: focus verified by get_active_window().address; move verified by the
     client's workspace.id in list_clients; close_all closes ONLY the test
     window (every pre-existing client survives - proven by address set).

Run:  ./.venv/bin/python -u gates/bringup_remaining.py [run_label]
"""

from __future__ import annotations

import json
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.l1 import browser, media, window  # noqa: E402
from friday.l2 import checks  # noqa: E402
from friday.observability import set_run_id  # noqa: E402

RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "bringup-remaining"

TEST_TONE = ROOT / "assets" / "test_tone.mp3"
SCRATCH = ROOT / "var" / "logs" / "upload_tmp"
TEST_FILE = SCRATCH / "friday_upload_test.txt"
UPLOAD_PAGE = """<!doctype html><html><head><meta charset="utf-8"></head><body>
<h1>friday upload test</h1>
<input type="file" id="f" />
<div id="status">no file</div>
<script>
document.getElementById('f').addEventListener('change', function(e){
  var f = e.target.files[0];
  document.getElementById('status').textContent = f ? 'selected: ' + f.name : 'no file';
});
</script>
</body></html>"""

# ------------------------------------------------------------------ helpers


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def _client_by_address(address: str) -> dict[str, Any] | None:
    for c in window.list_clients():
        if str(c.get("address")) == address:
            return c
    return None


def _active_address() -> str | None:
    aw = window.get_active_window()
    return str(aw.get("address")) if aw else None


def _dump(run_id: str, label: str) -> None:
    log = ROOT / "var" / "logs" / "friday.jsonl"
    lines = [
        json.loads(l) for l in log.read_text().splitlines()
        if json.loads(l).get("run_id") == run_id
    ]
    print(f"\n=== L0 trace: {label} ({len(lines)} lines, run_id={run_id}) ===")
    for rec in lines:
        outcome = rec["result"] if rec["result"] is not None else "None"
        if rec["exception"] is not None:
            outcome = f"{outcome} EXC: {rec['exception']}"
        print(
            f"[{rec['timestamp']}] {rec['layer']} step={rec['step_id']} {rec['primitive']:28s} "
            f"-> {str(outcome)[:90]}"
        )


# ---------------------------------------------------------------- section A


def section_media() -> list[str]:
    print("\n" + "=" * 72)
    print("SECTION A - media.pause / media.resume (audio only)")
    print("=" * 72)
    problems: list[str] = []

    print(f"\n[a1] media.play_for(0.1, test_tone) -> {media.play_for(0.1, str(TEST_TONE), volume=30)}")
    time.sleep(0.5)
    print(f"[a2] media.is_playing() -> {media.is_playing()}  (expect True)")
    if not media.is_playing():
        problems.append("a2: media not playing after play_for")

    print(f"[a3] media.pause() -> {media.pause()}")
    time.sleep(0.5)
    print(f"[a4] media.is_playing() -> {media.is_playing()}  (expect False - paused)")
    if media.is_playing():
        problems.append("a4: is_playing True while paused")

    print(f"[a5] media.resume() -> {media.resume()}")
    time.sleep(0.5)
    print(f"[a6] media.is_playing() -> {media.is_playing()}  (expect True - resumed)")
    if not media.is_playing():
        problems.append("a6: media not playing after resume")

    print(f"[a7] media.stop() -> {media.stop()}")
    time.sleep(0.5)
    print(f"[a8] media.is_playing() -> {media.is_playing()}  (expect False - stopped)")
    if media.is_playing():
        problems.append("a8: media still playing after stop")

    print("\n--- SECTION A DoD ---")
    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
    else:
        print("  OK: play -> True; pause -> False; resume -> True; stop -> False")
    return problems


# ---------------------------------------------------------------- section B


def section_upload() -> list[str]:
    print("\n" + "=" * 72)
    print("SECTION B - browser.upload_file (throwaway local page)")
    print("=" * 72)
    problems: list[str] = []

    tmp = SCRATCH
    tmp.mkdir(parents=True, exist_ok=True)
    (tmp / "index.html").write_text(UPLOAD_PAGE)
    TEST_FILE.write_text("friday upload_file bring-up payload\n")

    port = _free_port()
    server = subprocess.Popen(
        ["python3", "-m", "http.server", str(port), "--bind", "127.0.0.1", "--directory", str(tmp)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    url = f"http://127.0.0.1:{port}/index.html"
    try:
        time.sleep(1.0)  # let the server come up
        print(f"\n[b1] browser.goto({url}) -> {browser.goto(url)}")
        print(f"[b2] browser.upload_file(what=None, path={TEST_FILE.name}) -> "
              f"{browser.upload_file(None, str(TEST_FILE))}")
        time.sleep(0.5)
        page_text = browser.read_page_text()
        print("[b3] page text after upload:")
        for line in page_text.splitlines()[:6]:
            print(f"     | {line}")
        if TEST_FILE.name not in page_text:
            problems.append(f"b3: page does not report uploaded file {TEST_FILE.name!r}")
        print(f"[b4] checks.browser_has_text('selected: {TEST_FILE.name}') "
              f"-> {checks.browser_has_text(f'selected: {TEST_FILE.name}')}  (expect True)")
        if not checks.browser_has_text(f"selected: {TEST_FILE.name}"):
            problems.append("b4: L2 check failed - upload not reflected in page state")
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()

    print("\n--- SECTION B DoD ---")
    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
    else:
        print("  OK: upload_file attached the file and the page state shows it (L2-confirmed)")
    return problems


# ---------------------------------------------------------------- section C


def section_window() -> list[str]:
    print("\n" + "=" * 72)
    print("SECTION C - window focus_window / move_to_workspace / close_all (test window only)")
    print("=" * 72)
    problems: list[str] = []

    before = window.list_clients()
    before_addrs = {str(c.get("address")) for c in before}
    before_classes = {str(c.get("class", "")).lower() for c in before}
    original_active = _active_address()
    print(f"\n[c0] pre-existing clients ({len(before)}):")
    for c in before:
        print(f"     - class={c.get('class')!r} addr={c.get('address')} ws={c.get('workspace', {}).get('id')}")
    print(f"[c0] originally-active address: {original_active}")
    print(f"[c0] classes to exclude from close_all: {sorted(before_classes)}")

    if "firefox" in {str(c.get("class", "")).lower() for c in before} or any(
        "firefox" in str(c.get("class", "")).lower() for c in before
    ):
        problems.append("c0: firefox already open - refusing to run (safety: cannot use it as a test window)")
        return problems

    test_client: dict[str, Any] | None = None
    try:
        print("\n[c1] window.open_app('firefox') -> ", end="")
        test_client = window.open_app("firefox")
        test_addr = str(test_client.get("address"))
        print(f"{test_client}")
        print(f"[c2] test window address: {test_addr}")

        print("\n[c3] window.focus_window(test window) -> ", end="")
        print(window.focus_window(test_addr))
        time.sleep(0.5)
        active = _active_address()
        print(f"[c4] get_active_window().address -> {active}  (expect {test_addr})")
        if active != test_addr:
            problems.append(f"c4: active window is {active}, not the focused test window {test_addr}")

        print("\n[c5] window.move_to_workspace(9, test window) -> ", end="")
        print(window.move_to_workspace(9, test_addr))
        time.sleep(0.5)
        moved = _client_by_address(test_addr)
        print(f"[c6] test window workspace.id -> {moved.get('workspace', {}).get('id')}  (expect 9)")
        if not moved or moved.get("workspace", {}).get("id") != 9:
            problems.append(f"c6: test window did not land on workspace 9 (got {moved.get('workspace', {}) if moved else None})")

        # move it back to the originally-active workspace so it is not left elsewhere
        orig_ws = None
        for c in before:
            if str(c.get("address")) == original_active:
                orig_ws = c.get("workspace", {}).get("id")
        if orig_ws:
            print(f"\n[c7] window.move_to_workspace({orig_ws}, test window) -> {window.move_to_workspace(orig_ws, test_addr)}")
            time.sleep(0.5)

        # TOCTOU guard: the exclude list is a snapshot from c0. If a NEW
        # client appeared since (e.g. the user opened a window mid-run), its
        # class is not excluded and close_all would close it - refuse instead.
        now = window.list_clients()
        new_clients = [c for c in now if str(c.get("address")) not in before_addrs
                       and str(c.get("address")) != test_addr]
        if new_clients:
            problems.append(
                f"c8: {len(new_clients)} new client(s) appeared since the snapshot "
                f"({[c.get('class') for c in new_clients]}) - refusing to run close_all "
                "so nothing unexpected can be closed"
            )
            return problems
        print("\n[c8] window.close_all(exclude_classes={...}) -> ", end="")
        n_closed = window.close_all(exclude_classes=sorted(before_classes))
        print(f"{n_closed} closed")
        after = window.list_clients()
        after_addrs = {str(c.get("address")) for c in after}
        survivors = before_addrs & after_addrs
        print(f"[c9] pre-existing clients still present: {len(survivors)}/{len(before_addrs)}")
        missing = before_addrs - after_addrs
        if missing:
            problems.append(f"c9: close_all closed a pre-existing window: {missing}")
        if str(test_addr) in after_addrs:
            problems.append("c9: close_all did NOT close the (only non-excluded) test window")
        print(f"[c9] test window closed: {test_addr not in after_addrs}")
    finally:
        # safety net: close any test window still open, then restore focus
        if test_client is not None:
            addr = str(test_client.get("address"))
            if _client_by_address(addr):
                try:
                    window.close_window(addr)
                    print(f"  [cleanup] closed leftover test window {addr}")
                except Exception as exc:
                    print(f"  [cleanup] could not close leftover test window: {exc}")
        if original_active and _client_by_address(original_active):
            try:
                window.focus_window(original_active)
                print(f"  [cleanup] focus restored to {original_active}")
            except Exception as exc:
                print(f"  [cleanup] could not restore focus: {exc}")

    print("\n--- SECTION C DoD ---")
    if problems:
        for p in problems:
            print(f"  FAIL: {p}")
    else:
        print("  OK: focused test window, moved it ws9 and back, close_all closed ONLY it;")
        print("      every pre-existing window survived; focus restored")
    return problems


# ------------------------------------------------------------------- main


def main() -> None:
    print("=" * 72)
    print("BRING-UP (remaining L1 primitives): media pause/resume, browser upload,")
    print("window focus/move/close_all - unattended, user windows protected")
    print("=" * 72)
    set_run_id(RUN_LABEL)

    all_problems: list[str] = []

    try:
        if not TEST_TONE.exists():
            print(f"SKIP A: test tone missing at {TEST_TONE}")
        else:
            all_problems += section_media()

        all_problems += section_upload()

        all_problems += section_window()
    except Exception as exc:
        # never propagate raw: an unattended run must still close the browser
        # and print an honest DoD, not traceback into a locked-profile leak
        all_problems.append(f"unexpected exception: {type(exc).__name__}: {exc}")
    finally:
        # hygiene - always: a raised section must not leave the Playwright
        # browser holding the profile
        browser.close()

    _dump(RUN_LABEL, f"bring-up {RUN_LABEL}")

    print("\n=== BRING-UP DoD ===")
    for p in all_problems:
        print(f"  FAIL: {p}")
    if not all_problems:
        print("  OK: pause/resume proved; upload_file proved; focus/move/close_all proved")
        print("      with every pre-existing window untouched and focus restored")
    ok = not all_problems

    print(f"\nBRING-UP: {'DONE' if ok else 'FAILED'} (media A / upload B / window C)")
    sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
