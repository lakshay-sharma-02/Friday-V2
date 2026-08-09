#!/usr/bin/env python
"""ONE-TIME Gmail OAuth setup (Phase 2 Task #10 prerequisite).

Runs the installed-app OAuth consent flow for the Gmail API (scope
gmail.readonly ONLY - this integration is read-only by design), exchanges
the authorization code for tokens, and stores the three values that
friday/l1/gmail.py needs into pass at `friday/gmail`:

    {"client_id": ..., "client_secret": ..., "refresh_token": ...}

Prerequisites (done once in the browser, steps you must complete first):
  1. console.cloud.google.com -> create a project (or pick one).
  2. APIs & Services -> Library -> "Gmail API" -> Enable.
  3. APIs & Services -> OAuth consent screen -> External -> add YOUR email
     as a test user. (Scopes are requested at runtime: gmail.readonly.)
  4. APIs & Services -> Credentials -> Create credentials -> OAuth client
     ID -> Application type: Desktop app -> Create -> Download JSON.

Usage:
  ./.venv/bin/python -u gates/_gmail_oauth_setup.py /path/to/credentials.json

After it prints confirmation, verify with:
  pass show friday/gmail
then continue with the bring-up and the task runner.

The client_secret is NEVER printed. The refresh_token is printed once
(the whole point of this step is to obtain it) and stored in pass.
"""
from __future__ import annotations

import json
import subprocess
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
PORTS = [8765, 8766, 8767, 8080]


def load_client_credentials() -> tuple[str, str]:
    if len(sys.argv) > 1:
        raw = json.loads(Path(sys.argv[1]).read_text())
        inst = raw.get("installed") or raw.get("web") or raw
        return inst["client_id"], inst["client_secret"]
    import os
    cid, csec = os.environ.get("GMAIL_CLIENT_ID"), os.environ.get("GMAIL_CLIENT_SECRET")
    if cid and csec:
        return cid, csec
    print("usage: _gmail_oauth_setup.py /path/to/credentials.json  "
          "(or set GMAIL_CLIENT_ID + GMAIL_CLIENT_SECRET)", flush=True)
    sys.exit(2)


def catch_code(port: int) -> str:
    captured: dict[str, str] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            q = parse_qs(urlsplit(self.path).query)
            captured["code"] = q.get("code", [""])[0]
            captured["error"] = q.get("error", [""])[0]
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.end_headers()
            body = (b"<html><body><h2>Friday received the code.</h2>"
                    b"<p>You can close this window and return to the terminal.</p></body></html>")
            self.wfile.write(body)

        def log_message(self, *args) -> None:  # silence default logging
            pass

    server = HTTPServer(("127.0.0.1", port), Handler)
    deadline = time.time() + 300  # 5 minutes to approve
    while time.time() < deadline:
        server.handle_request()
        if captured.get("code") or captured.get("error"):
            break
    server.server_close()
    if captured.get("error"):
        raise RuntimeError(f"OAuth consent returned an error: {captured['error']}")
    return captured.get("code", "")


def exchange(client_id: str, client_secret: str, code: str, redirect_uri: str) -> dict:
    resp = requests.post(
        TOKEN_URL,
        data={
            "grant_type": "authorization_code",
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise RuntimeError(f"token exchange failed ({resp.status_code}): {resp.text[:300]}")
    return resp.json()


def store_in_pass(client_id: str, client_secret: str, refresh_token: str) -> None:
    entry = json.dumps({
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
    })
    try:
        subprocess.run(
            ["pass", "insert", "-m", "friday/gmail"],
            input=entry + "\n", text=True, capture_output=True, timeout=15, check=True,
        )
        print("stored in pass at friday/gmail (verify: pass show friday/gmail)", flush=True)
    except Exception as exc:  # noqa: BLE001 - any failure -> print the manual command
        print(f"pass insert failed ({type(exc).__name__}): {exc}", flush=True)
        print("store manually with:", flush=True)
        print(f"  pass insert -m friday/gmail  # then paste this JSON:", flush=True)
        print(entry, flush=True)


def main() -> None:
    client_id, client_secret = load_client_credentials()

    port = next(p for p in PORTS if not _port_in_use(p))
    redirect_uri = f"http://localhost:{port}/"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": SCOPE,
        "access_type": "offline",
        "prompt": "consent",
    }
    auth_url = f"{AUTH_URL}?{urlencode(params)}"
    print("=" * 72)
    print("GMAIL ONE-TIME OAUTH SETUP - read-only scope only (gmail.readonly)")
    print("=" * 72)
    print(f"scope       : {SCOPE}")
    print(f"redirect    : {redirect_uri}")
    print("opening the consent screen in your browser - approve it once...")
    webbrowser.open(auth_url)

    code = catch_code(port)
    if not code:
        print("FAILED: no authorization code received within 5 minutes. Re-run.", flush=True)
        sys.exit(1)

    tokens = exchange(client_id, client_secret, code, redirect_uri)
    refresh_token = tokens.get("refresh_token")
    if not refresh_token:
        print("FAILED: no refresh_token in exchange response. Did the consent screen "
              "request access_type=offline + prompt=consent?", flush=True)
        sys.exit(1)
    print(f"OK: access token obtained (expires in {tokens.get('expires_in')}s); "
          f"refresh token obtained: {refresh_token[:12]}...", flush=True)
    store_in_pass(client_id, client_secret, refresh_token)
    print("SETUP: DONE - friday/l1/gmail.py will now authenticate automatically "
          "(GMAIL_CLIENT_ID/GMAIL_CLIENT_SECRET/GMAIL_REFRESH_TOKEN env vars "
          "override the pass entry).", flush=True)


def _port_in_use(port: int) -> bool:
    import socket
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
            return False
        except OSError:
            return True


if __name__ == "__main__":
    main()
