"""Messaging primitives: whatsapp's MIME allow-list and the pre-network
preconditions of whatsapp/telegram/discord sends. Every test here fails
BEFORE any HTTP request - no network is touched."""

from __future__ import annotations

import unittest
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


class TestTelegram(EnvTestCase):
    def test_send_text_empty(self):
        with self.assertRaises(PreconditionError):
            telegram.send_text("")

    def test_send_document_missing_file(self):
        with self.assertRaises(PreconditionError):
            telegram.send_document("/no/such/file")


class TestDiscord(EnvTestCase):
    def test_send_text_empty(self):
        with self.assertRaises(PreconditionError):
            discord.send_text("")

    def test_send_file_missing(self):
        with self.assertRaises(PreconditionError):
            discord.send_file("/no/such/file")


if __name__ == "__main__":
    unittest.main()
