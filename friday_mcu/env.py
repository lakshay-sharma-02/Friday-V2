"""Local credential loader.

The adapters read credentials from env vars (TELEGRAM_BOT_TOKEN, ...), but the
project keeps its real credentials in `config/credentials.json` (gitignored).
Nothing ever loaded that file — so the watcher, API and channels silently ran
with zero platforms configured unless the user exported every variable by hand.

`load_credentials()` maps the file's sections onto the env var names the
adapters read, only for variables that are not already set, and never echoes
or logs any value. Calling it is cheap and idempotent.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CREDENTIALS_FILE = PROJECT_ROOT / "config" / "credentials.json"

# credentials.json section -> env var names (calendar reuses the Gmail OAuth
# vars because the adapter is backed by the same Google project).
_ENV_MAP: dict[str, dict[str, str]] = {
    "telegram": {
        "bot_token": "TELEGRAM_BOT_TOKEN",
        "chat_id": "TELEGRAM_DEFAULT_CHAT",
    },
    "discord": {
        "bot_token": "DISCORD_BOT_TOKEN",
        "channel_id": "DISCORD_CHANNEL_ID",
    },
    "whatsapp": {
        "access_token": "WHATSAPP_ACCESS_TOKEN",
        "phone_number_id": "WHATSAPP_PHONE_NUMBER_ID",
        "default_phone": "WHATSAPP_DEFAULT_PHONE",
    },
    "gmail": {
        "client_id": "GMAIL_CLIENT_ID",
        "client_secret": "GMAIL_CLIENT_SECRET",
        "refresh_token": "GMAIL_REFRESH_TOKEN",
    },
    "calendar": {
        "client_id": "GMAIL_CLIENT_ID",
        "client_secret": "GMAIL_CLIENT_SECRET",
        "refresh_token": "GMAIL_REFRESH_TOKEN",
    },
}


def credentials_file() -> Path:
    return Path(os.environ.get("FRIDAY_CREDENTIALS_FILE", str(DEFAULT_CREDENTIALS_FILE)))


def load_credentials() -> set[str]:
    """Populate adapter env vars from config/credentials.json.

    Returns the set of env var names this call (or a previous call) loaded —
    empty when the file is absent, malformed, or holds nothing usable.
    Existing environment variables always win.
    """
    loaded: set[str] = set()
    path = credentials_file()
    if not path.exists():
        return loaded
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return loaded
    if not isinstance(data, dict):
        return loaded

    for section, mapping in _ENV_MAP.items():
        creds = data.get(section)
        if not isinstance(creds, dict):
            continue
        for key, env_name in mapping.items():
            if os.environ.get(env_name):
                continue  # explicit env var wins over the file
            value = creds.get(key)
            if isinstance(value, str) and value.strip():
                os.environ[env_name] = value
                loaded.add(env_name)
    return loaded


def _status_summary() -> list[str]:
    """Names of platforms with usable credentials (no values)."""
    checks = [
        ("telegram", ["TELEGRAM_BOT_TOKEN"]),
        ("discord", ["DISCORD_BOT_TOKEN"]),
        ("whatsapp", ["WHATSAPP_ACCESS_TOKEN", "WHATSAPP_PHONE_NUMBER_ID"]),
        ("gmail/calendar", ["GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN"]),
    ]
    return [name for name, keys in checks if all(os.environ.get(k) for k in keys)]
