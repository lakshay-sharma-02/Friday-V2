import unittest
from unittest import mock

from friday.contracts import REGISTRY, Idempotency
from friday.errors import PreconditionError, PrimitiveError
from friday.l1 import calendar as cal_module


class CalendarListUpcomingSelfCheck(unittest.TestCase):
    def test_registered_in_registry(self):
        self.assertIn("calendar.list_upcoming", REGISTRY)

    def test_contract_idempotency_is_idempotent(self):
        c = REGISTRY["calendar.list_upcoming"]
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)

    def test_contract_name_has_exactly_one_dot(self):
        c = REGISTRY["calendar.list_upcoming"]
        parts = c.name.split(".")
        self.assertEqual(len(parts), 2)

    def test_default_days_is_7(self):
        import inspect
        sig = inspect.signature(cal_module.list_upcoming)
        default = sig.parameters.get("days").default
        self.assertEqual(default, 7)


class CalendarListUpcomingBehavior(unittest.TestCase):
    def test_invalid_days_raises_precondition_error(self):
        with self.assertRaises(PreconditionError):
            cal_module.list_upcoming(0)
        with self.assertRaises(PreconditionError):
            cal_module.list_upcoming(-1)
        with self.assertRaises(PreconditionError):
            cal_module.list_upcoming("seven")

    @mock.patch.dict("os.environ", {"GOOGLE_CALENDAR_TOKEN": "mock-token"})
    @mock.patch("requests.get")
    def test_returns_events_on_api_success(self, mock_get):
        mock_resp = mock.Mock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {
            "items": [
                {
                    "id": "event1",
                    "summary": "Team Meeting",
                    "start": {"dateTime": "2026-08-14T10:00:00Z"},
                    "end": {"dateTime": "2026-08-14T11:00:00Z"},
                    "location": "Room 1",
                    "attendees": [{"email": "a@b.com"}, {"email": "c@d.com"}],
                }
            ]
        }
        mock_get.return_value = mock_resp
        result = cal_module.list_upcoming(7)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["event_id"], "event1")
        self.assertEqual(result[0]["summary"], "Team Meeting")

    @mock.patch.dict("os.environ", {})
    def test_returns_empty_list_without_credentials(self):
        """No credentials means no events returned (not an error)."""
        result = cal_module.list_upcoming(7)
        self.assertEqual(result, [])

    @mock.patch.dict("os.environ", {"GOOGLE_CALENDAR_TOKEN": "mock-token"})
    @mock.patch("requests.get")
    def test_api_failure_raises_primitive_error(self, mock_get):
        mock_resp = mock.Mock()
        mock_resp.status_code = 403
        mock_resp.text = "Insufficient permissions"
        mock_get.return_value = mock_resp
        with self.assertRaises(PrimitiveError) as ctx:
            cal_module.list_upcoming(7)
        self.assertIn("calendar API error", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
