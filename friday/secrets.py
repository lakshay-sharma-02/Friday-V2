"""Shared credential access (pass-backed).

The secrets mechanism for Friday: credentials live in `pass` at
`friday/<service>` as JSON, or two-line user/pass as a fallback. Every
primitive that needs secrets reads through here - never hardcoded, never
logged in plaintext.

Dead-import rule: this module is actually called by the browser login path
and the whatsapp API - it is not a decorative import.
"""

from __future__ import annotations

import json
import subprocess

from friday.errors import PrimitiveError


def get_credentials(service: str) -> dict[str, str]:
    proc = None
    try:
        proc = subprocess.run(
            ["pass", "show", f"friday/{service}"],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except FileNotFoundError as exc:
        raise PrimitiveError(
            "pass is not installed; install it with: sudo pacman -S pass",
            state="no credentials retrieved",
        ) from exc
    except subprocess.TimeoutExpired as exc:
        extra = f"; stderr: {proc.stderr.strip()}" if proc is not None else ""
        raise PrimitiveError(
            f"pass show friday/{service} timed out (GPG pinentry?){extra}",
            state="no credentials retrieved",
        ) from exc
    if proc.returncode != 0:
        raise PrimitiveError(
            f"pass show friday/{service} failed: {proc.stderr.strip() or 'no such entry'}",
            state="no credentials retrieved",
        )
    try:
        data = json.loads(proc.stdout)
        return {str(k): str(v) for k, v in data.items()}
    except json.JSONDecodeError:
        lines = [ln.strip() for ln in proc.stdout.strip().splitlines() if ln.strip()]
        if len(lines) >= 2:
            return {"username": lines[0], "password": lines[1]}
        raise PrimitiveError(
            f"friday/{service} entry is neither JSON nor two-line user/pass",
            state="no credentials parsed",
        ) from None
