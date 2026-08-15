"""screenshot.capture (gate-registered 2026-08-15) - hermetic tests: the
full/active/selector capture modes against mocked grim + hyprctl, the
precondition guards, and the CAPTURE subprocess shape in the automated
gate (literal allowlisted tool binary + runtime args; everything else
still rejected)."""

from __future__ import annotations

import unittest
from unittest import mock

from friday.contracts import REGISTRY, Idempotency
from friday.errors import PreconditionError, PrimitiveError, PrimitiveTimeout
from friday.l1 import screenshot as shot


class TestContract(unittest.TestCase):
    def test_registered_in_registry(self):
        self.assertIn("screenshot.capture", REGISTRY)
        self.assertEqual(
            REGISTRY["screenshot.capture"].idempotency, Idempotency.IDEMPOTENT
        )


class TestFullCapture(unittest.TestCase):
    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_full_uses_literal_grim_argv(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        out = shot.capture(target="full", output_path="/tmp/shot.png")
        self.assertEqual(out, "/tmp/shot.png")
        mock_run.assert_called_once_with(
            ["grim", "/tmp/shot.png"], capture_output=True, timeout=shot.DEFAULT_TIMEOUT
        )

    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_default_path_when_omitted(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        self.assertEqual(shot.capture(), shot.DEFAULT_OUTPUT)

    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_grim_failure_raises(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=1, stdout=b"", stderr=b"no display")
        with self.assertRaises(PrimitiveError):
            shot.capture(output_path="/tmp/shot.png")

    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_grim_timeout_raises_primitive_timeout(self, mock_run):
        mock_run.side_effect = TimeoutError("grim hung")
        with self.assertRaises(PrimitiveTimeout):
            shot.capture(output_path="/tmp/shot.png")

    def test_relative_output_path_rejected(self):
        with self.assertRaises(PreconditionError):
            shot.capture(output_path="shot.png")

    def test_missing_output_dir_rejected(self):
        with self.assertRaises(PreconditionError):
            shot.capture(output_path="/no_such_dir_xyz/shot.png")


class TestWindowCapture(unittest.TestCase):
    @staticmethod
    def _client(cls, title, at, size, address="0x1234"):
        return {
            "class": cls, "initialClass": cls, "title": title,
            "initialTitle": title, "at": at, "size": size, "address": address,
        }

    @mock.patch("friday.l1.screenshot.subprocess.run")
    @mock.patch("friday.l1.screenshot._window_geometry", return_value="1,39 1364x728")
    def test_selector_passes_geometry(self, mock_geom, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        out = shot.capture(target="kitty", output_path="/tmp/term.png")
        mock_run.assert_called_once_with(
            ["grim", "-g", "1,39 1364x728", "/tmp/term.png"],
            capture_output=True, timeout=shot.DEFAULT_TIMEOUT,
        )
        self.assertEqual(out, "/tmp/term.png")

    @mock.patch("friday.l1.window.get_active_window")
    @mock.patch("friday.l1.screenshot.subprocess.run")
    def test_active_window_phrasing_maps_to_active(self, mock_run, mock_active):
        """The LLM says 'active window' (the goal phrasing) - the impl must
        normalize it to the active-window geometry, not treat it as a
        window selector."""
        mock_active.return_value = self._client("kitty", "term", [0, 0], [800, 600])
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        out = shot.capture(target="active window", output_path="/tmp/a.png")
        mock_run.assert_called_once_with(
            ["grim", "-g", "0,0 800x600", "/tmp/a.png"],
            capture_output=True, timeout=shot.DEFAULT_TIMEOUT,
        )
        self.assertEqual(out, "/tmp/a.png")

    @mock.patch("friday.l1.window.get_active_window", return_value=None)
    def test_no_active_window_raises_precondition(self, mock_active):
        with self.assertRaises(PreconditionError):
            shot.capture(target="active", output_path="/tmp/a.png")

    @mock.patch("friday.l1.window.list_clients")
    def test_missing_selector_raises_precondition(self, mock_clients):
        mock_clients.return_value = [self._client("kitty", "term", [0, 0], [800, 600])]
        with self.assertRaises(PreconditionError):
            shot.capture(target="firefox", output_path="/tmp/x.png")


class TestGateCaptureShape(unittest.TestCase):
    """The CAPTURE subprocess shape the gate admits for screenshot-class
    primitives (2026-08-15): a literal allowlisted tool binary as the
    FIRST argv element with runtime args after it - and nothing else."""

    def _check(self, src):
        from friday.automated_gate import check_danger

        return check_danger(src)

    def test_literal_tool_with_runtime_args_allowed(self):
        src = (
            "import subprocess\n"
            "def capture(geom: str, out: str) -> str:\n"
            '    p = subprocess.run(["grim", "-g", geom, out], capture_output=True, timeout=10)\n'
            "    return out\n"
        )
        self.assertEqual(self._check(src), [])

    def test_non_allowlisted_tool_rejected(self):
        """bash/python/rm with runtime args is the shell-escape the gate
        exists to block - the CAPTURE shape requires an allowlisted tool."""
        src = (
            "import subprocess\n"
            "def f(cmd: str) -> str:\n"
            '    p = subprocess.run(["bash", "-c", cmd], capture_output=True, timeout=10)\n'
            "    return p.stdout\n"
        )
        self.assertTrue(self._check(src), "bash -c must stay rejected")

    def test_variable_first_element_rejected(self):
        src = (
            "import subprocess\n"
            "def f(tool: str, out: str) -> str:\n"
            '    p = subprocess.run([tool, out], capture_output=True, timeout=10)\n'
            "    return out\n"
        )
        self.assertTrue(self._check(src))

    def test_capture_shape_requires_timeout(self):
        src = (
            "import subprocess\n"
            "def capture(out: str) -> str:\n"
            '    p = subprocess.run(["grim", out], capture_output=True)\n'
            "    return out\n"
        )
        self.assertTrue(self._check(src))


if __name__ == "__main__":
    unittest.main()
