# Hermetic tests for screenshot.capture - every external boundary is
# mocked (grim subprocess, hyprctl via window.list_clients), following
# the clipboard.read_text proposal's proven pattern (mock.Mock, never
# subprocess.CompletedProcess - the gate rejects that shape).
import unittest
from unittest import mock

from friday.contracts import REGISTRY, Idempotency
from friday.errors import PreconditionError, PrimitiveError, PrimitiveTimeout
from friday.l1 import screenshot as shot


class ScreenshotContract(unittest.TestCase):
    def test_registered_in_registry(self):
        self.assertIn("screenshot.capture", REGISTRY)

    def test_contract_idempotency_is_idempotent(self):
        self.assertEqual(REGISTRY["screenshot.capture"].idempotency, Idempotency.IDEMPOTENT)

    def test_contract_name_has_exactly_one_dot(self):
        self.assertEqual(len(REGISTRY["screenshot.capture"].name.split(".")), 2)


class ScreenshotFull(unittest.TestCase):
    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_full_capture_calls_grim_with_literal_argv(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        out = shot.capture(target="full", output_path="/tmp/shot.png")
        self.assertEqual(out, "/tmp/shot.png")
        mock_run.assert_called_once_with(
            ["grim", "/tmp/shot.png"], capture_output=True, timeout=shot.DEFAULT_TIMEOUT
        )

    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_full_capture_returns_default_path(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        out = shot.capture()
        self.assertEqual(out, shot.DEFAULT_OUTPUT)

    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_grim_failure_raises_primitive_error(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=1, stdout=b"", stderr=b"grim: no display")
        with self.assertRaises(PrimitiveError):
            shot.capture(output_path="/tmp/shot.png")

    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_grim_timeout_raises_primitive_timeout(self, mock_run):
        mock_run.side_effect = TimeoutError("grim timed out")
        with self.assertRaises(PrimitiveTimeout):
            shot.capture(output_path="/tmp/shot.png")

    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_grim_missing_raises_primitive_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("grim")
        with self.assertRaises(PrimitiveError):
            shot.capture(output_path="/tmp/shot.png")

    def test_relative_output_path_rejected(self):
        with self.assertRaises(PreconditionError):
            shot.capture(output_path="relative.png")

    def test_missing_output_dir_rejected(self):
        with self.assertRaises(PreconditionError):
            shot.capture(output_path="/nonexistent_dir_xyz/shot.png")


class ScreenshotWindow(unittest.TestCase):
    def _client(self, cls, title, at, size, address="0x1234"):
        return {
            "class": cls, "initialClass": cls, "title": title,
            "initialTitle": title, "at": at, "size": size, "address": address,
        }

    @mock.patch("friday.l1.screenshot.subprocess.run")
    @mock.patch("friday.l1.screenshot._window_geometry", return_value="1,39 1364x728")
    def test_window_capture_passes_geometry(self, mock_geom, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        out = shot.capture(target="kitty", output_path="/tmp/term.png")
        self.assertEqual(out, "/tmp/term.png")
        mock_run.assert_called_once_with(
            ["grim", "-g", "1,39 1364x728", "/tmp/term.png"],
            capture_output=True, timeout=shot.DEFAULT_TIMEOUT,
        )

    # The impl resolves geometry by importing window.list_clients /
    # get_active_window INSIDE the function (lazy import), so the mock
    # must patch the SOURCE module (friday.l1.window), not an attribute
    # on the screenshot module.
    @mock.patch("friday.l1.window.get_active_window")
    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_active_window_uses_active_geometry(self, mock_run, mock_active):
        mock_active.return_value = self._client("kitty", "term", [0, 0], [800, 600])
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        out = shot.capture(target="active", output_path="/tmp/a.png")
        self.assertEqual(out, "/tmp/a.png")
        mock_run.assert_called_once_with(
            ["grim", "-g", "0,0 800x600", "/tmp/a.png"],
            capture_output=True, timeout=shot.DEFAULT_TIMEOUT,
        )

    @mock.patch("friday.l1.window.get_active_window", return_value=None)
    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_active_window_none_raises_precondition(self, mock_run, mock_active):
        with self.assertRaises(PreconditionError):
            shot.capture(target="active", output_path="/tmp/a.png")

    @mock.patch("friday.l1.window.list_clients")
    def test_missing_selector_raises_precondition(self, mock_clients):
        mock_clients.return_value = [self._client("kitty", "term", [0, 0], [800, 600])]
        with self.assertRaises(PreconditionError):
            shot.capture(target="firefox", output_path="/tmp/x.png")


if __name__ == "__main__":
    unittest.main()
