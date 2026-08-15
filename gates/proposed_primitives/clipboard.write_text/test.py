import os
import subprocess
import unittest
from unittest import mock

from friday.errors import PrimitiveError
from friday.l1 import clipboard


class WriteTextTest(unittest.TestCase):
    def test_writes_via_wl_copy_on_wayland(self):
        with mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=False):
            with mock.patch(
                "subprocess.run",
                return_value=mock.Mock(returncode=0, stdout=None, stderr=None),
            ) as run:
                result = clipboard.write_text("hello")
        self.assertEqual(result, "hello")
        run.assert_called_once_with(
            ["wl-copy"], input="hello", stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, text=True, timeout=5,
        )

    def test_writes_via_xclip_on_x11(self):
        env = {k: v for k, v in os.environ.items() if k != "WAYLAND_DISPLAY"}
        env["DISPLAY"] = ":0"
        with mock.patch.dict(os.environ, env, clear=True):
            with mock.patch(
                "subprocess.run",
                return_value=mock.Mock(returncode=0, stdout=None, stderr=None),
            ) as run:
                result = clipboard.write_text("note")
        self.assertEqual(result, "note")
        self.assertEqual(run.call_args[0][0], ["xclip", "-selection", "clipboard"])
        self.assertEqual(run.call_args[1]["stdout"], subprocess.DEVNULL)
        self.assertEqual(run.call_args[1]["stderr"], subprocess.DEVNULL)

    def test_tool_failure_raises_primitive_error(self):
        with mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=False):
            with mock.patch(
                "subprocess.run",
                return_value=mock.Mock(returncode=1, stdout=None, stderr=None),
            ):
                with self.assertRaises(PrimitiveError):
                    clipboard.write_text("x")

    def test_missing_tool_raises_primitive_error(self):
        with mock.patch.dict(os.environ, {"WAYLAND_DISPLAY": "wayland-0"}, clear=False):
            with mock.patch("subprocess.run", side_effect=FileNotFoundError("wl-copy")):
                with self.assertRaises(PrimitiveError):
                    clipboard.write_text("x")


if __name__ == "__main__":
    unittest.main()
