#!/usr/bin/env python
"""Send a local FILE to a Telegram chat via the official Bot API.

Usage:  ./.venv/bin/python -u gates/send_file_telegram.py <file> [chat_id]

chat_id is a numeric chat id (e.g. 123456789) or @username. Credentials:
TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID env vars, or a pass entry
`friday/telegram` (JSON: bot_token, chat_id).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.l1 import telegram  # noqa: E402

FILE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "README.md"
CHAT = sys.argv[2] if len(sys.argv) > 2 else None  # None -> configured chat_id

if not FILE.exists():
    print(f"FAILED: file not found: {FILE}", flush=True)
    sys.exit(1)

print(f"target: send {FILE.name} ({FILE.stat().st_size} bytes) via Bot API -> {CHAT or 'configured chat'}", flush=True)
bot = telegram.get_me()
print(f"bot identity: @{bot}", flush=True)
result = telegram.send_document(to=CHAT, file_path=str(FILE), caption="Sent by Friday")
print(json.dumps(result, indent=2), flush=True)
print(f"RESULT: Telegram accepted the message (id {result['message_id']}) - check your chat", flush=True)
