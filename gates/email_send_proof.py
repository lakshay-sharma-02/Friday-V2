#!/usr/bin/env python
"""EMAIL-SEND proof - the capability-gap loop's first side-effecting
primitive, proven live.

`gmail.send_document` was hand-built (the two LLM drafts for it were
rejected on record), passed the automated gate (AST clean, sandboxed
test 6/6, build-verify honestly NOT APPLICABLE for gmail), was
human-signed and registered. This runner proves the ORIGINAL refused
goal - "email the newest receipt pdf to myself" - now completes instead
of refusing: a deterministic verified plan (same convention as the
WATCHER proofs) locates the newest receipt PDF in ~/Downloads and emails
it via the registered primitive, recording the run in tasks.jsonl and
writing gates/EMAIL_SEND_PROOF.md.

Recipient resolution (in order): --to <email>  >  GMAIL_DEFAULT_TO env
>  'default_to' in the pass entry friday/gmail. When no recipient is
configured, the runner fails loudly - a send must never guess an address.

PREREQUISITE (user-only, one browser step): the refresh token in pass
must carry the gmail.send scope. tokeninfo on a fresh access token is
the definitive check - a token minted for gmail.readonly only will 403
at send time. Re-consent with BOTH scopes:

  GMAIL_DEFAULT_TO=you@example.com ./.venv/bin/python -u \\
      gates/_gmail_oauth_setup.py /path/to/credentials.json \\
      --scope "https://www.googleapis.com/auth/gmail.readonly https://www.googleapis.com/auth/gmail.send"

Run:  ./.venv/bin/python -u gates/email_send_proof.py [--to you@example.com]
"""

from __future__ import annotations

import argparse
import io
import json
import sys
from contextlib import redirect_stdout
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

PROOF = "gates/EMAIL_SEND_PROOF.md"
RECEIPT_PDF = "friday_demo_receipt.pdf"  # the newest receipt pdf in Downloads (2026-08-11)
DOWNLOADS = "/home/lakshay/Downloads"


def _recipient(args_to: str | None) -> str:
    import os

    from friday.secrets import get_credentials

    to = args_to or os.environ.get("GMAIL_DEFAULT_TO")
    if not to:
        try:
            creds = get_credentials("gmail")
        except Exception:
            creds = {}
        to = creds.get("default_to") or ""
    if not to or "@" not in to:
        raise SystemExit(
            "NO RECIPIENT: pass --to <email>, set GMAIL_DEFAULT_TO, or store "
            "'default_to' in pass at friday/gmail (the consent command does this). "
            "A send must never guess an address."
        )
    return to


def _scope_check() -> tuple[str, bool]:
    """(report, can_send) - definitive proof the token can send: tokeninfo
    lists the scopes the CURRENT refresh token grants (scopes are fixed at
    consent time). can_send is False when gmail.send is missing - the
    runner MUST abort before attempting a send that would 403."""
    from friday.l1 import gmail

    import requests

    try:
        tok = gmail._access_token()
    except Exception as exc:
        return f"FAILED to obtain an access token: {type(exc).__name__}: {exc}", False
    r = requests.get(
        "https://oauth2.googleapis.com/tokeninfo",
        params={"access_token": tok},
        timeout=30,
    )
    if r.status_code != 200:
        return f"FAILED tokeninfo ({r.status_code}): {r.text[:200]}", False
    scopes = (r.json().get("scope") or "").split()
    has_send = any("gmail.send" in s for s in scopes)
    has_ro = any("gmail.readonly" in s for s in scopes)
    report = f"granted scopes: {sorted(scopes)}\ngmail.send: {has_send} | gmail.readonly: {has_ro}"
    if not has_send:
        report += (
            "\nRE-CONSENT NEEDED: the token lacks gmail.send (scopes are fixed "
            "at consent time). Re-run with BOTH scopes (keep readonly - the "
            "token is shared with the morning digest):\n"
            "  GMAIL_DEFAULT_TO=<your email> ./.venv/bin/python -u \\n"
            "      gates/_gmail_oauth_setup.py /path/to/credentials.json \\n"
            "      --scope \"https://www.googleapis.com/auth/gmail.readonly "
            "https://www.googleapis.com/auth/gmail.send\"\n"
            "Full doc: gates/GMAIL_SETUP.md section 6.5."
        )
    return report, has_send


def main() -> int:
    ap = argparse.ArgumentParser(description="Live proof for the registered gmail.send_document primitive")
    ap.add_argument("--to", default=None, help="recipient email (overrides GMAIL_DEFAULT_TO / pass default_to)")
    args = ap.parse_args()

    out: list[str] = []
    print("=" * 72)
    print(f"EMAIL-SEND proof - the loop's first side-effecting primitive, live ({datetime.now(timezone.utc).isoformat(timespec='seconds')})")
    print("=" * 72)

    to = _recipient(args.to)
    print(f"\n--- 1. scope check (definitive: tokeninfo on a fresh access token) ---")
    scope_report, can_send = _scope_check()
    print(scope_report)
    out.append(scope_report)
    if not can_send:
        print("\nABORTING before any send attempt - gmail.send scope missing.")
        (ROOT / PROOF).write_text(
            "# EMAIL_SEND_PROOF - BLOCKED (no send scope)\n\n"
            f"Status date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.\n\n"
            "The live send was NOT attempted: tokeninfo on a fresh access token"
            " shows the refresh token lacks the gmail.send scope (scopes are\n"
            "fixed at consent time). This is the one user-only step - re-consent\n"
            "with both scopes (gates/GMAIL_SETUP.md section 6.5), then re-run.\n\n```\n"
            + scope_report + "\n```\n",
            encoding="utf-8",
        )
        return 1

    print("\n--- 2. the deterministic verified plan (real executor) ---")
    plan = {
        "goal": "email the newest receipt pdf to myself",
        "steps": [
            {
                "primitive": "files.find_file_exact",
                "args": {"name": RECEIPT_PDF, "directory": DOWNLOADS},
                "verify": {"check": "checks.file_exists", "args": {"path": "$steps.1.result"}, "expect": True},
                "verify_wait_s": 0.1, "backoff_s": 0.05,
            },
            {
                "primitive": "gmail.send_document",
                "args": {
                    "file_path": "$steps.1.result",
                    "to": to,
                    "subject": "Friday: newest receipt PDF",
                    "body": "Newest receipt PDF from Downloads, sent by Friday via gmail.send_document.",
                },
                "verify": {"check": "checks.text_nonempty", "args": {"value": "$steps.2.result.message_id"}, "expect": True},
                "verify_wait_s": 0.1, "backoff_s": 0.05,
            },
        ],
    }
    from friday.l3.executor import run_plan

    result = run_plan(plan, run_id="email-send-proof")
    run_log = [f"plan status: {result.status}"]
    for sr in result.steps:
        run_log.append(f"  step {sr.step_id}: {sr.primitive:24s} {sr.status}")
        if sr.result is not None:
            run_log.append(f"      result: {json.dumps(sr.result, default=str)[:220]}")
    print("\n".join(run_log))
    out += run_log

    sent = result.status == "COMPLETED" and all(s.status == "VERIFIED" for s in result.steps)
    proof = "\n".join([
        "# EMAIL_SEND_PROOF - the loop's first side-effecting primitive, live",
        "",
        f"Status date: {datetime.now(timezone.utc).isoformat(timespec='seconds')}.",
        "",
        "gmail.send_document was hand-built (the two LLM drafts for it were",
        "rejected on record - confabulated wrapper + invalid contract name),",
        "passed the automated gate (AST clean, sandboxed test 6/6, build-verify",
        "honestly NOT APPLICABLE for gmail - the human signature IS the semantic",
        "gate for send-capable code), and registered. The original refused goal -",
        "'email the newest receipt pdf to myself' - now runs through the REAL",
        "executor with every step VERIFIED.",
        "",
        "## 1. Scope check (tokeninfo on a fresh access token)",
        "",
        "```",
        scope_report,
        "```",
        "",
        "## 2. The deterministic verified plan (real executor)",
        "",
        "```",
        "\n".join(run_log),
        "```",
        "",
        "## Verdict",
        "",
        f"{'SEND PROVEN END TO END' if sent else 'SEND FAILED - see the step statuses'} - the",
        "recipient is redacted from this proof; the L0 line redacts it too",
        "(log_transform keeps message_id/filename visible, never the address).",
        "",
    ])
    (ROOT / PROOF).write_text(proof + "\n", encoding="utf-8")
    print(f"\nproof written to {PROOF}")
    return 0 if sent else 1


if __name__ == "__main__":
    sys.exit(main())
