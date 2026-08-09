"""L2 checks: read-only semantics exercised through mocked accessors
(no real hyprctl/browser/network), the double-observe regression (one L2
line per call), and the pure message_sent validator."""

from __future__ import annotations

import json
import os
import unittest
from unittest import mock

from friday import observability as obs
from friday.errors import PrimitiveError
from friday.l2 import checks
from tests.helpers import EnvTestCase


class TestPureChecks(EnvTestCase):
    def test_file_exists(self):
        d = self.mktmp()
        (d / "a.txt").write_text("x", encoding="utf-8")
        self.assertTrue(checks.file_exists(str(d / "a.txt")))
        self.assertFalse(checks.file_exists(str(d / "missing.txt")))

    def test_message_sent_whatsapp(self):
        self.assertTrue(checks.message_sent("whatsapp", "wamid.HBgABC"))
        self.assertFalse(checks.message_sent("whatsapp", ""))

    def test_message_sent_telegram(self):
        self.assertTrue(checks.message_sent("telegram", "12345"))
        self.assertFalse(checks.message_sent("telegram", "abc"))

    def test_message_sent_discord(self):
        self.assertTrue(checks.message_sent("discord", "12345678901234567"))  # 17 digits
        self.assertFalse(checks.message_sent("discord", "123"))

    def test_message_sent_unknown_platform(self):
        self.assertFalse(checks.message_sent("myspace", "123"))


class TestWindowChecks(EnvTestCase):
    CLIENTS = [
        {"class": "kitty", "title": "term", "workspace": {"id": 1}},
        {"class": "firefox", "title": "web", "workspace": {"id": 2}},
    ]

    def setUp(self):
        super().setUp()
        self._patch = mock.patch.object(checks.window, "list_clients", return_value=list(self.CLIENTS))
        self._patch.start()
        self.addCleanup(self._patch.stop)

    def test_window_client_count(self):
        self.assertEqual(checks.window_client_count(), 2)

    def test_window_has_class_substring(self):
        self.assertTrue(checks.window_has_class("firefox"))
        self.assertFalse(checks.window_has_class("brave"))

    def test_window_only_classes(self):
        self.assertTrue(checks.window_only_classes(["kitty", "firefox"]))
        self.assertFalse(checks.window_only_classes(["kitty"]))

    def test_window_on_workspace(self):
        self.assertTrue(checks.window_on_workspace("firefox", 2))
        self.assertFalse(checks.window_on_workspace("firefox", 1))

    def test_window_only_classes_vacuous_on_empty(self):
        with mock.patch.object(checks.window, "list_clients", return_value=[]):
            self.assertTrue(checks.window_only_classes([]))


class TestBrowserChecks(EnvTestCase):
    def test_browser_has_text(self):
        with mock.patch.object(checks, "read_page_text", return_value="Hello Example Domain"):
            self.assertTrue(checks.browser_has_text("Example Domain"))
            self.assertFalse(checks.browser_has_text("Nope"))

    def test_browser_has_text_no_page_is_false(self):
        def raise_no_page():
            raise PrimitiveError("no browser page; call goto() first", state="no browser running")

        with mock.patch.object(checks, "read_page_text", side_effect=raise_no_page):
            self.assertFalse(checks.browser_has_text("anything"))

    def test_browser_has_text_real_error_propagates(self):
        def raise_other():
            raise PrimitiveError("context died", state="x")

        with mock.patch.object(checks, "read_page_text", side_effect=raise_other):
            with self.assertRaises(PrimitiveError):
                checks.browser_has_text("x")

    def test_browser_input_has_value_direct(self):
        fake = mock.Mock()
        fake.input_value.return_value = "typed"
        with mock.patch.object(checks, "find_locator", return_value=fake):
            self.assertTrue(checks.browser_input_has_value("field", "typed"))
            self.assertFalse(checks.browser_input_has_value("field", "other"))

    def test_browser_input_has_value_wrapper_path(self):
        outer = mock.Mock()
        outer.input_value.side_effect = Exception("not an input")
        inner = mock.Mock()
        inner.input_value.return_value = "v"
        outer.locator.return_value.first = inner
        with mock.patch.object(checks, "find_locator", return_value=outer):
            self.assertTrue(checks.browser_input_has_value("wrapper", "v"))


class TestMessagingChecks(EnvTestCase):
    def test_whatsapp_identity_ok(self):
        with mock.patch.object(checks, "whatsapp_identity", return_value="1555"):
            self.assertTrue(checks.whatsapp_identity_ok())


class TestGmailChecks(EnvTestCase):
    def test_gmail_unread_exists(self):
        with mock.patch.object(checks, "gmail_unread", return_value=[{"message_id": "1"}]):
            self.assertTrue(checks.gmail_unread_exists("a@b"))

    def test_gmail_message_matches(self):
        with mock.patch.object(checks, "gmail_message", return_value={"sender": "Google <no-reply@accounts.google.com>"}):
            self.assertTrue(checks.gmail_message_matches("m1", "accounts.google.com"))
            self.assertFalse(checks.gmail_message_matches("m1", "someone.else"))

    def test_gmail_unread_exists_emits_exactly_one_l2_line(self):
        """Regression for the duplicate @observe decorator bug: exactly one
        L2 line per call."""
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))
        with mock.patch.object(checks, "gmail_unread", return_value=[]):
            checks.gmail_unread_exists("a@b")
        n = sum(1 for l in open(log, encoding="utf-8")
                if json.loads(l).get("primitive") == "checks.gmail_unread_exists")
        self.assertEqual(n, 1)


class TestL2Observed(EnvTestCase):
    def test_checks_emit_l2_lines(self):
        d = self.mktmp()
        log = d / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))
        with mock.patch.object(checks.window, "list_clients", return_value=[]):
            checks.window_client_count()
        lines = [json.loads(l) for l in open(log, encoding="utf-8") if l.strip()]
        self.assertEqual(lines[0]["layer"], "L2")
        self.assertEqual(lines[0]["primitive"], "checks.window_client_count")


if __name__ == "__main__":
    unittest.main()
