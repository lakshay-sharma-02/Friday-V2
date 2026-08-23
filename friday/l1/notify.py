"""L1 primitive: notify (desktop notifications).

POSIX: libnotify's notify-send is the standard Arch/Hyprland path for
desktop notifications. Windows (the 2026-08-17 port step): notify-send
does not exist, so a PowerShell NotifyIcon balloon is used instead. A
notification is the watch loop's way to tell the user a background goal
finished. Pure local side effect - no network, no state that a plan could
verify afterwards (notifications are fire-and-forget), so this primitive
is used mostly by the watcher and for goals whose deliverable IS the
notification itself.
"""

from __future__ import annotations

import os
import subprocess
from typing import Any

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError

NOTIFY_SEND = "notify-send"
DEFAULT_TIMEOUT_MS = 5000

# Module-level flag so tests can exercise the Windows branch on any host.
_IS_WINDOWS = os.name == "nt"


def _windows_cmd(title: str, body: str, timeout_ms: int) -> list[str]:
    """One PowerShell -STA command showing a NotifyIcon balloon. Single
    quotes are doubled (PowerShell's escape for embedded quotes)."""
    ps_title = title.replace("'", "''")
    ps_body = body.replace("'", "''")
    script = (
        "Add-Type -AssemblyName System.Windows.Forms; "
        "$n = New-Object System.Windows.Forms.NotifyIcon; "
        "$n.Icon = [System.Drawing.SystemIcons]::Information; "
        f"$n.BalloonTipTitle = '{ps_title}'; "
        f"$n.BalloonTipText = '{ps_body}'; "
        "$n.Visible = $true; "
        f"$n.ShowBalloonTip({int(timeout_ms)}); "
        "Start-Sleep -Milliseconds 500; $n.Dispose()"
    )
    return ["powershell", "-NoProfile", "-STA", "-Command", script]


@contract(
    precondition="notify-send is installed (libnotify) on POSIX, or PowerShell on "
    "Windows; title is non-empty.",
    postcondition="A desktop notification with the given title (and body, if any) is "
    "displayed. Makes no other state changes - notifications are "
    "fire-and-forget, so no L2 check can verify one.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,  # re-notifying is harmless
    failure_mode="PrimitiveError if the notifier is missing (install libnotify on "
    "POSIX) or exits non-zero; PreconditionError on empty title.",
    returns="dict: {title, body, sent}.",
)
def notify_send(title: str, body: str = "", timeout_ms: int = DEFAULT_TIMEOUT_MS) -> dict[str, Any]:
    if not title or not title.strip():
        raise PreconditionError("notify_send requires a non-empty title")
    if _IS_WINDOWS:
        cmd = _windows_cmd(title.strip(), body, timeout_ms)
    else:
        cmd = [NOTIFY_SEND, "-t", str(int(timeout_ms)), title.strip()]
        if body:
            cmd.append(body)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
    except FileNotFoundError as exc:
        raise PrimitiveError(
            "notify-send is not installed; install libnotify (sudo pacman -S libnotify)",
            state="no notification shown",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        raise PrimitiveError(
            "notify-send hung",
            state="notification status unknown",
        ) from exc
    if proc.returncode != 0:
        raise PrimitiveError(
            f"notify-send failed (rc={proc.returncode}): "
            f"{proc.stderr.strip() or proc.stdout.strip()}",
            state="no notification shown",
        )
    return {"title": title, "body": body, "sent": True}
