# Hand-corrected after human review (2026-08-14): the LLM draft imported
# the wrong module path (friday.clipboard, no l1) and used
# subprocess.CompletedProcess to mock - the gate rejects that shape and
# the shipped convention is mock.Mock(returncode=..., stdout=...).
import unittest
from unittest import mock

from friday.contracts import REGISTRY, Idempotency
from friday.errors import PrimitiveError
from friday.l1 import clipboard as clip_module


class ClipboardReadTextSelfCheck(unittest.TestCase):
    def test_registered_in_registry(self):
        self.assertIn("clipboard.read_text", REGISTRY)

    def test_contract_idempotency_is_idempotent(self):
        c = REGISTRY["clipboard.read_text"]
        self.assertEqual(c.idempotency, Idempotency.IDEMPOTENT)

    def test_contract_name_has_exactly_one_dot(self):
        c = REGISTRY["clipboard.read_text"]
        self.assertEqual(len(c.name.split(".")), 2)


class ClipboardReadTextBehavior(unittest.TestCase):
    @mock.patch("friday.l1.clipboard.subprocess.run")
    def test_success_returns_stdout(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"hello world\n", stderr=b"")
        self.assertEqual(clip_module.read_text(), "hello world")

    @mock.patch("friday.l1.clipboard.subprocess.run")
    def test_empty_clipboard_returns_empty_string(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        self.assertEqual(clip_module.read_text(), "")

    @mock.patch("friday.l1.clipboard.subprocess.run")
    def test_tool_failure_raises_primitive_error(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=1, stdout=b"", stderr=b"no wayland")
        with self.assertRaises(PrimitiveError):
            clip_module.read_text()

    @mock.patch("friday.l1.clipboard.subprocess.run")
    def test_timeout_raises_primitive_error(self, mock_run):
        # subprocess.TimeoutExpired subclasses TimeoutError; raising the
        # base keeps this test free of subprocess.* constructor calls.
        mock_run.side_effect = TimeoutError("wl-paste timed out")
        with self.assertRaises(PrimitiveError):
            clip_module.read_text()

    @mock.patch("friday.l1.clipboard.subprocess.run")
    def test_wayland_session_uses_wl_paste_argv(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        with mock.patch.dict("os.environ", {"WAYLAND_DISPLAY": "wayland-0", "DISPLAY": ":0"}, clear=False):
            clip_module.read_text()
        mock_run.assert_called_once_with(["wl-paste"], capture_output=True, timeout=5)

    @mock.patch("friday.l1.clipboard.subprocess.run")
    def test_x11_session_uses_xclip_argv(self, mock_run):
        mock_run.return_value = mock.Mock(returncode=0, stdout=b"", stderr=b"")
        with mock.patch.dict("os.environ", {"WAYLAND_DISPLAY": "", "DISPLAY": ":0"}, clear=False):
            clip_module.read_text()
        mock_run.assert_called_once_with(
            ["xclip", "-selection", "clipboard", "-o"], capture_output=True, timeout=5
        )


if __name__ == "__main__":
    unittest.main()
