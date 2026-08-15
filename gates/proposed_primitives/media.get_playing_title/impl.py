from __future__ import annotations

from friday.contracts import Idempotency, contract


@contract(
    precondition="None - reports current state with no caller obligations.",
    postcondition="Makes NO state changes. Returns the current media-title property of "
    "the running mpv player, or None if no player is reachable. Distinct from "
    "media.play/play_for, which start playback.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Never raises: a missing or unreachable mpv player is reported "
    "as None, not an error. An mpv IPC reply that lacks a title value or "
    "carries an error is also treated as None.",
    returns="str | None - the current media title (mpv 'media-title' "
    "property), or None when no player responds or the property is "
    "unavailable.",
)
def get_playing_title() -> str | None:
    """Return the current mpv media title, or None if no player is reachable.

    Read-only query counterpart to play/play_for. Sends a single
    get_property request for 'media-title' over the mpv IPC socket;
    if the player is not running, the socket request fails, or the
    reply carries an error, returns None instead of raising - the goal
    "what song is currently playing" is answered with absence, not a
    crash.
    """
    reply = _socket_send({"command": ["get_property", "media-title"]})
    if not _reply_ok(reply):
        return None
    data = reply.get("data")
    if isinstance(data, str) and data.strip():
        return data
    return None