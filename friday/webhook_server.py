"""Webhook server for WhatsApp Cloud API incoming messages.

A lightweight HTTP server (stdlib only, no Flask/FastAPI dependency) that
receives WhatsApp Cloud API webhook POSTs and enqueues incoming media
(media_id + metadata) into the pending queue that the watcher's
whatsapp-media trigger polls.

WhatsApp Cloud API webhook flow:
  1. VERIFICATION (GET): Meta sends hub.mode=subscribe, hub.verify_token,
     hub.challenge. The server responds with the challenge if the token
     matches.
  2. MESSAGES (POST): Meta sends incoming message payloads. The server
     extracts media objects (image, document, audio, video, sticker) and
     calls enqueue_media_for_download() for each.

Usage:
  python -m friday.webhook_server                    # default port 8080
  python -m friday.webhook_server --port 9000        # custom port
  FRIDAY_WEBHOOK_PORT=9000 python -m friday.webhook_server

Env vars:
  FRIDAY_WEBHOOK_PORT       - listen port (default 8080)
  FRIDAY_WEBHOOK_VERIFY_TOKEN - the verify token you set in Meta's
                             dashboard (default: 'friday-verify-token')
  FRIDAY_WEBHOOK_APP_SECRET - (optional) app secret for HMAC-SHA256
                             signature verification of incoming POSTs
"""

from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer
from socketserver import ThreadingMixIn
from typing import Any

from friday.observability import emit_event

class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    """Handle each request in a new thread — prevents one slow client
    (like localtunnel's long-poll) from blocking all other requests."""
    daemon_threads = True


DEFAULT_PORT = 8080
DEFAULT_VERIFY_TOKEN = "friday-verify-token"

# Media types that contain a downloadable media_id
_MEDIA_TYPES = {"image", "document", "audio", "video", "sticker"}


def _extract_media_messages(body: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract media items from a WhatsApp Cloud API webhook payload.

    Returns a list of dicts with keys: media_id, sender, media_type, caption.
    Non-media messages (text, location, contacts, etc.) are silently skipped.
    """
    messages: list[dict[str, Any]] = []
    for entry in body.get("entry", []):
        for change in entry.get("changes", []):
            value = change.get("value", {})
            for msg in value.get("messages", []):
                msg_type = msg.get("type", "")
                if msg_type not in _MEDIA_TYPES:
                    continue
                media_obj = msg.get(msg_type, {})
                media_id = media_obj.get("id", "")
                if not media_id:
                    continue
                messages.append({
                    "media_id": media_id,
                    "sender": msg.get("from", ""),
                    "media_type": msg_type,
                    "caption": media_obj.get("caption", ""),
                })
    return messages


def _verify_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify the X-Hub-Signature-256 HMAC-SHA256 signature from Meta.

    Returns True if the signature is valid, False otherwise.
    If no secret is configured, always returns True (permissive mode).
    """
    if not secret:
        return True
    expected = hmac.new(
        secret.encode("utf-8"), payload, hashlib.sha256
    ).hexdigest()
    # Meta sends "sha256=<hex>" format
    if signature.startswith("sha256="):
        signature = signature[7:]
    return hmac.compare_digest(expected, signature)


class WebhookHandler(BaseHTTPRequestHandler):
    """HTTP handler for WhatsApp Cloud API webhooks."""

    verify_token: str = DEFAULT_VERIFY_TOKEN
    app_secret: str = ""

    def do_GET(self) -> None:
        """Handle webhook verification (Meta sends this on setup)."""
        from urllib.parse import parse_qs, urlparse

        parsed = urlparse(self.path)
        params = parse_qs(parsed.query)

        mode = params.get("hub.mode", [None])[0]
        token = params.get("hub.verify_token", [None])[0]
        challenge = params.get("hub.challenge", [None])[0]

        if mode == "subscribe" and token == self.verify_token and challenge:
            emit_event(
                layer="WEBHOOK",
                primitive="verify",
                args={"mode": mode},
                result="verified",
            )
            self._respond(200, challenge)
        else:
            emit_event(
                layer="WEBHOOK",
                primitive="verify",
                args={"mode": mode, "token_match": token == self.verify_token},
                result="rejected",
            )
            self._respond(403, "forbidden")

    def do_POST(self) -> None:
        """Handle incoming message webhooks."""
        content_length = int(self.headers.get("Content-Length", 0))
        raw_body = self.rfile.read(content_length)

        # Signature verification (if app_secret is configured)
        signature = self.headers.get("X-Hub-Signature-256", "")
        if self.app_secret and not _verify_signature(raw_body, signature, self.app_secret):
            emit_event(
                layer="WEBHOOK",
                primitive="receive",
                result="rejected",
                exception="invalid signature",
            )
            self._respond(403, "forbidden")
            return

        try:
            body = json.loads(raw_body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            emit_event(
                layer="WEBHOOK",
                primitive="receive",
                result="error",
                exception=f"bad JSON: {exc}",
            )
            self._respond(400, "bad request")
            return

        # Always acknowledge quickly — Meta retries on non-2xx
        self._respond(200, "ok")

        # Extract and enqueue media (after responding to avoid timeout)
        media_items = _extract_media_messages(body)
        if not media_items:
            return

        from friday.l1.whatsapp import enqueue_media_for_download

        enqueued = 0
        for item in media_items:
            try:
                result = enqueue_media_for_download(
                    media_id=item["media_id"],
                    sender=item["sender"],
                    media_type=item["media_type"],
                    caption=item["caption"],
                )
                if result.get("status") == "enqueued":
                    enqueued += 1
            except Exception as exc:
                emit_event(
                    layer="WEBHOOK",
                    primitive="enqueue",
                    args={"media_id": item["media_id"]},
                    result="error",
                    exception=f"{type(exc).__name__}: {exc}",
                )

        if enqueued:
            emit_event(
                layer="WEBHOOK",
                primitive="receive",
                args={"media_count": len(media_items)},
                result=f"enqueued {enqueued}",
            )

    def _respond(self, code: int, body: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(body.encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        """Suppress default stderr logging — we use L0 observability."""
        pass


def run_server(
    port: int = DEFAULT_PORT,
    verify_token: str = DEFAULT_VERIFY_TOKEN,
    app_secret: str = "",
) -> None:
    """Start the webhook server. Blocks until interrupted."""
    WebhookHandler.verify_token = verify_token
    WebhookHandler.app_secret = app_secret

    server = ThreadingHTTPServer(("0.0.0.0", port), WebhookHandler)
    emit_event(
        layer="WEBHOOK",
        primitive="server",
        args={"port": port, "verify_token_set": bool(verify_token)},
        result="START",
    )
    print(f"Friday webhook server listening on port {port}")
    print(f"  Verify token: {verify_token[:4]}...{verify_token[-4:]}" if len(verify_token) > 8 else f"  Verify token: {verify_token}")
    if app_secret:
        print("  App secret: configured (HMAC verification enabled)")
    else:
        print("  App secret: not set (HMAC verification disabled)")
    print("  Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        emit_event(layer="WEBHOOK", primitive="server", result="STOP")


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description="Friday WhatsApp webhook server")
    ap.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("FRIDAY_WEBHOOK_PORT", str(DEFAULT_PORT))),
        help="Port to listen on (default: $FRIDAY_WEBHOOK_PORT or 8080)",
    )
    ap.add_argument(
        "--verify-token",
        default=os.environ.get("FRIDAY_WEBHOOK_VERIFY_TOKEN", DEFAULT_VERIFY_TOKEN),
        help="Verify token for Meta webhook setup (default: $FRIDAY_WEBHOOK_VERIFY_TOKEN)",
    )
    ap.add_argument(
        "--app-secret",
        default=os.environ.get("FRIDAY_WEBHOOK_APP_SECRET", ""),
        help="App secret for HMAC signature verification (default: $FRIDAY_WEBHOOK_APP_SECRET)",
    )
    args = ap.parse_args(argv)
    run_server(args.port, args.verify_token, args.app_secret)


if __name__ == "__main__":
    main()
