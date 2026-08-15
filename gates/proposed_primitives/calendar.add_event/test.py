import unittest
from unittest import mock
from friday.l1 import calendar
from friday.errors import PreconditionError, PrimitiveError
from tests.helpers import EnvTestCase

class TestAddEvent(EnvTestCase):
    @staticmethod
    def _event_response() -> dict:
        return {
            "id": "created-event-123",
            "summary": "Meeting",
            "start": {"dateTime": "2026-08-15T14:00:00Z"},
            "end": {"dateTime": "2026-08-15T15:00:00Z"},
            "status": "confirmed",
        }

    def test_creates_event_and_returns_metadata(self):
        resp = mock.Mock(status_code=200)
        resp.json.return_value = self._event_response()
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"), \
             mock.patch("friday.l1.calendar.requests.post", return_value=resp) as post:
            out = calendar.add_event(
                summary="Meeting",
                start="2026-08-15T14:00:00Z",
                end="2026-08-15T15:00:00Z",
            )
        self.assertEqual(out["event_id"], "created-event-123")
        self.assertEqual(out["summary"], "Meeting")
        url = post.call_args.args[0]
        self.assertTrue(url.endswith("/calendars/primary/events"), url)
        body = post.call_args.kwargs["json"]
        self.assertEqual(body["summary"], "Meeting")

    def test_empty_summary_raises_precondition(self):
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"):
            with self.assertRaises(PreconditionError):
                calendar.add_event(summary="  ", start="2026-08-15T14:00:00Z", end="2026-08-15T15:00:00Z")

    def test_end_before_start_raises_precondition(self):
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"):
            with self.assertRaises(PreconditionError):
                calendar.add_event(summary="Meeting", start="2026-08-15T15:00:00Z", end="2026-08-15T14:00:00Z")

    def test_api_error_raises_primitive_error(self):
        resp = mock.Mock(status_code=403)
        resp.text = "insufficient scopes"
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"), \
             mock.patch("friday.l1.calendar.requests.post", return_value=resp):
            with self.assertRaises(PrimitiveError):
                calendar.add_event(summary="Meeting", start="2026-08-15T14:00:00Z", end="2026-08-15T15:00:00Z")

    def test_mixed_timezone_compares_by_instant(self):
        # hand-correction 2026-08-14: 14:00+05:30 IS after 10:00Z (14:00+05:30
        # == 08:30Z) - a string comparison would wrongly say 14:00 > 10:00 and
        # pass, but the reverse case below must be REJECTED by instant
        resp = mock.Mock(status_code=200)
        resp.json.return_value = self._event_response()
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"), \
             mock.patch("friday.l1.calendar.requests.post", return_value=resp):
            out = calendar.add_event(
                summary="Meeting",
                start="2026-08-15T14:00:00+05:30",
                end="2026-08-15T10:00:00Z",
            )
        self.assertEqual(out["event_id"], "created-event-123")
        # end earlier by instant -> PreconditionError, even though the STRING
        # '2026-08-15T14:00:00+05:30' > '2026-08-15T10:00:00Z' lexically
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"):
            with self.assertRaises(PreconditionError):
                calendar.add_event(
                    summary="Meeting",
                    start="2026-08-15T14:00:00+05:30",
                    end="2026-08-15T08:00:00Z",
                )

    def test_invalid_datetime_raises_precondition(self):
        # hand-correction 2026-08-14: garbage must be rejected, not compared
        with mock.patch("friday.l1.calendar._access_token", return_value="tok"):
            with self.assertRaises(PreconditionError):
                calendar.add_event(summary="Meeting", start="not-a-date", end="2026-08-15T15:00:00Z")