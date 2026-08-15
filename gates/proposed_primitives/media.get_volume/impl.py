from __future__ import annotations

from friday.contracts import Idempotency, contract


@contract(
    precondition="None - reports current state with no caller obligations.",
    postcondition="Makes NO state changes. Returns the current playback volume "
    "(0-100) of the running mpv player, or None if no player is reachable. "
    "Distinct from set_volume, which writes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="Never raises: a missing or unreachable mpv player is reported "
    "as None, not an error. An mpv IPC reply that lacks a volume value is "
    "also treated as None.",
    returns="int | None - the current volume in the 0-100 range, or None when "
    "no player responds.",
)
def get_volume() -> int | None:
    """Return the current mpv playback volume (0-100), or None if no player is reachable.

    Read-only counterpart to set_volume. Sends a single get_property
    request over the mpv IPC socket; if the player is not running, the socket
    request fails, or the reply carries an error, returns None instead of
    raising - the goal \"what is the current media volume level\" is answered
    with absence, not a crash.
    """
    reply = _socket_send({"command": ["get_property", "volume"]})
    if not _reply_ok(reply):
        return None
    data = reply.get("data")
    if isinstance(data, (int, float)) and 0 <= data <= 100:
        return int(data)
    return None