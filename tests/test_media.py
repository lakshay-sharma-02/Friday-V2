"""media primitives with mocked socket/subprocess - no real mpv is ever
spawned. Covers the is_playing decision (core-idle + pause), reply
parsing, the orphan-sweep/pgrep helpers, and preconditions."""

from __future__ import annotations

import subprocess
import unittest
from unittest import mock

from friday.errors import PreconditionError, PrimitiveError
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


class TestLaunchAndWaitSocket(EnvTestCase):
    """The launch path: _wait_socket's probe loop and _launch's success /
    mpv-missing / socket-never-ready branches. Popen, the socket probe and
    builtins.open are all mocked - no real subprocess is ever spawned, no
    real /tmp/friday_mpv_stderr.log is ever written, nothing is signaled
    or killed."""

    # _launch builds stderr=open(MPV_STDERR_LOG, 'w') as a Popen argument,
    # which evaluates even when Popen is mocked - redirect it so the tests
    # never touch the real debug log.
    _OPEN = mock.patch("builtins.open", mock.mock_open())

    def test_wait_socket_true_when_probe_replies(self):
        with mock.patch.object(media, "_socket_send", return_value={"error": "success"}):
            self.assertTrue(media._wait_socket(timeout=0.2))

    def test_wait_socket_false_when_silent(self):
        with mock.patch.object(media, "_socket_send", return_value=None):
            self.assertFalse(media._wait_socket(timeout=0.05))

    def test_launch_mpv_missing_raises_and_leaves_proc(self):
        sentinel = mock.Mock()  # a pre-existing handle, e.g. a prior player
        with self._OPEN, mock.patch.object(media, "_proc", sentinel), \
             mock.patch.object(media.subprocess, "Popen", side_effect=FileNotFoundError):
            with self.assertRaises(PrimitiveError) as ctx:
                media._launch(["mpv"], "test")
            self.assertIs(media._proc, sentinel)  # unchanged by the failed launch
        self.assertIn("mpv binary not found", str(ctx.exception))

    def test_launch_success(self):
        proc = mock.Mock(pid=4242)
        with self._OPEN, mock.patch.object(media, "_proc", None), \
             mock.patch.object(media.subprocess, "Popen", return_value=proc), \
             mock.patch.object(media, "_wait_socket", return_value=True):
            out = media._launch(["mpv", "x"], "test")
            self.assertEqual(out, {"pid": 4242, "socket": media.SOCKET_PATH})
            self.assertIs(media._proc, proc)  # the live handle is kept for stop()

    def test_launch_socket_never_ready_stops_and_sweeps(self):
        proc = mock.Mock(pid=999)
        with self._OPEN, mock.patch.object(media, "_proc", None), \
             mock.patch.object(media.subprocess, "Popen", return_value=proc), \
             mock.patch.object(media, "_wait_socket", return_value=False), \
             mock.patch.object(media, "_stop_process") as stop, \
             mock.patch.object(media, "_sweep_orphans") as sweep:
            with self.assertRaises(PrimitiveError) as ctx:
                media._launch(["mpv", "x"], "test")
        self.assertIn("never became ready", str(ctx.exception))
        stop.assert_called_once_with(proc)  # the just-launched child is reaped
        sweep.assert_called_once()  # no listener may survive the failure
        self.assertIsNone(media._proc)  # no stale reference is kept


if __name__ == "__main__":
    unittest.main()
