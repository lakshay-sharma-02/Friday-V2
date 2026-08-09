#!/usr/bin/env python
"""Send a local FILE to a WhatsApp number via the official Cloud API
(friday.l1.whatsapp). Deterministic - no browser, no sync.

Usage:  ./.venv/bin/python -u gates/send_file_whatsapp_api.py <file> [91XXXXXXXXXX]

Credentials: WHATSAPP_ACCESS_TOKEN + WHATSAPP_PHONE_NUMBER_ID env vars, or
a pass entry `friday/whatsapp` (JSON).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.l1 import whatsapp  # noqa: E402

FILE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "README.md"
PHONE = sys.argv[2] if len(sys.argv) > 2 else "918396020807"

if not FILE.exists():
    print(f"FAILED: file not found: {FILE}", flush=True)
    sys.exit(1)

print(f"target: send {FILE.name} ({FILE.stat().st_size} bytes) via Cloud API -> {PHONE}", flush=True)
result = whatsapp.send_document(to=PHONE, file_path=str(FILE), caption="Sent by Friday")
print(json.dumps(result, indent=2), flush=True)
if result.get("message_id"):
    print("RESULT: WhatsApp accepted the message - check your phone", flush=True)
else:
    print("RESULT: accepted by API but no message id in response", flush=True)
