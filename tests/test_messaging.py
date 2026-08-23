"""Messaging primitives: whatsapp's MIME allow-list, pre-network
preconditions of sends, and the incoming-media download flow. Every test
here fails BEFORE any HTTP request - no network is touched."""

from __future__ import annotations

import tempfile
import unittest
import unittest.mock
from pathlib import Path

from friday.errors import PreconditionError
from friday.l1 import discord, telegram, whatsapp
from tests.helpers import EnvTestCase


class TestWhatsapp(EnvTestCase):
    def test_mime_map(self):
        self.assertEqual(whatsapp._mime_for(Path("a.pdf")), "application/pdf")
        self.assertEqual(whatsapp._mime_for(Path("a.mp3")), "audio/mpeg")
        self.assertEqual(whatsapp._mime_for(Path("a.png")), "image/png")
        self.assertEqual(whatsapp._mime_for(Path("a.md")), "text/plain")

    def test_mime_unknown_raises(self):
        with self.assertRaises(PreconditionError):
            whatsapp._mime_for(Path("a.xyz"))

    def test_send_text_empty(self):
        with self.assertRaises(PreconditionError):
            whatsapp.send_text("")

    def test_send_text_bad_recipient(self):
        with self.assertRaises(PreconditionError):
            whatsapp.send_text("hi", to="not-a-number")

    def test_send_document_missing_file(self):
        with self.assertRaises(PreconditionError):
            whatsapp.send_document("/no/such/file.pdf", to="918396020807")

    def test_upload_document_missing_file(self):
        with self.assertRaises(PreconditionError):
            whatsapp.upload_document("/no/such/file.pdf")

    # --- download_media pre-network preconditions ---

    def test_get_media_url_empty(self):
        with self.assertRaises(PreconditionError):
            whatsapp.get_media_url("")

    def test_get_media_url_whitespace(self):
        with self.assertRaises(PreconditionError):
            whatsapp.get_media_url("   ")

    def test_download_media_empty_id(self):
        with self.assertRaises(PreconditionError):
            whatsapp.download_media("")

    def test_download_media_bad_dest(self):
        with self.assertRaises(PreconditionError):
            whatsapp.download_media("abc123", dest_dir="/no/such/dir")

    def test_download_media_missing_dest_file(self):
        """dest_dir must be an existing directory, not a file."""
        import tempfile
        with tempfile.NamedTemporaryFile() as f:
            with self.assertRaises(PreconditionError):
                whatsapp.download_media("abc123", dest_dir=f.name)

    def test_download_media_ext_for_mime(self):
        """The reverse MIME map covers common types."""
        self.assertEqual(whatsapp._EXT_FOR_MIME.get("image/jpeg"), ".jpg")
        self.assertEqual(whatsapp._EXT_FOR_MIME.get("video/mp4"), ".mp4")
        self.assertEqual(whatsapp._EXT_FOR_MIME.get("application/pdf"), ".pdf")

    @unittest.mock.patch("friday.l1.whatsapp.requests")
    def test_download_media_full_flow(self, mock_requests):
        """End-to-end mocked download: get_media_url -> download binary."""
        import tempfile

        # Mock get_media_url response
        url_resp = unittest.mock.Mock()
        url_resp.status_code = 200
        url_resp.json.return_value = {
            "url": "https://example.com/media/abc123",
            "mime_type": "image/png",
            "file_size": 1024,
            "id": "abc123",
        }

        # Mock download response
        dl_resp = unittest.mock.Mock()
        dl_resp.status_code = 200
        dl_resp.content = b"\x89PNG\r\n\x1a\n" + b"\x00" * 1000  # fake PNG
        dl_resp.headers = {"Content-Disposition": 'filename="photo.png"'}

        mock_requests.get.side_effect = [url_resp, dl_resp]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = whatsapp.download_media("abc123", dest_dir=tmpdir)
            self.assertEqual(result["filename"], "photo.png")
            self.assertEqual(result["mime_type"], "image/png")
            self.assertEqual(result["file_size"], len(dl_resp.content))
            self.assertTrue(Path(result["path"]).exists())
            self.assertEqual(Path(result["path"]).read_bytes(), dl_resp.content)

    @unittest.mock.patch("friday.l1.whatsapp.requests")
    def test_download_media_fallback_filename(self, mock_requests):
        """When Content-Disposition is absent, fallback uses media_id + ext."""
        import tempfile

        url_resp = unittest.mock.Mock()
        url_resp.status_code = 200
        url_resp.json.return_value = {
            "url": "https://example.com/media/xyz789",
            "mime_type": "application/pdf",
            "file_size": 500,
            "id": "xyz789",
        }

        dl_resp = unittest.mock.Mock()
        dl_resp.status_code = 200
        dl_resp.content = b"%PDF-1.4 fake"
        dl_resp.headers = {}  # no Content-Disposition

        mock_requests.get.side_effect = [url_resp, dl_resp]

        with tempfile.TemporaryDirectory() as tmpdir:
            result = whatsapp.download_media("xyz789", dest_dir=tmpdir)
            self.assertEqual(result["filename"], "xyz789.pdf")
            self.assertTrue(Path(result["path"]).exists())

    @unittest.mock.patch("friday.l1.whatsapp.requests")
    def test_get_media_url_api_error(self, mock_requests):
        """get_media_url raises PrimitiveError on non-200."""
        from friday.errors import PrimitiveError

        resp = unittest.mock.Mock()
        resp.status_code = 404
        resp.text = "Media not found"
        mock_requests.get.return_value = resp

        with self.assertRaises(PrimitiveError):
            whatsapp.get_media_url("bad_id")

    @unittest.mock.patch("friday.l1.whatsapp.requests")
    def test_get_media_url_no_url_in_response(self, mock_requests):
        """get_media_url raises PrimitiveError when url is missing."""
        from friday.errors import PrimitiveError

        resp = unittest.mock.Mock()
        resp.status_code = 200
        resp.json.return_value = {"id": "abc"}  # no url
        resp.text = '{"id": "abc"}'
        mock_requests.get.return_value = resp

        with self.assertRaises(PrimitiveError):
            whatsapp.get_media_url("abc")

    # --- enqueue / pending media queue ---

    def test_enqueue_empty_media_id(self):
        with self.assertRaises(PreconditionError):
            whatsapp.enqueue_media_for_download("")

    def test_enqueue_and_load(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            pending_file = Path(tmpdir) / "pending.json"
            self.set_env(FRIDAY_WHATSAPP_PENDING_FILE=str(pending_file))
            result = whatsapp.enqueue_media_for_download(
                "media123", sender="+1234567890", media_type="image"
            )
            self.assertEqual(result["status"], "enqueued")
            self.assertEqual(result["pending_count"], 1)
            loaded = whatsapp.load_pending_media()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["media_id"], "media123")
            self.assertEqual(loaded[0]["sender"], "+1234567890")

    def test_enqueue_deduplicates(self):
        import json

        with tempfile.TemporaryDirectory() as tmpdir:
            pending_file = Path(tmpdir) / "pending.json"
            self.set_env(FRIDAY_WHATSAPP_PENDING_FILE=str(pending_file))
            whatsapp.enqueue_media_for_download("media123")
            result2 = whatsapp.enqueue_media_for_download("media123")
            self.assertEqual(result2["status"], "already_enqueued")
            loaded = whatsapp.load_pending_media()
            self.assertEqual(len(loaded), 1)

    def test_enqueue_multiple(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pending_file = Path(tmpdir) / "pending.json"
            self.set_env(FRIDAY_WHATSAPP_PENDING_FILE=str(pending_file))
            whatsapp.enqueue_media_for_download("m1")
            whatsapp.enqueue_media_for_download("m2")
            whatsapp.enqueue_media_for_download("m3")
            loaded = whatsapp.load_pending_media()
            self.assertEqual(len(loaded), 3)
            self.assertEqual(loaded[0]["media_id"], "m1")
            self.assertEqual(loaded[2]["media_id"], "m3")

    def test_clear_pending_media_all(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pending_file = Path(tmpdir) / "pending.json"
            self.set_env(FRIDAY_WHATSAPP_PENDING_FILE=str(pending_file))
            whatsapp.enqueue_media_for_download("m1")
            whatsapp.enqueue_media_for_download("m2")
            whatsapp.clear_pending_media()
            loaded = whatsapp.load_pending_media()
            self.assertEqual(len(loaded), 0)

    def test_clear_pending_media_selective(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            pending_file = Path(tmpdir) / "pending.json"
            self.set_env(FRIDAY_WHATSAPP_PENDING_FILE=str(pending_file))
            whatsapp.enqueue_media_for_download("m1")
            whatsapp.enqueue_media_for_download("m2")
            whatsapp.enqueue_media_for_download("m3")
            whatsapp.clear_pending_media(["m1", "m3"])
            loaded = whatsapp.load_pending_media()
            self.assertEqual(len(loaded), 1)
            self.assertEqual(loaded[0]["media_id"], "m2")

    def test_load_pending_media_empty_on_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            self.set_env(
                FRIDAY_WHATSAPP_PENDING_FILE=str(Path(tmpdir) / "nonexistent.json")
            )
            loaded = whatsapp.load_pending_media()
            self.assertEqual(loaded, [])


class TestTelegram(EnvTestCase):
    def test_send_text_empty(self):
        with self.assertRaises(PreconditionError):
            telegram.send_text("")

    def test_send_document_missing_file(self):
        with self.assertRaises(PreconditionError):
            telegram.send_document("/no/such/file")


class TestTelegramReceive(EnvTestCase):
    def test_poll_updates_empty(self):
        """poll_updates returns empty list when no new messages."""
        import tempfile
        from unittest.mock import patch, Mock

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"ok": True, "result": []}

        with tempfile.TemporaryDirectory() as tmpdir:
            self.set_env(
                FRIDAY_TELEGRAM_OFFSET_FILE=str(Path(tmpdir) / "offset.json"),
                TELEGRAM_BOT_TOKEN="test_token",
            )
            with patch("friday.l1.telegram.requests.get", return_value=mock_resp):
                from friday.l1.telegram import poll_updates
                msgs = poll_updates()
            self.assertEqual(msgs, [])

    def test_poll_updates_extracts_media(self):
        """poll_updates extracts photo messages with file_id."""
        import tempfile
        from unittest.mock import patch, Mock

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": True,
            "result": [{
                "update_id": 100,
                "message": {
                    "message_id": 1,
                    "chat": {"id": 123456},
                    "date": 1700000000,
                    "from": {"username": "testuser"},
                    "photo": [
                        {"file_id": "small", "file_unique_id": "s"},
                        {"file_id": "large", "file_unique_id": "l"},
                    ],
                    "caption": "test image",
                },
            }],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            self.set_env(
                FRIDAY_TELEGRAM_OFFSET_FILE=str(Path(tmpdir) / "offset.json"),
                TELEGRAM_BOT_TOKEN="test_token",
            )
            with patch("friday.l1.telegram.requests.get", return_value=mock_resp):
                from friday.l1.telegram import poll_updates
                msgs = poll_updates()
            self.assertEqual(len(msgs), 1)
            self.assertEqual(msgs[0]["file_id"], "large")  # largest photo
            self.assertEqual(msgs[0]["media_type"], "photo")
            self.assertEqual(msgs[0]["caption"], "test image")
            self.assertEqual(msgs[0]["from"], "testuser")

    def test_poll_updates_skips_text_messages(self):
        """Text-only messages are skipped (nothing to download)."""
        import tempfile
        from unittest.mock import patch, Mock

        mock_resp = Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "ok": True,
            "result": [{
                "update_id": 100,
                "message": {
                    "message_id": 1,
                    "chat": {"id": 123456},
                    "date": 1700000000,
                    "text": "hello",
                },
            }],
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            self.set_env(
                FRIDAY_TELEGRAM_OFFSET_FILE=str(Path(tmpdir) / "offset.json"),
                TELEGRAM_BOT_TOKEN="test_token",
            )
            with patch("friday.l1.telegram.requests.get", return_value=mock_resp):
                from friday.l1.telegram import poll_updates
                msgs = poll_updates()
            self.assertEqual(msgs, [])

    def test_download_file_full_flow(self):
        """End-to-end mocked download: getFile -> download binary."""
        import tempfile
        from unittest.mock import patch, Mock

        file_info_resp = Mock()
        file_info_resp.status_code = 200
        file_info_resp.json.return_value = {
            "ok": True,
            "result": {"file_path": "documents/file_123.pdf"},
        }

        dl_resp = Mock()
        dl_resp.status_code = 200
        dl_resp.content = b"%PDF-1.4 fake content"

        with tempfile.TemporaryDirectory() as tmpdir:
            self.set_env(
                TELEGRAM_BOT_TOKEN="test_token",
            )
            with patch("friday.l1.telegram.requests.get") as mock_get:
                mock_get.side_effect = [file_info_resp, dl_resp]
                from friday.l1.telegram import download_file
                result = download_file("abc123", dest_dir=tmpdir, filename="test.pdf")
            self.assertEqual(result["filename"], "test.pdf")
            self.assertEqual(result["file_size"], len(dl_resp.content))
            self.assertTrue(Path(result["path"]).exists())

    def test_download_file_empty_id(self):
        from friday.errors import PreconditionError
        from friday.l1.telegram import download_file
        with self.assertRaises(PreconditionError):
            download_file("")

    def test_download_file_bad_dest(self):
        from friday.errors import PreconditionError
        from friday.l1.telegram import download_file
        with self.assertRaises(PreconditionError):
            download_file("abc123", dest_dir="/no/such/dir")


class TestDiscord(EnvTestCase):
    def test_send_text_empty(self):
        with self.assertRaises(PreconditionError):
            discord.send_text("")

    def test_send_file_missing(self):
        with self.assertRaises(PreconditionError):
            discord.send_file("/no/such/file")


if __name__ == "__main__":
    unittest.main()
