#!/usr/bin/env python
"""Inspect how the `claude` CLI on this machine is authenticated and
routed - WITHOUT ever printing a secret. Values of anything key/token-like
are masked; env var names and base URLs are shown (base URLs are not
credentials)."""

from __future__ import annotations

import json
import os
import pathlib
import subprocess
import sys

home = pathlib.Path.home()

print("=== claude CLI ===")
print(subprocess.run(["which", "claude"], capture_output=True, text=True).stdout.strip())
ver = subprocess.run(["claude", "--version"], capture_output=True, text=True)
print(ver.stdout.strip() or ver.stderr.strip())

print("\n=== auth-related env vars (values masked) ===")
hits = sorted(
    k for k in os.environ
    if any(s in k.lower() for s in ("anthropic", "openrouter", "claude", "api_key", "apikey", "base_url"))
)
for k in hits:
    v = os.environ[k]
    low = k.lower()
    if "base_url" in low or "url" in low or "proxy" in low:
        print(f"ENV {k} = {v}")  # base URLs are not secrets
    else:
        print(f"ENV {k} = <set, {len(v)} chars, masked>")
if not hits:
    print("(no auth env vars set)")

print("\n=== claude config files ===")
for p in (home / ".claude" / "settings.json",
          home / ".config" / "claude" / "settings.json",
          home / ".claude.json"):
    if p.exists():
        print(f"--- {p} ---")
        try:
            data = json.loads(p.read_text())
        except json.JSONDecodeError as exc:
            print(f"  (unparseable: {exc})")
            continue

        def mask(obj: object, indent: int = 0) -> None:
            pad = "  " * indent
            if isinstance(obj, dict):
                for k, v in obj.items():
                    low = str(k).lower()
                    if isinstance(v, (dict, list)):
                        print(f"{pad}{k}:")
                        mask(v, indent + 1)
                    elif isinstance(v, str) and any(
                        s in low for s in ("key", "token", "secret", "password", "oauth")
                    ):
                        print(f"{pad}{k} = <masked, {len(v)} chars>")
                    elif isinstance(v, str) and any(
                        s in low for s in ("url", "proxy", "model", "base")
                    ):
                        print(f"{pad}{k} = {v}")
                    else:
                        print(f"{pad}{k} = {v}")
            elif isinstance(obj, list):
                for i, v in enumerate(obj):
                    mask({f"[{i}]": v}, indent)

        mask(data)
    else:
        print(f"--- {p} (absent) ---")

print("\n=== claude config get (auth-relevant, masked) ===")
for key in ("apiKeyHelper", "baseUrl", "model", "env", "proxy"):
    r = subprocess.run(["claude", "config", "get", key], capture_output=True, text=True)
    out = (r.stdout or r.stderr).strip()
    if out:
        low = out.lower()
        if any(s in low for s in ("sk-", "key", "token", "secret")) and len(out) > 20:
            print(f"{key}: <masked>")
        else:
            print(f"{key}: {out[:120]}")
    else:
        print(f"{key}: (unset)")

sys.exit(0)
