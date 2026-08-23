"""window primitives: protected-class refusal in close_window/close_all
(fail-before-any-dispatch), selector normalization, and the compact L0
log projection - all through mocked hyprctl, never the real compositor."""

from __future__ import annotations

import unittest
from unittest import mock

from friday.errors import PreconditionError, PrimitiveError
from friday.l1 import window as w
from tests.helpers import EnvTestCase

CLIENTS = [
    {"address": "0xkitty", "class": "kitty", "title": "term"},
    {"address": "0xfirefox", "class": "firefox", "title": "web"},
]


class _HyprctlHarness:
    """Replaces window._hyprctl: records dispatch args, no real side effect."""

    def __init__(self):
        self.calls = []

    def __call__(self, *args, **kwargs):
        self.calls.append(args)
        return mock.Mock(returncode=0, stdout="", stderr="")


class TestProtectedClasses(EnvTestCase):
    def setUp(self):
        super().setUp()
        # these tests exercise the POSIX/hyprctl path; the suite runs on
        # Windows too, where the primitives dispatch to the win32 backend
        self.p_os = mock.patch.object(w, "_IS_WINDOWS", False)
        self.hypr = _HyprctlHarness()
        self.p_hypr = mock.patch.object(w, "_hyprctl", self.hypr)
        self.p_wait = mock.patch.object(w, "_wait_until", return_value=True)
        self.p_clients = mock.patch.object(w, "list_clients", return_value=list(CLIENTS))
        self.p_os.start()
        self.p_hypr.start()
        self.p_wait.start()
        self.p_clients.start()
        self.addCleanup(self.p_os.stop)
        self.addCleanup(self.p_hypr.stop)
        self.addCleanup(self.p_wait.stop)
        self.addCleanup(self.p_clients.stop)

    def test_default_protected_is_kitty(self):
        self.assertEqual(w._protected_classes(), ("kitty",))

    def test_env_override(self):
        self.set_env(FRIDAY_PROTECTED_CLASSES="gnome-terminal,kitty")
        self.assertEqual(w._protected_classes(), ("gnome-terminal", "kitty"))

    def test_close_window_refuses_protected_address(self):
        with self.assertRaises(PreconditionError) as ctx:
            w.close_window("0xkitty")
        self.assertIn("protected", str(ctx.exception).lower())
        self.assertEqual(self.hypr.calls, [])  # nothing dispatched

    def test_close_window_refuses_protected_via_class_selector(self):
        with self.assertRaises(PreconditionError):
            w.close_window("kitty")
        self.assertEqual(self.hypr.calls, [])

    def test_close_window_allows_non_protected(self):
        w.close_window("0xfirefox")
        self.assertTrue(any("address:0xfirefox" in str(c) for c in self.hypr.calls))

    def test_close_all_refuses_before_any_dispatch(self):
        with self.assertRaises(PreconditionError):
            w.close_all(exclude_classes=["firefox"])  # kitty not excluded
        self.assertEqual(self.hypr.calls, [])

    def test_close_all_excluding_protected_closes_rest(self):
        self.assertEqual(w.close_all(exclude_classes=["kitty"]), 1)
        self.assertTrue(any("address:0xfirefox" in str(c) for c in self.hypr.calls))
        self.assertFalse(any("0xkitty" in str(c) for c in self.hypr.calls))

    def test_env_override_relaxes_protection(self):
        self.set_env(FRIDAY_PROTECTED_CLASSES="nothing-here")
        self.assertEqual(w.close_all(exclude_classes=["firefox"]), 1)  # kitty closable now
        self.assertTrue(any("0xkitty" in str(c) for c in self.hypr.calls))


class TestSelectorNormalization(EnvTestCase):
    def test_address_prefix(self):
        self.assertEqual(w._selector_arg("0x1234"), "address:0x1234")

    def test_explicit_prefix_passthrough(self):
        self.assertEqual(w._selector_arg("class:firefox"), "class:firefox")
        self.assertEqual(w._selector_arg("title:foo"), "title:foo")

    def test_bare_name_becomes_class(self):
        self.assertEqual(w._selector_arg("firefox"), "class:firefox")


class TestPreconditions(EnvTestCase):
    def test_open_app_empty_command(self):
        with self.assertRaises(PreconditionError):
            w.open_app("   ")

    def test_close_window_empty_selector(self):
        with self.assertRaises(PreconditionError):
            w.close_window("")

    def test_move_to_workspace_invalid(self):
        with self.assertRaises(PreconditionError):
            w.move_to_workspace(0, "firefox")


class TestLogProjection(EnvTestCase):
    def test_compact_client(self):
        c = w._compact_client(
            {
                "address": "0x1",
                "class": "kitty",
                "title": "t",
                "workspace": {"id": 2},
                "pid": 9,
                "mapped": True,
                "at": [1, 2],
                "size": [3, 4],
                "monitor": 0,
            }
        )
        self.assertEqual(
            c,
            {
                "address": "0x1",
                "class": "kitty",
                "title": "t",
                "workspace_id": 2,
                "pid": 9,
                "mapped": True,
            },
        )

    def test_log_clients_result_list_and_single(self):
        out = w._log_clients_result(list(CLIENTS))
        self.assertEqual(len(out), 2)
        self.assertIn("address", out[0])
        single = w._log_clients_result(CLIENTS[0])
        self.assertEqual(single["address"], "0xkitty")


class TestListClientsErrors(EnvTestCase):
    def test_hyprctl_failure_raises_primitive_error(self):
        def boom(*a, **k):
            return mock.Mock(returncode=1, stderr="compositor not running", stdout="")

        with (
            mock.patch.object(w, "_IS_WINDOWS", False),
            mock.patch.object(w, "_hyprctl", boom),
            self.assertRaises(PrimitiveError),
        ):
            w.list_clients()


class TestWin32Backend(EnvTestCase):
    """The win32 backend (2026-08-17, the port's step 7): the hyprctl-shaped
    client dicts, the dispatch branches (PostMessageW close, SetForeground-
    Window focus, Popen launch, honest move_to_workspace stub) - with the
    user32 layer mocked, never the real desktop."""

    ROWS = [
        (0x1234, "my terminal", "CASCADIA_HOSTING_WINDOW_CLASS", 8056, [96, 104, 889, 545]),
        (0x5678, "brave", "Chrome_WidgetWin_1", 5004, [0, 0, 1382, 784]),
    ]

    def test_win_clients_shape(self):
        with mock.patch.object(w, "_win_enum_windows", return_value=list(self.ROWS)):
            clients = w._win_clients()
        self.assertEqual(len(clients), 2)
        first = clients[0]
        self.assertEqual(first["address"], "0x1234")
        self.assertEqual(first["class"], "CASCADIA_HOSTING_WINDOW_CLASS")
        self.assertEqual(first["at"], [96, 104])
        self.assertEqual(first["size"], [889, 545])
        self.assertEqual(first["pid"], 8056)
        self.assertEqual(first["workspace"], {"id": 0})

    def test_list_clients_dispatches_to_win32(self):
        with (
            mock.patch.object(w, "_IS_WINDOWS", True),
            mock.patch.object(
                w, "_win_enum_windows", return_value=[(0x1, "t", "c", 1, [0, 0, 10, 10])]
            ),
        ):
            clients = w.list_clients()
        self.assertEqual([c["address"] for c in clients], ["0x1"])

    def test_win_enum_failure_degrades_to_empty(self):
        with (
            mock.patch.object(w, "_IS_WINDOWS", True),
            mock.patch.object(w, "_win_enum_windows", side_effect=OSError("win32 blew up")),
        ):
            self.assertEqual(w.list_clients(), [])

    def test_close_window_uses_postmessage_on_windows(self):
        fake = mock.Mock()
        with (
            mock.patch.object(w, "_IS_WINDOWS", True),
            mock.patch.object(w, "_user32", return_value=fake),
            mock.patch.object(
                w, "list_clients", return_value=[{"address": "0x1234", "class": "x"}]
            ),
            mock.patch.object(w, "_wait_until", return_value=True),
        ):
            w.close_window("0x1234")
        fake.PostMessageW.assert_called_once_with(0x1234, w._WM_CLOSE, 0, 0)

    def test_focus_window_uses_setforeground_on_windows(self):
        fake = mock.Mock()
        with (
            mock.patch.object(w, "_IS_WINDOWS", True),
            mock.patch.object(w, "_user32", return_value=fake),
            mock.patch.object(
                w, "list_clients", return_value=[{"address": "0x1234", "class": "x"}]
            ),
            mock.patch.object(w, "_wait_until", return_value=True),
        ):
            w.focus_window("0x1234")
        fake.SetForegroundWindow.assert_called_once_with(0x1234)

    def test_focus_window_no_match_raises(self):
        with (
            mock.patch.object(w, "_IS_WINDOWS", True),
            mock.patch.object(w, "list_clients", return_value=[]),
        ):
            with self.assertRaises(PrimitiveError):
                w.focus_window("0x9999")

    def test_move_to_workspace_stub_on_windows(self):
        with mock.patch.object(w, "_IS_WINDOWS", True):
            with self.assertRaises(PreconditionError):
                w.move_to_workspace(1, "0x1234")

    def test_open_app_launches_via_popen_on_windows(self):
        launched = {"address": "0x1", "class": "new", "title": "t"}
        with (
            mock.patch.object(w, "_IS_WINDOWS", True),
            mock.patch.object(w, "list_clients", return_value=[]),
            mock.patch.object(w.subprocess, "Popen") as popen,
            mock.patch.object(w, "_wait_until_return", return_value=launched),
        ):
            out = w.open_app("notepad")
        popen.assert_called_once_with("notepad", shell=True)
        self.assertEqual(out["address"], "0x1")

    def test_shutdown_is_noop_on_windows(self):
        with mock.patch.object(w, "_IS_WINDOWS", True), mock.patch.object(w, "_hyprctl") as hypr:
            w.shutdown()
        hypr.assert_not_called()


if __name__ == "__main__":
    unittest.main()
