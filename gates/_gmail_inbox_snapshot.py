#!/usr/bin/env python
"""One-off diagnostic: snapshot the UNREAD inbox so the user can pick a
target sender for the bring-up / task goal ("pick whatever is unread").

Read-only, gmail.readonly scope. Prints distinct From values with counts
and the most recent subject per sender - no bodies, no tokens.

Run:  ./.venv/bin/python -u gates/_gmail_inbox_snapshot.py
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.l1 import gmail  # noqa: E402


def main() -> None:
    print("=== UNREAD INBOX SNAPSHOT (structural only, no bodies) ===", flush=True)
    body = gmail._get("/users/me/messages", {"q": "is:unread", "maxResults": 50})
    items = body.get("messages") or []
    if not items:
        print("No unread messages found in the inbox.", flush=True)
        return
    senders: Counter[str] = Counter()
    subjects: dict[str, str] = {}
    for item in items:
        mid = item.get("id", "")
        meta = gmail._get(
            f"/users/me/messages/{mid}",
            {"format": "metadata", "metadataHeaders": ["From", "Subject", "Date"]},
        )
        payload = meta.get("payload", {})
        frm = gmail._header(payload, "From")
        subj = gmail._header(payload, "Subject")
        senders[frm] += 1
        if frm not in subjects:
            subjects[frm] = subj
    print(f"{len(items)} unread message(s), {len(senders)} distinct sender(s):\n")
    for frm, n in senders.most_common():
        print(f"  {n:3d} unread | {frm}")
        print(f"           latest subject: {subjects[frm][:80]!r}")
    print("\nPick a sender above and re-run the bring-up/task with it, e.g.:")
    print("  ./.venv/bin/python -u gates/bringup_gmail.py '<sender-fragment>'")


if __name__ == "__main__":
    main()
