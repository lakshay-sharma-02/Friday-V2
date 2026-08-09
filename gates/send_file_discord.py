#!/usr/bin/env python
"""Send a local FILE to a Discord channel via the official REST API.

Usage:  ./.venv/bin/python -u gates/send_file_discord.py <file> [channel_id]

channel_id is a numeric Discord channel id. Credentials: DISCORD_BOT_TOKEN +
DISCORD_CHANNEL_ID env vars, or a pass entry `friday/discord` (JSON:
bot_token, channel_id).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from friday.l1 import discord  # noqa: E402

FILE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else ROOT / "README.md"
CHANNEL = sys.argv[2] if len(sys.argv) > 2 else None  # None -> configured channel_id

if not FILE.exists():
    print(f"FAILED: file not found: {FILE}", flush=True)
    sys.exit(1)

print(f"target: send {FILE.name} ({FILE.stat().st_size} bytes) via REST API -> channel {CHANNEL or 'configured channel'}", flush=True)
bot = discord.get_me()
print(f"bot identity: @{bot}", flush=True)
result = discord.send_file(channel_id=CHANNEL, file_path=str(FILE), caption="Sent by Friday")
print(json.dumps(result, indent=2), flush=True)
print(f"RESULT: Discord accepted the message (id {result['message_id']}) - check your channel", flush=True)
