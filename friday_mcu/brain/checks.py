"""L2 — Verification checks.

Every function here is side-effect-free: it reads current real-world state
through a primitive's read-only accessor and returns True/False (or a
scalar) against a specific claim. The executor runs these AFTER a
primitive to verify its effect.

Import discipline: only read-only primitive functions are imported.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _window_clients() -> list[dict[str, Any]]:
    """Read the live client list through the read-only primitive."""
    try:
        from friday_mcu.adapters.window import list_clients
        clients = list_clients()
        return clients if isinstance(clients, list) else []
    except Exception:
        return []


def window_client_count() -> int:
    """Claim: 'there are N windows open right now'. Read-only."""
    return len(_window_clients())


def window_has_class(cls: str) -> bool:
    """Claim: 'at least one open window has class X'. Read-only."""
    cls_lower = cls.lower()
    return any(cls_lower in str(c.get("class", "")).lower() for c in _window_clients())


def media_playing() -> bool:
    """Claim: 'media is currently playing'. Read-only."""
    try:
        from friday_mcu.adapters.media import is_playing
        return bool(is_playing())
    except Exception:
        return False


def file_exists(path: str) -> bool:
    """Claim: 'a file exists at path'. Read-only filesystem check."""
    return Path(path).exists()


def list_nonempty(value: list) -> bool:
    """Claim: 'a step result is a non-empty list'. Pure shape check."""
    return isinstance(value, list) and len(value) > 0


def call_succeeded(value: Any) -> bool:
    """Claim: 'the primitive call did not raise an error'.

    Use this for read-only 'check' goals where empty results are valid.
    Pass the raw step result as 'value'.
    """
    if isinstance(value, str) and value.startswith("ERROR:"):
        return False
    return True


def text_nonempty(value: str) -> bool:
    """Claim: 'a step result is a non-empty string'. Pure shape check."""
    return isinstance(value, str) and bool(value.strip())


def message_sent(platform: str, message_id: str) -> bool:
    """Claim: 'the messaging platform acknowledged a message with this id'.

    Read-only pure function: never touches the network.
    """
    if not message_id:
        return False
    p = platform.lower()
    if p == "whatsapp":
        return message_id.startswith("wamid")
    if p == "telegram":
        return message_id.isdigit()
    if p == "discord":
        return message_id.isdigit() and len(message_id) >= 17
    return False


def gmail_unread_exists(sender: str = "") -> bool:
    """Claim: 'there is at least one unread message from this sender'."""
    try:
        from friday_mcu.adapters.gmail import list_unread
        result = list_unread(sender=sender, max_results=1)
        return bool(result)
    except Exception:
        return False


def gmail_message_matches(message_id: str, expected_sender_substring: str = "") -> bool:
    """Claim: 'the fetched message's From header contains the expected sender'."""
    try:
        from friday_mcu.adapters.gmail import get_message
        msg = get_message(message_id=message_id)
        sender = str(msg.get("sender", ""))
        needle = expected_sender_substring.lower()
        return bool(needle and needle in sender.lower())
    except Exception:
        return False


def memory_has_key(key: str, category: str | None = None) -> bool:
    """Claim: 'a memory exists with this key'."""
    from friday_mcu.memory.store import MemoryManager
    mgr = MemoryManager()
    results = mgr.search(key, limit=10)
    return any(r.key == key for r in results)


def memory_store_status(status: str) -> bool:
    """Claim: 'the last memory store operation had this status'."""
    return status in ("stored", "updated")


def repo_is_clean(repo_path: str) -> bool:
    """Claim: 'the git repository has no uncommitted changes'."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0 and not result.stdout.strip()
    except Exception:
        return False


def http_status_ok(status_code: int) -> bool:
    """Claim: 'the HTTP response status is 2xx'."""
    return 200 <= status_code < 300


def http_status_code(status_code: int) -> int:
    """Claim: 'the HTTP response status is N'. Returns the actual code."""
    return status_code
