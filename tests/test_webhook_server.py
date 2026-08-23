"""Webhook server: WhatsApp Cloud API payload parsing, HMAC signature
verification, and HTTP handler behavior. Every test is self-contained —
no network, no real HTTP server."""

from __future__ import annotations

import hashlib
import hmac
import json
import unittest
from io import BytesIO
from unittest import mock

from friday.webhook_server import (
    _extract_media_messages,
    _verify_signature,
)


class TestExtractMediaMessages(unittest.TestCase):
    """Parse WhatsApp Cloud API webhook payloads for media items."""

    def _payload(self, msg_type: str, media_id: str = "m1", **extra) -> dict:
        """Build a minimal webhook payload with one message."""
        media_obj = {"id": media_id, **extra}
        return {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "id": "wamid.test",
                            "type": msg_type,
                            msg_type: media_obj,
                        }]
                    }
                }]
            }]
        }

    def test_image_message(self):
        items = _extract_media_messages(self._payload("image", caption="hello"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["media_type"], "image")
        self.assertEqual(items[0]["media_id"], "m1")
        self.assertEqual(items[0]["sender"], "1234567890")
        self.assertEqual(items[0]["caption"], "hello")

    def test_document_message(self):
        items = _extract_media_messages(self._payload("document", filename="test.pdf"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["media_type"], "document")

    def test_audio_message(self):
        items = _extract_media_messages(self._payload("audio"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["media_type"], "audio")

    def test_video_message(self):
        items = _extract_media_messages(self._payload("video"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["media_type"], "video")

    def test_sticker_message(self):
        items = _extract_media_messages(self._payload("sticker"))
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["media_type"], "sticker")

    def test_text_message_skipped(self):
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "1234567890",
                            "id": "wamid.test",
                            "type": "text",
                            "text": {"body": "hello"},
                        }]
                    }
                }]
            }]
        }
        items = _extract_media_messages(payload)
        self.assertEqual(items, [])

    def test_empty_payload(self):
        items = _extract_media_messages({})
        self.assertEqual(items, [])

    def test_no_messages_in_payload(self):
        items = _extract_media_messages({"entry": [{"changes": [{"value": {}}]}]})
        self.assertEqual(items, [])

    def test_multiple_media_messages(self):
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [
                            {"from": "111", "id": "w1", "type": "image", "image": {"id": "m1"}},
                            {"from": "222", "id": "w2", "type": "document", "document": {"id": "m2"}},
                        ]
                    }
                }]
            }]
        }
        items = _extract_media_messages(payload)
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["media_id"], "m1")
        self.assertEqual(items[1]["media_id"], "m2")

    def test_media_id_missing_skipped(self):
        payload = {
            "entry": [{
                "changes": [{
                    "value": {
                        "messages": [{
                            "from": "111",
                            "id": "w1",
                            "type": "image",
                            "image": {"mime_type": "image/jpeg"},  # no id
                        }]
                    }
                }]
            }]
        }
        items = _extract_media_messages(payload)
        self.assertEqual(items, [])


class TestVerifySignature(unittest.TestCase):
    """HMAC-SHA256 signature verification for incoming webhooks."""

    def test_valid_signature(self):
        payload = b'{"test": "data"}'
        secret = "my_secret"
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        self.assertTrue(_verify_signature(payload, f"sha256={sig}", secret))

    def test_valid_signature_without_prefix(self):
        payload = b'{"test": "data"}'
        secret = "my_secret"
        sig = hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        self.assertTrue(_verify_signature(payload, sig, secret))

    def test_invalid_signature(self):
        payload = b'{"test": "data"}'
        self.assertFalse(_verify_signature(payload, "sha256=wrong", "secret"))

    def test_no_secret_allows_all(self):
        """When no app_secret is configured, all signatures pass."""
        self.assertTrue(_verify_signature(b"anything", "", ""))
        self.assertTrue(_verify_signature(b"anything", "bad", ""))

    def test_empty_payload(self):
        secret = "s"
        sig = hmac.new(secret.encode(), b"", hashlib.sha256).hexdigest()
        self.assertTrue(_verify_signature(b"", f"sha256={sig}", secret))


if __name__ == "__main__":
    unittest.main()
