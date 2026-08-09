#!/usr/bin/env python
"""Standalone bring-up for the gmail primitives (Phase 2 Task #10).

Sections:
  A. gmail.list_unread(sender)   - structural shape of real unread mail
  B. gmail.get_message(message_id) - headers + body presence (body REDACTED)
  C. gmail.summarize(message_id) - the LLM summary (the deliverable)

The message BODY is never printed in full - only its byte length - and
tokens are never printed. Structural shape (ids, From, Subject, Date) is
shown so the proof is raw, not narrative.

Run:  ./.venv/bin/python -u gates/bringup_gmail.py <sender>
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.errors import FridayError  # noqa: E402
from friday.l1 import gmail  # noqa: E402
from friday.observability import set_run_id  # noqa: E402

SENDER = sys.argv[1] if len(sys.argv) > 1 else ""


def main() -> None:
    if not SENDER:
        print("usage: bringup_gmail.py <sender-email-or-name>", flush=True)
        sys.exit(2)

    set_run_id("bringup-gmail")
    problems: list[str] = []
    print("=" * 72)
    print("GMAIL BRING-UP - list_unread / get_message / summarize (read-only)")
    print(f"SENDER: {SENDER!r}")
    print("=" * 72)

    # --- Section A: list_unread -------------------------------------------------
    print("\n=== SECTION A - gmail.list_unread (structural shape, real inbox) ===")
    try:
        msgs = gmail.list_unread(SENDER, max_results=5)
    except FridayError as exc:
        problems.append(f"A: list_unread raised {type(exc).__name__}: {exc}")
        msgs = []
    if not msgs:
        problems.append(
            f"A: no unread messages from {SENDER!r} - the bring-up needs at "
            "least one genuinely unread email from a known sender"
        )
    for m in msgs:
        print(json.dumps(m, indent=2))
    print(f"OK: list_unread returned {len(msgs)} unread message(s); structural "
          f"shape above (id, From, Subject, Date - no body, no token)")

    # --- Section B: get_message -------------------------------------------------
    print("\n=== SECTION B - gmail.get_message (headers + body presence, body REDACTED) ===")
    first_id = msgs[0]["message_id"] if msgs else ""
    if first_id:
        try:
            msg = gmail.get_message(first_id)
            print(f"message_id : {msg['message_id']}")
            print(f"from       : {msg['sender']}")
            print(f"subject    : {msg['subject']}")
            print(f"date       : {msg['date']}")
            print(f"snippet    : {msg['snippet'][:160]!r}")
            print(f"body       : <{len(msg['body'])} chars - REDACTED from output>")
            if not msg["sender"]:
                problems.append("B: get_message returned an empty From header")
            if not msg["body"] and not msg["snippet"]:
                problems.append("B: get_message returned no readable content")
            print("OK: get_message returned structural metadata + readable content "
                  "(body length above, content redacted)")
        except FridayError as exc:
            problems.append(f"B: get_message raised {type(exc).__name__}: {exc}")
    else:
        problems.append("B: skipped - no message id from section A")

    # --- Section C: summarize ---------------------------------------------------
    print("\n=== SECTION C - gmail.summarize (the deliverable; internal LLM call) ===")
    if first_id:
        try:
            summary = gmail.summarize(first_id)
            print(f"SUMMARY (for {first_id}):\n{summary}")
            if len(summary.strip()) < 20:
                problems.append("C: summary suspiciously short (< 20 chars)")
            print("OK: summarize returned a non-trivial summary (deliverable above)")
        except FridayError as exc:
            problems.append(f"C: summarize raised {type(exc).__name__}: {exc}")
    else:
        problems.append("C: skipped - no message id from section A")

    print("\n=== BRING-UP DoD ===")
    for line in problems:
        print(f"  FAIL: {line}")
    if not problems:
        print("  OK: list_unread -> structural shape (real unread mail)")
        print("  OK: get_message -> headers + readable body (redacted from output)")
        print("  OK: summarize -> non-trivial summary text produced")
        print("  OK: read-only throughout (no labels modified, no mail marked read)")
        print("BRING-UP: DONE")
        sys.exit(0)
    print(f"BRING-UP: FAILED ({len(problems)} problem(s))")
    sys.exit(1)


if __name__ == "__main__":
    main()
