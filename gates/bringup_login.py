#!/usr/bin/env python
"""Task 7 phase 1 - standalone bring-up of browser.credentials + login.

Hand-invoked (no executor, no LLM): prove the secrets path BEFORE any plan
ever calls it - the master plan's rule: a primitive that can't be proven
standalone doesn't get called by the executor.

Proves, with raw output:
  1. credentials("github") reads the pass entry and returns
     {username, password} - with the VALUES never printed (redaction).
  2. goto + read_page_text lands on the GitHub login form; each candidate
     handle is resolved through the fallback chain and printed.
  3. login("github", <username handle>, <password handle>, <sign-in
     handle>) fills and submits with the REAL credentials.
  4. the post-login page shows a logged-in marker and the url left /login.
  5. redaction DoD: the password value appears NOWHERE in this run's L0
     lines (the script fetches it in-process and checks).

Usage:
  ./.venv/bin/python -u gates/bringup_login.py [run_label]

Requires the user-created entry (credentials never pass through chat):
  pass insert -m friday/github      # JSON: {"username": "...", "password": "..."}
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import PrimitiveError  # noqa: E402
from friday.l1 import browser  # noqa: E402
from friday.observability import set_run_id  # noqa: E402

SERVICE = "github"
LOGIN_URL = "https://github.com/login"
# Real page strings, resolved through find_locator's fallback chain
# (attribute relaxation -> accessible-name -> visible text). Edit only if
# the printed probe output shows they do not resolve.
USERNAME_SEL = "Username or email address"
PASSWORD_SEL = "Password"
SUBMIT_SEL = "Sign in"
# Marker that only exists on the logged-in GitHub home page. The first
# bring-up run showed GitHub's current home is a "Dashboard" view
# ("Repositories" was the old layout).
LOGGED_IN_MARKER = "Dashboard"

# Optional argv[1] labels the run so its L0 lines are easy to isolate.
RUN_LABEL = sys.argv[1] if len(sys.argv) > 1 else "bringup-login"


def _redact(value: str) -> str:
    """Never print secret values - only their shape."""
    return f"<{type(value).__name__}, len={len(value)}>"


def _wait_for_text(marker: str, timeout_s: float = 15.0) -> str:
    """Poll read_page_text until the marker appears (the page can still be
    rendering right after submit) and return the settled text. Mirrors how
    L2 checks poll; a bounded wait, never a loop that can hang."""
    deadline = time.monotonic() + timeout_s
    last = ""
    while time.monotonic() < deadline:
        last = browser.read_page_text()
        if marker in last:
            return last
        time.sleep(0.5)
    return last


def main() -> None:
    set_run_id(RUN_LABEL)
    print("=" * 72)
    print("TASK 7 PHASE 1 - standalone bring-up: credentials + login")
    print("=" * 72)

    # 1. credentials from pass (values redacted)
    print("\n--- 1. credentials(service) from pass ---")
    creds = browser.credentials(SERVICE)
    problems: list[str] = []
    if "username" not in creds or "password" not in creds:
        print(f"FAIL: entry {SERVICE!r} lacks 'username'/'password' keys: {sorted(creds)}")
        sys.exit(1)
    print(
        f"credentials({SERVICE!r}) -> keys={sorted(creds)} "
        f"username={_redact(creds['username'])} password={_redact(creds['password'])} "
        "(values never printed)"
    )
    password = creds["password"]

    # 2. prepare: the persistent profile may already hold a GitHub session
    # from an earlier run (the first bring-up logged in; the session cookie
    # persists in var/browser_profile). Log out first so the login below
    # must do REAL work - the plan's pre-logged-in-profile risk. github.com/logout
    # shows a confirmation page with a "Sign out" button when a session
    # exists (and just redirects to /login when not - the click then fails
    # harmlessly).
    print("\n--- 2. prepare: log out any existing session, land on login form ---")
    print(f"goto('https://github.com/logout') -> {browser.goto('https://github.com/logout')}")
    try:
        print(f"click('Sign out') -> {browser.click('Sign out')}")
    except PrimitiveError as exc:
        print(f"click('Sign out') -> skipped (no session to end): {str(exc)[:80]}")
    print(f"goto({LOGIN_URL!r}) -> {browser.goto(LOGIN_URL)}")
    text = browser.read_page_text()
    print("--- login page text (first 25 lines) ---")
    print("\n".join(text.splitlines()[:25]))
    for handle in (USERNAME_SEL, PASSWORD_SEL, SUBMIT_SEL):
        try:
            print(f"  handle {handle!r} -> {browser.find_locator(handle)}")
        except PrimitiveError as exc:
            print(f"  handle {handle!r} -> UNRESOLVED: {exc}")

    # 3. login, hand-invoked, real credentials
    print("\n--- 3. login(service, username, password, submit) ---")
    res = browser.login(SERVICE, USERNAME_SEL, PASSWORD_SEL, SUBMIT_SEL)
    print(f"login result: {res}")
    url = str(res.get("url", ""))

    # 4. post-login state (wait for it to settle - right after submit the
    # page may still be rendering)
    print("\n--- 4. post-login state ---")
    post = _wait_for_text(LOGGED_IN_MARKER)
    print("--- post-login page text (first 15 lines) ---")
    print("\n".join(post.splitlines()[:15]))
    if "github.com" not in url or "/login" in url:
        problems.append(f"login url is still on the login page: {url!r}")
    if "Sign in to GitHub" in post:
        problems.append("post-login text still shows the sign-in form")
    if LOGGED_IN_MARKER not in post:
        problems.append(
            f"post-login text missing logged-in marker {LOGGED_IN_MARKER!r}"
        )

    # 5. redaction DoD: password nowhere in this run's L0 lines
    log = ROOT / "var" / "logs" / "friday.jsonl"
    lines = [
        json.loads(l) for l in log.read_text().splitlines()
        if json.loads(l).get("run_id") == RUN_LABEL
    ]
    leaked = [rec for rec in lines if password in json.dumps(rec)]
    if leaked:
        problems.append(f"password value appears in {len(leaked)} L0 log lines")

    print("\n=== BRING-UP DoD ===")
    for p in problems:
        print(f"  FAIL: {p}")
    if not problems:
        print("  OK: credentials parsed from pass (values redacted)")
        print(f"  OK: login filled + submitted; url={url}")
        print(f"  OK: logged-in marker {LOGGED_IN_MARKER!r} present")
        print("  OK: password appears nowhere in the L0 trace")

    browser.close()
    print(f"\nBRING-UP: {'DONE' if not problems else 'FAILED'} "
          "(credentials -> login -> logged-in state; raw output above)")
    sys.exit(0 if not problems else 1)


if __name__ == "__main__":
    main()
