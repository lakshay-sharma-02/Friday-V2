from __future__ import annotations

import unittest
from unittest import mock

from friday.l1 import media
from tests.helpers import EnvTestCase


class TestGetPlayingTitle(EnvTestCase):
    def test_returns_title_when_player_responds(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "success",
            "data": "Never Gonna Give You Up",
        }):
            self.assertEqual(media.get_playing_title(), "Never Gonna Give You Up")

    def test_returns_none_when_no_player(self):
        with mock.patch.object(media, "_socket_send", return_value=None):
            self.assertIsNone(media.get_playing_title())

    def test_returns_none_on_ipc_error(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "property not found",
        }):
            self.assertIsNone(media.get_playing_title())

    def test_returns_none_on_empty_title(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "success",
            "data": "",
        }):
            self.assertIsNone(media.get_playing_title())

    def test_returns_none_on_non_string_title(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "success",
            "data": 42,
        }):
            self.assertIsNone(media.get_playing_title())

    def test_returns_none_on_whitespace_title(self):
        with mock.patch.object(media, "_socket_send", return_value={
            "error": "success",
            "data": "   ",
        }):
            self.assertIsNone(media.get_playing_title())


if __name__ == "__main__":
    unittest.main()