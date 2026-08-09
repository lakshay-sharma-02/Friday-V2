"""gmail internals (pure functions - no network/auth): the log-time
redaction transform for list_unread results, header extraction, and the
summarize flow with mocked get_message + LLM subprocess."""

from __future__ import annotations

import base64
import json
import unittest
from contextlib import contextmanager
from unittest import mock

from friday.errors import PrimitiveError
from friday.l1 import dev, gmail
from friday.l1.gmail import _header, _log_redact_mail_meta
from tests.helpers import EnvTestCase


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


class TestBodyText(unittest.TestCase):
    def test_single_part_body_decoded(self):
        data = base64.urlsafe_b64encode(b"hello world").decode()
        payload = {"body": {"data": data}}
        self.assertEqual(gmail._body_text(payload), "hello world")

    def test_multipart_prefers_text_plain(self):
        data = base64.urlsafe_b64encode(b"the plain part").decode()
        payload = {
            "parts": [
                {"mimeType": "text/html", "body": {"data": base64.urlsafe_b64encode(b"<b>html</b>").decode()}},
                {"mimeType": "text/plain", "body": {"data": data}},
            ]
        }
        self.assertEqual(gmail._body_text(payload), "the plain part")

    def test_no_body_returns_empty(self):
        self.assertEqual(gmail._body_text({"parts": []}), "")
        self.assertEqual(gmail._body_text({"body": {}}), "")

    def test_garbage_base64_returns_empty(self):
        # a lone data character can never form a full byte: urlsafe_b64decode
        # raises and _decode falls back to ''
        self.assertEqual(gmail._body_text({"body": {"data": "a"}}), "")


class TestSummarizeFlow(EnvTestCase):
    """gmail.summarize's internals, fully mocked - no network, no LLM.
    The body goes to the LLM subprocess by design, but must never appear
    in the L0 log (the redaction discipline from the Task-7 bring-up)."""

    def _msg(self, **kw):
        base = {"message_id": "m1", "sender": "a@b", "subject": "Subj",
                "date": "D", "snippet": "", "body": "Hello body"}
        base.update(kw)
        return base

    @contextmanager
    def _patched(self, llm_result, msg=None):
        with mock.patch("friday.l1.gmail.get_message", return_value=msg or self._msg()) as gm, \
             mock.patch("friday.l1.dev._run_claude", return_value=llm_result) as rc:
            yield gm, rc

    def test_summary_from_string_result(self):
        with self._patched({"result": "A summary."}) as (_, rc):
            self.assertEqual(gmail.summarize("m1"), "A summary.")
        args = rc.call_args.args
        self.assertIn("Hello body", args[0])  # the task carries the body to the LLM
        self.assertEqual(args[1:], (None, 120, dev.MODEL_ALIAS, False))  # no bypass, model alias

    def test_summary_from_dict_result(self):
        with self._patched({"result": {"summary": "Dict summary."}}):
            self.assertEqual(gmail.summarize("m1"), "Dict summary.")

    def test_message_without_body_or_snippet_raises(self):
        with self._patched({"result": "x"}, msg=self._msg(body="", snippet="")):
            with self.assertRaises(PrimitiveError) as ctx:
                gmail.summarize("m1")
        self.assertIn("no readable body or snippet", str(ctx.exception))

    def test_empty_llm_summary_raises(self):
        with self._patched({"result": "   "}):
            with self.assertRaises(PrimitiveError) as ctx:
                gmail.summarize("m1")
        self.assertIn("no usable summary", str(ctx.exception))

    def test_summary_body_never_reaches_l0_log(self):
        """Regression: the mail body is passed to the LLM subprocess, but
        the L0 log must only ever show the summarize call's message_id - a
        summarize() call must never leak mail content into friday.jsonl."""
        log = self.mktmp() / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))
        with self._patched({"result": "ok summary"}, msg=self._msg(body="SECRET MAIL BODY TEXT")):
            self.assertEqual(gmail.summarize("m1"), "ok summary")
        dump = open(log, encoding="utf-8").read()
        self.assertNotIn("SECRET MAIL BODY TEXT", dump)
        prims = [json.loads(l)["primitive"] for l in dump.splitlines() if l.strip()]
        self.assertEqual(prims.count("gmail.summarize"), 1)
        self.assertNotIn("dev.run", " ".join(prims))  # the internal _run_claude is unlogged


if __name__ == "__main__":
    unittest.main()
