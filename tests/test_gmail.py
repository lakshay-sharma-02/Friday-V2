"""gmail internals (pure functions - no network/auth): the log-time
redaction transform for list_unread results, header extraction, and the
summarize flow with mocked get_message + LLM subprocess."""

from __future__ import annotations

import base64
import json
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from friday.errors import PreconditionError, PrimitiveError
from friday.l1 import dev, gmail
from friday.l1.gmail import _header, _log_redact_mail_meta
from tests.helpers import EnvTestCase


class TestLogRedactMailMeta(unittest.TestCase):
    def test_redacts_sender_and_subject_keeps_ids(self):
        rows = [
            {
                "message_id": "m1",
                "sender": "Google <x@accounts.google.com>",
                "subject": "Security alert",
                "date": "Sat",
            },
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
        payload = {
            "headers": [{"name": "From", "value": "x@y"}, {"name": "Subject", "value": "hi"}]
        }
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
                {
                    "mimeType": "text/html",
                    "body": {"data": base64.urlsafe_b64encode(b"<b>html</b>").decode()},
                },
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
        base = {
            "message_id": "m1",
            "sender": "a@b",
            "subject": "Subj",
            "date": "D",
            "snippet": "",
            "body": "Hello body",
        }
        base.update(kw)
        return base

    @contextmanager
    def _patched(self, llm_result, msg=None):
        with (
            mock.patch("friday.l1.gmail.get_message", return_value=msg or self._msg()) as gm,
            mock.patch("friday.l1.dev._run_claude", return_value=llm_result) as rc,
        ):
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
        with self._patched({"result": "   "}), self.assertRaises(PrimitiveError) as ctx:
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


class TestSendDocument(EnvTestCase):
    """gmail.send_document (gate-registered 2026-08-11): the capability-gap
    loop's first SIDE-EFFECTING primitive, hand-built and human-signed.
    Hermetic: the Gmail API POST and the token refresh are mocked; the MIME
    assembly is real (a temp file is attached and the raw message is decoded
    back and asserted on). The RECIPIENT must never reach the L0 result line
    (mail-metadata redaction, same discipline as list_unread's log_transform)
    while message_id stays visible for tracing."""

    def _pdf(self) -> Path:
        d = self.mktmp(prefix="friday_send_")
        p = d / "receipt.pdf"
        p.write_bytes(b"%PDF-1.4 fake content for the hermetic test")
        return p

    @staticmethod
    def _resp(status: int = 200, body: dict | None = None) -> mock.Mock:
        r = mock.Mock(status_code=status, text="mock API error body")
        r.json.return_value = body or {"id": "msg-1", "threadId": "th-1"}
        return r

    def test_sends_attachment_and_returns_meta(self):
        pdf = self._pdf()
        with (
            mock.patch("friday.l1.gmail._access_token", return_value="tok"),
            mock.patch("friday.l1.gmail.requests.post", return_value=self._resp()) as post,
        ):
            out = gmail.send_document(str(pdf), to="me@example.com", subject="Receipt", body="hi")
        self.assertEqual(out["message_id"], "msg-1")
        self.assertEqual(out["thread_id"], "th-1")
        self.assertEqual(out["to"], "me@example.com")
        self.assertEqual(out["filename"], "receipt.pdf")
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertTrue(url.endswith("/users/me/messages/send"), url)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tok")
        decoded = base64.urlsafe_b64decode(kwargs["json"]["raw"] + "===").decode("utf-8")
        self.assertIn("receipt.pdf", decoded)
        self.assertIn("Subject: Receipt", decoded)

    def test_recipient_redacted_from_l0_result_line(self):
        """The RECIPIENT is mail metadata - the result line in
        var/logs/friday.jsonl must show <redacted>, never the address;
        message_id stays visible so the trace identifies the send."""
        log = self.mktmp() / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))
        with (
            mock.patch("friday.l1.gmail._access_token", return_value="tok"),
            mock.patch("friday.l1.gmail.requests.post", return_value=self._resp()),
        ):
            gmail.send_document(str(self._pdf()), to="me@example.com")
        lines = [
            json.loads(l) for l in open(log, encoding="utf-8").read().splitlines() if l.strip()
        ]
        send_line = [l for l in lines if l["primitive"] == "gmail.send_document"][-1]
        self.assertEqual(send_line["result"]["to"], "<redacted>")
        self.assertEqual(send_line["result"]["message_id"], "msg-1")
        self.assertNotIn("me@example.com", json.dumps(send_line["result"]))

    def test_missing_file_raises_precondition(self):
        with mock.patch("friday.l1.gmail._access_token", return_value="tok"):
            with self.assertRaises(PreconditionError):
                gmail.send_document("/no/such/file.pdf", to="me@example.com")

    def test_empty_to_raises(self):
        """An empty `to` must raise BEFORE any network call. `_default_to`
        is also patched: a real pass `default_to` entry (stored during the
        2026-08-11 re-consent) would otherwise resolve the empty string to
        a real recipient and the send would proceed to an unmocked HTTP
        POST - this test must stay hermetic against live pass state."""
        with (
            mock.patch("friday.l1.gmail._access_token", return_value="tok"),
            mock.patch("friday.l1.gmail._default_to", return_value=None),
        ):
            with self.assertRaises(PreconditionError):
                gmail.send_document(str(self._pdf()), to="")

    def test_default_recipient_env(self):
        with (
            mock.patch.dict("os.environ", {"GMAIL_DEFAULT_TO": "self@example.com"}),
            mock.patch("friday.l1.gmail._access_token", return_value="tok"),
            mock.patch("friday.l1.gmail.requests.post", return_value=self._resp()),
        ):
            out = gmail.send_document(str(self._pdf()))
        self.assertEqual(out["to"], "self@example.com")

    def test_api_error_surfaces_primitive_error(self):
        with (
            mock.patch("friday.l1.gmail._access_token", return_value="tok"),
            mock.patch("friday.l1.gmail.requests.post", return_value=self._resp(403)),
        ):
            with self.assertRaises(PrimitiveError) as ctx:
                gmail.send_document(str(self._pdf()), to="me@example.com")
        self.assertIn("403", str(ctx.exception))

    def test_registered_in_registry_as_at_most_once(self):
        from friday.contracts import REGISTRY

        c = REGISTRY["gmail.send_document"]
        self.assertEqual(c.idempotency.value, "at-most-once")


if __name__ == "__main__":
    unittest.main()
