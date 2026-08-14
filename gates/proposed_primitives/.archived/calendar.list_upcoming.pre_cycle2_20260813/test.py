import unittest
from unittest import mock
from friday.l1.calendar import list_upcoming

class TestListUpcoming(unittest.TestCase):
    def setUp(self):
        self.mock_fetch = mock.patch('friday.l1.calendar.calendar.fetch_upcoming', return_value=[
            {"event_id": "1", "title": "Meeting", "start_date": "2026-08-12", "end_date": "2026-08-12"},
        ]).start()

    def tearDown(self):
        mock.patch.stopall()

    def test_successful(self):
        result = list_upcoming(days=3)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["title"], "Meeting")

    def test_empty(self):
        with mock.patch('friday.l1.calendar.calendar.fetch_upcoming', return_value=[]):
            result = list_upcoming(days=5)
            self.assertEqual(result, [])

    def test_invalid_days(self):
        with self.assertRaises(ValueError):
            list_upcoming(days=-1)

if __name__ == '__main__':
    unittest.main()