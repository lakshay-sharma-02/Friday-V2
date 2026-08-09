"""gmail internals (pure functions - no network/auth): the log-time
redaction transform for list_unread results and header extraction."""

from __future__ import annotations

import unittest

from friday.l1.gmail import _header, _log_redact_mail_meta


class TestLogRedactMailMeta(unittest.TestCase):
    def test_redacts_sender_and_subject_keeps_ids(self):
        rows = [
            {"message_id": "m1", "sender": "Google <x@accounts.google.com>", "subject": "Security alert", "date": "Sat"},
            {"message_id": "m2", "sender": "a@b", "subject": "s", "date": "Sun"},
        ]
        out = _log_redact_mail_meta(rows)
        self.assertEqual(out[0]["sender"], "<redacted>")
        self.assertEqual(out[0]["subject"], "<redacted>")
        self.assertEqual(out[0]["message_id"], "m1")
        self.assertEqual(out[0]["date"], "Sat")
        self.assertEqual(len(out), 2)

    def test_non_list_passthrough(self):
        self.assertEqual(_log_redact_mail_meta("x"), "x")
        self.assertIsNone(_log_redact_mail_meta(None))

    def test_original_not_mutated(self):
        rows = [{"sender": "a@b", "subject": "s", "message_id": "m"}]
        _log_redact_mail_meta(rows)
        self.assertEqual(rows[0]["sender"], "a@b")  # transform copies, never mutates


class TestHeader(unittest.TestCase):
    def test_case_insensitive(self):
        payload = {"headers": [{"name": "From", "value": "x@y"}, {"name": "Subject", "value": "hi"}]}
        self.assertEqual(_header(payload, "from"), "x@y")
        self.assertEqual(_header(payload, "SUBJECT"), "hi")

    def test_missing_returns_empty(self):
        self.assertEqual(_header({"headers": []}, "From"), "")


if __name__ == "__main__":
    unittest.main()
