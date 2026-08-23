"""Shared credential access.

The secrets mechanism for Friday: credentials live in `pass` at
`friday/<service>` as JSON, or two-line user/pass as a fallback. Every
primitive that needs secrets reads through here - never hardcoded, never
logged in plaintext.

Portable env-var override (2026-08-17, the Windows-port step 1): `pass` is
POSIX-only, so any service can be configured through environment
variables instead - `{SERVICE}_CREDENTIALS` as a JSON dict (the pass-entry
shape) or `{SERVICE}_USERNAME` + `{SERVICE}_PASSWORD` (the two-line shape).
The env path is checked FIRST and returns None when unset, so the pass
store stays authoritative on Linux when no override exists. This unblocks
browser.login (e.g. GITHUB_USERNAME/GITHUB_PASSWORD) and the gmail/
calendar fallbacks on Windows without pass.

Dead-import rule: this module is actually called by the browser login path
and the whatsapp API - it is not a decorative import.
"""

from __future__ import annotations

import json
import os
import subprocess

from friday.errors import PrimitiveError


def _env_credentials(service: str) -> dict[str, str] | None:
    """Portable credential override via env vars (the pass shapes). Returns
    None when nothing is configured so the pass path stays authoritative."""
    prefix = service.upper()
    raw = os.environ.get(f"{prefix}_CREDENTIALS")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
        except json.JSONDecodeError:
            pass  # malformed JSON override -> fall through to pass
    user = os.environ.get(f"{prefix}_USERNAME")
    pwd = os.environ.get(f"{prefix}_PASSWORD")
    # both must be set - a half-configured pair silently shipping an empty
    # password to browser.login would be a footgun
    if user is not None and pwd is not None:
        return {"username": user, "password": pwd}
    return None


def get_credentials(service: str) -> dict[str, str]:
    env_creds = _env_credentials(service)
    if env_creds is not None:
        return env_creds
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
            "pass is not installed; install it with: sudo pacman -S pass, "
            f"or set the {service.upper()}_CREDENTIALS env var "
            "(JSON) to configure this service without pass",
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
