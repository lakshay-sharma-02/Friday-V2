"""media primitives with mocked socket/subprocess - no real mpv is ever
spawned. Covers the is_playing decision (core-idle + pause), reply
parsing, the orphan-sweep/pgrep helpers, and preconditions."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from friday.errors import PreconditionError
from friday.l1 import media
from tests.helpers import EnvTestCase


class TestReplyOk(unittest.TestCase):
    def test_success(self):
        self.assertTrue(media._reply_ok({"error": "success"}))
        self.assertTrue(media._reply_ok({"error": None}))

    def test_failure_or_none(self):
        self.assertFalse(media._reply_ok({"error": "property not found"}))
        self.assertFalse(media._reply_ok(None))


class TestIsPlaying(EnvTestCase):
    def test_playing_when_not_idle_and_not_paused(self):
        with mock.patch.object(media, "_socket_send", side_effect=[
            {"error": "success", "data": False},  # core-idle False -> not idle
            {"error": "success", "data": False},  # pause False
        ]):
            self.assertTrue(media.is_playing())

    def test_idle_means_stopped(self):
        # is_playing still probes pause after an idle=True reply - both
        # replies must be provided.
        with mock.patch.object(media, "_socket_send", side_effect=[
            {"error": "success", "data": True},   # core-idle True -> stopped
            {"error": "success", "data": False},  # pause probe (still made)
        ]):
            self.assertFalse(media.is_playing())

    def test_paused_means_not_playing(self):
        with mock.patch.object(media, "_socket_send", side_effect=[
            {"error": "success", "data": False},
            {"error": "success", "data": True},  # pause True
        ]):
            self.assertFalse(media.is_playing())

    def test_no_player_returns_false(self):
        with mock.patch.object(media, "_socket_send", return_value=None):
            self.assertFalse(media.is_playing())


class TestPreconditions(EnvTestCase):
    def test_play_for_minutes_must_be_positive(self):
        with self.assertRaises(PreconditionError):
            media.play_for(0, "/tmp/x.mp3")

    def test_play_for_requires_source(self):
        with self.assertRaises(PreconditionError):
            media.play_for(1, "   ")

    def test_play_requires_source(self):
        with self.assertRaises(PreconditionError):
            media.play("")

    def test_set_volume_range(self):
        for bad in (-1, 101):
            with self.assertRaises(PreconditionError):
                media.set_volume(bad)
        with mock.patch.object(media, "_socket_send", return_value=None):
            media.set_volume(50)  # in range: no raise


class TestOrphanSweep(EnvTestCase):
    def test_pgrep_parses_pids(self):
        proc = mock.Mock(returncode=0, stdout="123\n456\n", stderr="")
        with mock.patch.object(media.subprocess, "run", return_value=proc):
            self.assertEqual(media._pgrep_socket(), [123, 456])

    def test_pgrep_timeout_returns_empty(self):
        with mock.patch.object(media.subprocess, "run", side_effect=subprocess.TimeoutExpired("pgrep", 5)):
            self.assertEqual(media._pgrep_socket(), [])

    def test_pgrep_missing_binary_returns_empty(self):
        with mock.patch.object(media.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(media._pgrep_socket(), [])

    def test_sweep_with_no_orphans_is_noop(self):
        # Pin _proc to None: _sweep_orphans would otherwise try to stop a
        # stale module-global player if a future test ever set one.
        with mock.patch.object(media, "_proc", None), \
             mock.patch.object(media, "_pgrep_socket", return_value=[]), \
             mock.patch.object(media.subprocess, "run", side_effect=FileNotFoundError):
            self.assertEqual(media._sweep_orphans(), [])


if __name__ == "__main__":
    unittest.main()
