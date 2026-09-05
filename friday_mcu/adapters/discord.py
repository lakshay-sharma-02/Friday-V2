"""Discord Bot API adapter."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import requests

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import AdapterError, PreconditionError

API_BASE = "https://discord.com/api/v10"

# Persisted per-channel watermark: without it, poll_messages returns the same
# recent messages on every call and the discord-text watcher would re-execute
# the same goals forever.
STATE_DIR = Path.home() / ".config" / "friday" / "discord"
WATERMARK_FILE = STATE_DIR / "watermarks.json"


def _load_watermarks() -> dict[str, int]:
    try:
        data = json.loads(WATERMARK_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(data, dict):
        return {}
    return {str(k): int(v) for k, v in data.items() if isinstance(v, (str, int))}


def _save_watermarks(watermarks: dict[str, int]) -> None:
    try:
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        tmp = WATERMARK_FILE.with_name(WATERMARK_FILE.name + ".tmp")
        tmp.write_text(json.dumps(watermarks), encoding="utf-8")
        os.replace(tmp, WATERMARK_FILE)
    except OSError:
        pass


def mark_channel_read(channel_id: str, message_id: str) -> None:
    """Advance the channel watermark past a handled message."""
    ch = channel_id or os.environ.get("DISCORD_CHANNEL_ID", "")
    if not ch or not message_id:
        return
    try:
        new_id = int(message_id)
    except (TypeError, ValueError):
        return
    watermarks = _load_watermarks()
    if new_id > watermarks.get(ch, 0):
        watermarks[ch] = new_id
        _save_watermarks(watermarks)


def _headers() -> dict[str, str]:
    token = os.environ.get("DISCORD_BOT_TOKEN", "")
    if not token:
        raise AdapterError("DISCORD_BOT_TOKEN not set")
    return {"Authorization": f"Bot {token}", "Content-Type": "application/json"}


@contract(
    precondition="DISCORD_BOT_TOKEN is set.",
    postcondition="Returns the bot's profile info.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="AdapterError if the API call fails.",
    returns="dict: bot info from /users/@me.",
)
def get_me() -> dict[str, Any]:
    """Get Discord bot profile."""
    try:
        resp = requests.get(f"{API_BASE}/users/@me", headers=_headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as exc:
        raise AdapterError(f"Discord getMe failed: {exc}") from exc


@contract(
    precondition="text is non-empty and channel_id is set.",
    postcondition="Returns {message_id, channel_id, status}.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="AdapterError if the send fails.",
    returns="dict: {message_id: str, channel_id: str, status: str}.",
)
def send_text(text: str, channel_id: str = "") -> dict[str, Any]:
    """Send a text message via Discord."""
    ch_id = channel_id or os.environ.get("DISCORD_CHANNEL_ID", "")
    if not ch_id:
        raise PreconditionError("No channel_id and no DISCORD_CHANNEL_ID set")
    try:
        resp = requests.post(
            f"{API_BASE}/channels/{ch_id}/messages",
            headers=_headers(),
            json={"content": text},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        return {"message_id": result.get("id", ""), "channel_id": ch_id, "status": "sent"}
    except Exception as exc:
        raise AdapterError(f"Discord sendText failed: {exc}") from exc


@contract(
    precondition="file_path points to an existing file.",
    postcondition="Returns {message_id, channel_id, status, file}.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="AdapterError if upload fails.",
    returns="dict: {message_id: str, channel_id: str, status: str, file: str}.",
)
def send_file(file_path: str, channel_id: str = "", caption: str = "") -> dict[str, Any]:
    """Send a file via Discord."""
    ch_id = channel_id or os.environ.get("DISCORD_CHANNEL_ID", "")
    if not ch_id:
        raise PreconditionError("No channel_id and no DISCORD_CHANNEL_ID set")
    from pathlib import Path
    p = Path(file_path)
    if not p.exists():
        raise PreconditionError(f"File not found: {file_path}")
    try:
        with open(p, "rb") as f:
            resp = requests.post(
                f"{API_BASE}/channels/{ch_id}/messages",
                headers={"Authorization": f"Bot {os.environ.get('DISCORD_BOT_TOKEN', '')}"},
                data={"content": caption} if caption else {},
                files={"file": (p.name, f)},
                timeout=60,
            )
        resp.raise_for_status()
        result = resp.json()
        return {"message_id": result.get("id", ""), "channel_id": ch_id, "status": "sent", "file": p.name}
    except Exception as exc:
        raise AdapterError(f"Discord sendFile failed: {exc}") from exc


@contract(
    precondition="DISCORD_BOT_TOKEN is set.",
    postcondition="Returns recent messages from the channel.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="AdapterError if polling fails.",
    returns="list[dict]: [{id, content, author, channel_id}].",
)
def poll_messages(channel_id: str = "", limit: int = 10, commit: bool = False) -> list[dict[str, Any]]:
    """Poll for NEW messages in a Discord channel (newer than the watermark).

    commit=False (default) never advances the watermark — presence probes and
    read-only plans do not consume the queue. The watcher calls
    mark_channel_read() per handled message instead. Messages are returned in
    chronological order.
    """
    ch_id = channel_id or os.environ.get("DISCORD_CHANNEL_ID", "")
    if not ch_id:
        return []
    try:
        resp = requests.get(
            f"{API_BASE}/channels/{ch_id}/messages",
            headers=_headers(),
            params={"limit": limit},
            timeout=15,
        )
        resp.raise_for_status()
        messages = resp.json()
    except Exception:
        return []

    try:
        watermark = _load_watermarks().get(ch_id, 0)
    except Exception:
        watermark = 0

    seen: list[dict[str, Any]] = []
    max_id = watermark
    for m in messages:
        try:
            msg_id = int(m.get("id", 0))
        except (TypeError, ValueError):
            continue
        content = m.get("content", "")
        if not content:
            continue
        max_id = max(max_id, msg_id)
        if msg_id > watermark:
            seen.append({
                "id": str(msg_id),
                "content": content,
                "author": m.get("author", {}).get("username", ""),
                "channel_id": ch_id,
            })

    if commit and max_id > watermark:
        mark_channel_read(ch_id, str(max_id))

    seen.sort(key=lambda m: int(m["id"]))
    return seen


class DiscordAdapter(Adapter):
    @property
    def name(self) -> str:
        return "discord"

    @property
    def capabilities(self) -> list[str]:
        return ["get_me", "send_text", "send_file", "poll_messages"]

    async def initialize(self) -> None:
        pass

    async def execute(self, action: str, **kwargs: Any) -> Any:
        actions = {"get_me": get_me, "send_text": send_text, "send_file": send_file, "poll_messages": poll_messages, "mark_channel_read": mark_channel_read}
        fn = actions.get(action)
        if fn is None:
            raise AdapterError(f"Unknown discord action: {action}")
        return fn(**kwargs)

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        return bool(os.environ.get("DISCORD_BOT_TOKEN"))


try:
    register_adapter(DiscordAdapter())
except Exception:
    pass
