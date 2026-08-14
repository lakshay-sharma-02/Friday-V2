"""Hermetic unit tests for the gmail.send_document proposal.

No network, no credentials: the Gmail API POST and the token refresh are
mocked; the MIME assembly is REAL (a temp file is attached and the raw
message is decoded back and asserted on). Runs inside the automated
gate's sandbox (temp HOME, stripped credentials) against the DRAFT impl.

Patching note: the sandbox injects the draft impl as a DETACHED namespace
copy (dict(vars(module)) -> exec), so mock.patch on the module attribute
`friday.l1.gmail._access_token` mutates the module but never reaches the
draft function's own globals. `requests.post` IS patchable normally (the
requests module object is shared), but the token function must be swapped
in the ORIGINAL function's globals directly. Two subtleties: (1) @contract
wraps primitives with functools.wraps, so the exported send_document's
__globals__ is the observability module's dict - the original function is
send_document.__wrapped__; (2) that original's __globals__ is the draft's
detached namespace in the sandbox (and the real module dict in the live
suite), so mutating it works identically in both. _patched_token does
this.
"""

from __future__ import annotations

import base64
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from unittest import mock

from friday.errors import PreconditionError, PrimitiveError
from friday.l1.gmail import send_document

_MISSING = object()


def _draft_globals() -> dict:
    """The ORIGINAL (unwrapped) function's globals - see the patching note."""
    inner = getattr(send_document, "__wrapped__", send_document)
    return inner.__globals__


@contextmanager
def _patched_token(value: str = "tok"):
    g = _draft_globals()
    prev = g.get("_access_token", _MISSING)
    g["_access_token"] = lambda: value
    try:
        yield
    finally:
        if prev is _MISSING:
            g.pop("_access_token", None)
        else:
            g["_access_token"] = prev


def _resp(status: int = 200, body: dict | None = None) -> mock.Mock:
    r = mock.Mock(status_code=status, text="mock API error body")
    r.json.return_value = body or {"id": "msg-1", "threadId": "th-1"}
    return r


class TestSendDocument(unittest.TestCase):
    def _pdf(self) -> Path:
        d = Path(tempfile.mkdtemp(prefix="friday_send_"))
        p = d / "receipt.pdf"
        p.write_bytes(b"%PDF-1.4 fake content for the hermetic test")
        return p

    def test_sends_attachment_and_returns_meta(self):
        pdf = self._pdf()
        with _patched_token(), \
             mock.patch("friday.l1.gmail.requests.post", return_value=_resp()) as post:
            out = send_document(
                str(pdf), to="me@example.com", subject="Receipt", body="hi"
            )
        self.assertEqual(out["message_id"], "msg-1")
        self.assertEqual(out["thread_id"], "th-1")
        self.assertEqual(out["to"], "me@example.com")
        self.assertEqual(out["filename"], "receipt.pdf")
        # the POST hit the send endpoint with a Bearer token and the MIME
        # raw message - decode it back and prove the attachment rode along
        url = post.call_args.args[0]
        kwargs = post.call_args.kwargs
        self.assertTrue(url.endswith("/users/me/messages/send"), url)
        self.assertEqual(kwargs["headers"]["Authorization"], "Bearer tok")
        raw = kwargs["json"]["raw"]
        decoded = base64.urlsafe_b64decode(raw + "===").decode("utf-8")
        self.assertIn("receipt.pdf", decoded)
        self.assertIn("Subject: Receipt", decoded)
        self.assertIn("To: me@example.com", decoded)

    def test_default_recipient_env(self):
        pdf = self._pdf()
        with mock.patch.dict("os.environ", {"GMAIL_DEFAULT_TO": "self@example.com"}), \
             _patched_token(), \
             mock.patch("friday.l1.gmail.requests.post", return_value=_resp()) as post:
            out = send_document(str(pdf))
        self.assertEqual(out["to"], "self@example.com")
        self.assertIsNone(post.call_args.kwargs["json"].get("to"))

    def test_missing_file_raises_precondition(self):
        with _patched_token():
            with self.assertRaises(PreconditionError):
                send_document("/no/such/file.pdf", to="me@example.com")

    def test_empty_to_raises(self):
        with _patched_token():
            with self.assertRaises(PreconditionError):
                send_document(str(self._pdf()), to="")

    def test_api_error_surfaces_primitive_error(self):
        pdf = self._pdf()
        with _patched_token(), \
             mock.patch(
                 "friday.l1.gmail.requests.post",
                 return_value=_resp(403, {"error": {"message": "scope"}}),
             ):
            with self.assertRaises(PrimitiveError) as ctx:
                send_document(str(pdf), to="me@example.com")
        self.assertIn("403", str(ctx.exception))

    def test_log_transform_redacts_recipient_keeps_message_id(self):
        from friday.l1.gmail import _log_redact_send_meta

        out = _log_redact_send_meta(
            {"message_id": "m1", "thread_id": "t1", "to": "me@example.com", "filename": "f.pdf"}
        )
        self.assertEqual(out["to"], "<redacted>")
        self.assertEqual(out["message_id"], "m1")
        self.assertEqual(out["filename"], "f.pdf")


if __name__ == "__main__":
    unittest.main()
