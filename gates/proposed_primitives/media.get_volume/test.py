from __future__ import annotations

from unittest import mock

from friday.l1 import media
from tests.helpers import EnvTestCase


class TestGetVolume(EnvTestCase):
    def test_returns_volume_when_player_replies(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "success", "data": 65,
        }):
            self.assertEqual(media.get_volume(), 65)

    def test_coerces_float_volume_to_int(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "success", "data": 42.9,
        }):
            self.assertEqual(media.get_volume(), 42)
            self.assertIsInstance(media.get_volume(), int)

    def test_no_player_returns_none(self):
        with mock.patch.object(media, "_socket_send", return_value=None):
            self.assertIsNone(media.get_volume())

    def test_ipc_error_returns_none(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "property not found",
        }):
            self.assertIsNone(media.get_volume())

    def test_missing_data_key_returns_none(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "success",
        }):
            self.assertIsNone(media.get_volume())

    def test_out_of_range_data_returns_none(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "success", "data": 150,
        }):
            self.assertIsNone(media.get_volume())

    def test_non_numeric_data_returns_none(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "success", "data": "unknown",
        }):
            self.assertIsNone(media.get_volume())

    def test_is_idempotent_no_socket_side_effect(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "success", "data": 30,
        }) as sock:
            media.get_volume()
            media.get_volume()
            sock.assert_called_with({"command": ["get_property", "volume"]})


if __name__ == "__main__":
    import unittest
    unittest.main()
