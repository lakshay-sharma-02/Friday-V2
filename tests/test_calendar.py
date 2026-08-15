"""calendar.list_upcoming (gate-registered 2026-08-13) - hermetic tests for
the 2026-08-14 auth fix: the original draft read a raw access_token that
expires in ~1 hour with no refresh path. The fix mirrors gmail.py's proven
pattern (client_id/client_secret/refresh_token in pass friday/calendar or
CALENDAR_* env, refresh grant, cached token, 401 -> refresh + retry) and
makes auth failure raise PrimitiveError - DISTINCT from 'no upcoming
events', which is an empty list, so an unconfigured calendar can never
masquerade as a free week."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from friday import l1
from friday.l1 import calendar
from friday.errors import PrimitiveError

from tests.helpers import EnvTestCase


class TestAuth(EnvTestCase):
    """The refresh-grant flow: _auth pulls CALENDAR_* env or the pass entry
    friday/calendar; _access_token refreshes via the grant and caches."""

    def setUp(self) -> None:
        super().setUp()
        # the module-level token cache persists across tests in this
        # process - a token cached by one test would short-circuit _auth
        # in the next (gmail's tests never hit this because they always
        # mock _access_token; ours exercise the real flow)
        calendar._token_cache.update({"access_token": None, "expires_at": 0.0})

    def test_missing_credentials_raise(self):
        with mock.patch("friday.l1.calendar.get_credentials", side_effect=PrimitiveError("no pass")):
            with self.assertRaises(PrimitiveError) as ctx:
                calendar._access_token()
        self.assertIn("credentials missing", str(ctx.exception))

    def test_env_credentials_refresh_and_cache(self):
        self.set_env(
            CALENDAR_CLIENT_ID="cid",
            CALENDAR_CLIENT_SECRET="csec",
            CALENDAR_REFRESH_TOKEN="rtok",
        )
        resp = mock.Mock(status_code=200)
        resp.json.return_value = {"access_token": "fresh", "expires_in": 3600}
        with mock.patch("friday.l1.calendar.requests.post", return_value=resp) as post:
            tok = calendar._access_token()
            tok2 = calendar._access_token()  # cached - no second call
        self.assertEqual(tok, "fresh")
        self.assertEqual(tok2, "fresh")
        self.assertEqual(post.call_count, 1)
        self.assertEqual(post.call_args.kwargs["data"]["grant_type"], "refresh_token")
        self.assertEqual(post.call_args.kwargs["data"]["refresh_token"], "rtok")

    def test_refresh_failure_raises(self):
        self.set_env(
            CALENDAR_CLIENT_ID="cid",
            CALENDAR_CLIENT_SECRET="csec",
            CALENDAR_REFRESH_TOKEN="rtok",
        )
        resp = mock.Mock(status_code=400, text="invalid_grant")
        with mock.patch("friday.l1.calendar.requests.post", return_value=resp):
            with self.assertRaises(PrimitiveError) as ctx:
                calendar._access_token()
        self.assertIn("token refresh failed", str(ctx.exception))


class TestListUpcoming(EnvTestCase):
    """list_upcoming against a mocked Calendar API: the auth + API call are
    mocked; event parsing, the 401-refresh-retry, empty-vs-error, and the
    log redaction are real."""

    @staticmethod
    def _events() -> dict:
        return {
            "items": [
                {
                    "id": "ev-1",
                    "summary": "Standup",
                    "start": {"dateTime": "2026-08-15T09:00:00Z"},
                    "end": {"dateTime": "2026-08-15T09:30:00Z"},
                    "location": "Zoom",
                    "attendees": [{"email": "a@x.com"}, {"email": "b@x.com"}],
                },
                {
                    "id": "ev-2",
                    "summary": "All-day",
                    "start": {"date": "2026-08-16"},
                    "end": {"date": "2026-08-17"},
                },
            ]
        }

    def test_returns_parsed_events(self):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = self._events()
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"), \
             mock.patch("friday.l1.calendar.requests.get", return_value=resp) as get:
            out = calendar.list_upcoming(days=7)
        self.assertEqual([e["event_id"] for e in out], ["ev-1", "ev-2"])
        self.assertEqual(out[0]["summary"], "Standup")
        self.assertEqual(out[0]["attendees_count"], "2")
        self.assertEqual(out[1]["start_time"], "2026-08-16")  # date-only events
        url = get.call_args.args[0]
        self.assertTrue(url.endswith("/calendars/primary/events"), url)
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer tok")
        self.assertIn("timeMin", get.call_args.kwargs["params"])

    def test_401_refreshes_once_and_retries(self):
        """A stale cached access token (expired ~1h) must not fail the call:
        one 401 -> refresh -> retry (mirrors gmail.py's _get)."""
        self.set_env(
            CALENDAR_CLIENT_ID="cid",
            CALENDAR_CLIENT_SECRET="csec",
            CALENDAR_REFRESH_TOKEN="rtok",
        )
        stale = mock.Mock(status_code=401, text="Invalid Credentials")
        good = mock.Mock(status_code=200)
        good.json.return_value = {"items": []}
        tok_resp = mock.Mock(status_code=200)
        tok_resp.json.return_value = {"access_token": "fresh", "expires_in": 3600}
        with mock.patch("friday.l1.calendar.requests.get",
                        side_effect=[stale, good]) as get, \
             mock.patch("friday.l1.calendar.requests.post", return_value=tok_resp):
            out = calendar.list_upcoming()
        self.assertEqual(out, [])
        self.assertEqual(get.call_count, 2)
        # the retry used the FRESH token
        self.assertEqual(get.call_args.kwargs["headers"]["Authorization"], "Bearer fresh")

    def test_api_error_raises_not_empty(self):
        resp = mock.Mock(status_code=403, text="calendar API not enabled")
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"), \
             mock.patch("friday.l1.calendar.requests.get", return_value=resp):
            with self.assertRaises(PrimitiveError) as ctx:
                calendar.list_upcoming()
        self.assertIn("calendar API error", str(ctx.exception))

    def test_invalid_days_raises_precondition(self):
        from friday.errors import PreconditionError

        with self.assertRaises(PreconditionError):
            calendar.list_upcoming(days=0)

    def test_summary_redacted_from_l0_log(self):
        """Event SUMMARY is metadata that could leak - the L0 result line
        must show <redacted> while event_id / times stay visible."""
        log = self.mktmp() / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(log))
        resp = mock.Mock(status_code=200)
        resp.json.return_value = self._events()
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"), \
             mock.patch("friday.l1.calendar.requests.get", return_value=resp):
            calendar.list_upcoming(days=7)
        lines = [json.loads(l) for l in open(log, encoding="utf-8").read().splitlines() if l.strip()]
        cal_line = [l for l in lines if l["primitive"] == "calendar.list_upcoming"][-1]
        self.assertEqual(cal_line["result"][0]["summary"], "<redacted>")
        self.assertEqual(cal_line["result"][0]["event_id"], "ev-1")
        self.assertNotIn("Standup", json.dumps(cal_line["result"]))


class TestAddEvent(EnvTestCase):
    """calendar.add_event (gate-registered 2026-08-14) - hermetic tests:
    parameter validation (RFC 3339 parsing, end-after-start, empty
    summary) and the scope guard (a 403 from a readonly-only token is
    surfaced as an actionable PrimitiveError naming the consent re-run,
    not a generic API failure)."""

    def setUp(self) -> None:
        super().setUp()
        calendar._token_cache.update({"access_token": None, "expires_at": 0.0})

    def _post(self, status: int, text: str) -> mock.Mock:
        resp = mock.Mock(status_code=status, text=text)
        return resp

    def test_creates_event(self):
        resp = self._post(200, "")
        resp.json.return_value = {
            "id": "ev-9", "status": "confirmed",
            "start": {"dateTime": "2026-08-15T09:00:00Z"},
            "end": {"dateTime": "2026-08-15T09:30:00Z"},
        }
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"), \
             mock.patch("friday.l1.calendar.requests.post", return_value=resp) as post:
            out = calendar.add_event("Standup", "2026-08-15T09:00:00Z", "2026-08-15T09:30:00Z")
        self.assertEqual(out["event_id"], "ev-9")
        self.assertEqual(out["summary"], "Standup")
        self.assertEqual(post.call_args.kwargs["headers"]["Authorization"], "Bearer tok")
        self.assertEqual(post.call_args.kwargs["json"]["summary"], "Standup")

    def test_empty_summary_rejected(self):
        from friday.errors import PreconditionError

        with self.assertRaises(PreconditionError):
            calendar.add_event("  ", "2026-08-15T09:00:00Z", "2026-08-15T09:30:00Z")

    def test_end_before_start_rejected_across_offsets(self):
        """The 2026-08-14 hand-fix: an END of '14:00+05:30' vs a START of
        '10:00Z' must compare by INSTANT, not as strings - 14:00+05:30 is
        08:30Z, which is BEFORE 10:00Z, so the end is before the start and
        PreconditionError must be raised (a naive string comparison would
        wrongly accept it: '10:00Z' < '14:00+05:30')."""
        from friday.errors import PreconditionError

        with self.assertRaises(PreconditionError):
            calendar.add_event("Late", "2026-08-15T10:00:00Z", "2026-08-15T14:00:00+05:30")

    def test_garbage_datetime_rejected(self):
        from friday.errors import PreconditionError

        with self.assertRaises(PreconditionError):
            calendar.add_event("Bad", "not-a-date", "2026-08-15T10:00:00Z")

    def test_403_readonly_scope_is_actionable(self):
        """The scope guard (2026-08-15): a 403 'Insufficient Permission'
        means the refresh token only carries calendar.readonly - the error
        must name the fix (re-run consent with the events scope), never a
        generic 'failed (403)'."""
        resp = self._post(403, "{\"error\": {\"message\": \"Insufficient Permission\"}}")
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"), \
             mock.patch("friday.l1.calendar.requests.post", return_value=resp):
            with self.assertRaises(PrimitiveError) as ctx:
                calendar.add_event("X", "2026-08-15T09:00:00Z", "2026-08-15T09:30:00Z")
        msg = str(ctx.exception)
        self.assertIn("calendar.events", msg)
        self.assertIn("_calendar_oauth_setup.py --scope", msg)
        self.assertIn("missing calendar.events scope", ctx.exception.state)

    def test_403_unrelated_is_generic(self):
        """A 403 that is NOT a scope problem (e.g. calendar API disabled)
        stays a generic failure - the scope guard must not over-claim."""
        resp = self._post(403, "calendar API not enabled for this project")
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"), \
             mock.patch("friday.l1.calendar.requests.post", return_value=resp):
            with self.assertRaises(PrimitiveError) as ctx:
                calendar.add_event("X", "2026-08-15T09:00:00Z", "2026-08-15T09:30:00Z")
        self.assertIn("calendar.add_event failed (403)", str(ctx.exception))
        self.assertNotIn("calendar.events", str(ctx.exception))

    def test_500_api_error_raises(self):
        resp = self._post(500, "internal error")
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"), \
             mock.patch("friday.l1.calendar.requests.post", return_value=resp):
            with self.assertRaises(PrimitiveError) as ctx:
                calendar.add_event("X", "2026-08-15T09:00:00Z", "2026-08-15T09:30:00Z")
        self.assertIn("calendar.add_event failed (500)", str(ctx.exception))
