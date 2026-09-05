"""Tests for the phone-as-Jarvis layer:

- phone telemetry store (allowlist, persistence, context render)
- chat command router (/friday help|status|adapters|memory|phone, goal fallback)
- watcher text triggers routing through the command layer
- Discord reply keyword fix (channel_id=, not to=)
- phone context exposed to the planner's full context block
"""

from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TestPhoneState(unittest.TestCase):
    """Phone telemetry store: allowlist + persistence + context render."""

    def test_update_and_get_roundtrip(self):
        from friday_mcu import phone as phone_mod

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "phone_state.json"
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                merged = phone_mod.update_phone_state({
                    "device": "Pixel 8",
                    "battery": 84,
                    "activity": "walking",
                    "do_not_disturb": True,
                })
                self.assertEqual(merged["device"], "Pixel 8")
                self.assertEqual(merged["battery"], 84)
                self.assertIn("last_seen", merged)

                state = phone_mod.get_phone_state()
                self.assertEqual(state["device"], "Pixel 8")
                self.assertEqual(state["activity"], "walking")
                self.assertTrue(state["do_not_disturb"])

    def test_allowlist_drops_unknown_keys(self):
        from friday_mcu import phone as phone_mod

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "phone_state.json"
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                merged = phone_mod.update_phone_state({
                    "device": "Pixel",
                    "credit_card": "4111 1111 1111 1111",
                    "location": "home",
                })
                self.assertNotIn("credit_card", merged)
                self.assertEqual(merged["device"], "Pixel")

    def test_empty_value_clears_key(self):
        from friday_mcu import phone as phone_mod

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "phone_state.json"
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                phone_mod.update_phone_state({"device": "Pixel", "activity": "walking"})
                phone_mod.update_phone_state({"activity": ""})
                state = phone_mod.get_phone_state()
                self.assertEqual(state["device"], "Pixel")
                self.assertNotIn("activity", state)

    def test_no_state_returns_empty(self):
        from friday_mcu import phone as phone_mod

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "missing.json"
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                self.assertEqual(phone_mod.get_phone_state(), {})
                self.assertEqual(phone_mod.phone_context(), "")

    def test_context_render(self):
        from friday_mcu import phone as phone_mod

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "phone_state.json"
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                phone_mod.update_phone_state({
                    "device": "Pixel 8",
                    "battery": 84,
                    "activity": "at desk",
                    "location": "office",
                })
                ctx = phone_mod.phone_context()
                self.assertIn("PHONE:", ctx)
                self.assertIn("Pixel 8", ctx)
                self.assertIn("at desk", ctx)
                self.assertIn("84%", ctx)
                self.assertIn("office", ctx)

    def test_context_marks_dnd(self):
        from friday_mcu import phone as phone_mod

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "phone_state.json"
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                phone_mod.update_phone_state({"do_not_disturb": True, "device": "Pixel"})
                self.assertIn("do-not-disturb ON", phone_mod.phone_context())

    def test_sms_and_notification_sensors(self):
        """SMS/call/notification telemetry persists and renders."""
        from friday_mcu import phone as phone_mod

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "phone_state.json"
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                merged = phone_mod.update_phone_state({
                    "sms_unread": 2,
                    "sms_latest": "Boss : did you send it?\nsecond line",
                    "missed_calls": 1,
                    "notifications": 5,
                    "notifications_top": "com.whatsapp",
                })
                self.assertEqual(merged["sms_unread"], 2)
                self.assertEqual(merged["missed_calls"], 1)

                ctx = phone_mod.phone_context()
                self.assertIn("sms: 2 unread", ctx)
                self.assertIn("latest sms: Boss : did you send it? second line", ctx)
                self.assertIn("1 missed calls", ctx)
                self.assertIn("5 notifications", ctx)
                self.assertIn("com.whatsapp", ctx)

    def test_sensors_allowlisted(self):
        """Only allowlisted sensor keys are persisted."""
        from friday_mcu import phone as phone_mod

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "phone_state.json"
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                merged = phone_mod.update_phone_state({
                    "sms_unread": 3,
                    "sms_latest": "hello",
                    "notifications": 1,
                    "call_log": "stripped",  # not allowlisted
                })
                self.assertNotIn("call_log", merged)
                self.assertEqual(merged["sms_unread"], 3)


class TestChatCommandRouting(unittest.TestCase):
    """The command router: /friday built-ins, goal fallback, chatter."""

    def test_goal_prefix_falls_through(self):
        from friday_mcu.comms.commands import route

        r = route("/goal summarize my unread email")
        self.assertIsNone(r)  # caller must plan + execute

    def test_help_command(self):
        from friday_mcu.comms.commands import route

        r = route("/friday help")
        self.assertIsNotNone(r)
        self.assertTrue(r.consumed)
        self.assertIn("Commands", r.reply)

    def test_status_command(self):
        from friday_mcu.comms.commands import route

        r = route("/friday status")
        self.assertIsNotNone(r)
        self.assertTrue(r.consumed)
        self.assertTrue(r.reply)

    def test_adapters_command(self):
        from friday_mcu.comms.commands import route

        r = route("/friday adapters")
        self.assertTrue(r.consumed)
        self.assertIn("telegram", r.reply)
        self.assertIn("gmail", r.reply)

    def test_memory_command(self):
        from friday_mcu.comms.commands import route

        r = route("/friday memory")
        self.assertTrue(r.consumed)
        self.assertIn("Episodic", r.reply)

    def test_phone_command(self):
        from friday_mcu.comms.commands import route

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "phone_state.json"
            state_file.write_text(json.dumps({
                "device": "Pixel 8", "battery": 60, "sms_unread": 2,
                "notifications": 4, "last_seen": 9999999999,
            }), encoding="utf-8")
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                r = route("/friday phone")
                self.assertTrue(r.consumed)
                self.assertIn("Pixel 8", r.reply)
                self.assertIn("sms: 2 unread", r.reply)
                self.assertIn("notifications: 4", r.reply)

    def test_chatter_not_consumed_no_reply(self):
        from friday_mcu.comms.commands import route

        r = route("hey friday what's up")
        self.assertIsNotNone(r)
        self.assertFalse(r.consumed)
        self.assertIsNone(r.reply)

    def test_unknown_slash_gets_help(self):
        from friday_mcu.comms.commands import route

        r = route("/banana")
        self.assertTrue(r.consumed)
        self.assertIn("Commands", r.reply)

    def test_goal_prefix_without_goal_gets_usage(self):
        from friday_mcu.comms.commands import route

        r = route("/goal")
        self.assertTrue(r.consumed)
        self.assertIn("Usage", r.reply)

    def test_goal_prefix_env_override(self):
        from friday_mcu.comms import commands as commands_mod

        with mock.patch.dict("os.environ", {"FRIDAY_COMMAND_PREFIX": "/do"}):
            self.assertIsNone(commands_mod.route("/do launch the rockets"))

    def test_empty_prefix_makes_plain_text_a_goal(self):
        from friday_mcu.comms import commands as commands_mod

        with mock.patch.dict("os.environ", {"FRIDAY_COMMAND_PREFIX": ""}):
            r = commands_mod.route("summarize my email")
            self.assertIsNone(r)  # goal fallback

    def test_extract_goal_backcompat(self):
        from friday_mcu.comms.commands import extract_goal

        self.assertEqual(extract_goal("/goal pause music", "/goal"), "pause music")
        self.assertEqual(extract_goal("/GOAL check email", "/goal"), "check email")
        self.assertIsNone(extract_goal("hey what's up", "/goal"))
        self.assertEqual(extract_goal("pause the music", ""), "pause the music")


class TestTextTriggerRouting(unittest.TestCase):
    """Watcher text triggers route through the command layer."""

    def test_goal_message_executes_and_replies(self):
        from friday_mcu.watcher import _run_text_trigger

        messages = [{"text": "/goal check email", "chat_id": "123", "message_id": "456", "update_id": 7, "from": "user"}]
        with mock.patch("friday_mcu.adapters.telegram.poll_text_messages", return_value=messages, create=True), \
             mock.patch("friday_mcu.adapters.telegram.send_text", create=True) as mock_send, \
             mock.patch("friday_mcu.adapters.telegram.mark_read", create=True) as mock_read, \
             mock.patch("friday_mcu.watcher._execute_goal", return_value={
                 "status": "COMPLETED", "duration_s": 1.0, "_result": "2 unread emails",
                 "steps": [{"step_id": 1, "primitive": "gmail.list_unread", "status": "VERIFIED", "attempts": 1}],
             }) as mock_exec:
            detail = _run_text_trigger({"id": "tg", "schedule": {"type": "telegram-text"}}, "run-1", "telegram")
            self.assertEqual(detail["status"], "COMPLETED")
            mock_exec.assert_called_once()
            self.assertEqual(mock_send.call_count, 1)
            self.assertIn("2 unread emails", mock_send.call_args[0][0])
            # Consumed once handled (offset advanced past update_id 7).
            mock_read.assert_called_once_with([7])
            self.assertEqual(detail["results"][0]["status"], "COMPLETED")

    def test_friday_command_replies_without_llm(self):
        from friday_mcu.watcher import _run_text_trigger

        messages = [{"text": "/friday help", "chat_id": "123", "message_id": "1", "update_id": 3, "from": "user"}]
        with mock.patch("friday_mcu.adapters.telegram.poll_text_messages", return_value=messages, create=True), \
             mock.patch("friday_mcu.adapters.telegram.send_text", create=True) as mock_send, \
             mock.patch("friday_mcu.adapters.telegram.mark_read", create=True) as mock_read, \
             mock.patch("friday_mcu.watcher._execute_goal") as mock_exec:
            detail = _run_text_trigger({"id": "tg", "schedule": {"type": "telegram-text"}}, "run-1", "telegram")
            self.assertEqual(detail["status"], "COMPLETED")
            mock_exec.assert_not_called()  # zero LLM cost
            self.assertEqual(mock_send.call_count, 1)
            self.assertIn("Commands", mock_send.call_args[0][0])
            self.assertEqual(detail["results"][0]["status"], "COMMAND")
            mock_read.assert_called_once_with([3])

    def test_chatter_consumed_no_reply(self):
        from friday_mcu.watcher import _run_text_trigger

        messages = [{"text": "hello there", "chat_id": "123", "message_id": "2", "update_id": 9, "from": "user"}]
        with mock.patch("friday_mcu.adapters.telegram.poll_text_messages", return_value=messages, create=True), \
             mock.patch("friday_mcu.adapters.telegram.send_text", create=True) as mock_send, \
             mock.patch("friday_mcu.adapters.telegram.mark_read", create=True) as mock_read, \
             mock.patch("friday_mcu.watcher._execute_goal") as mock_exec:
            detail = _run_text_trigger({"id": "tg", "schedule": {"type": "telegram-text"}}, "run-1", "telegram")
            self.assertEqual(detail["status"], "COMPLETED")
            mock_exec.assert_not_called()
            mock_send.assert_not_called()  # chatter gets no reply
            mock_read.assert_called_once_with([9])  # ...but is still consumed
            self.assertEqual(detail["messages_skipped"], 1)

    def test_goal_prefix_env_used(self):
        from friday_mcu.watcher import _run_text_trigger

        messages = [{"text": "/do pause music", "chat_id": "123", "message_id": "5", "update_id": 11, "from": "user"}]
        with mock.patch.dict("os.environ", {"FRIDAY_COMMAND_PREFIX": "/do"}), \
             mock.patch("friday_mcu.adapters.telegram.poll_text_messages", return_value=messages, create=True), \
             mock.patch("friday_mcu.adapters.telegram.send_text", create=True), \
             mock.patch("friday_mcu.adapters.telegram.mark_read", create=True), \
             mock.patch("friday_mcu.watcher._execute_goal", return_value={
                 "status": "COMPLETED", "duration_s": 0.5, "_result": "paused",
                 "steps": [{"step_id": 1, "primitive": "media.pause", "status": "VERIFIED", "attempts": 1}],
             }) as mock_exec:
            _run_text_trigger({"id": "tg", "schedule": {"type": "telegram-text"}}, "run-1", "telegram")
            mock_exec.assert_called_once_with("pause music", mock.ANY)

    def test_discord_reply_uses_channel_id_kwarg(self):
        """Regression: discord.send_text takes channel_id=, not to= — the old
        call raised TypeError which was swallowed, so Discord never replied."""
        from friday_mcu.watcher import _run_text_trigger

        raw = [{"id": "2001", "content": "/goal hi", "author": "boss", "channel_id": "ch-42"}]
        with mock.patch("friday_mcu.adapters.discord.poll_messages", return_value=raw, create=True), \
             mock.patch("friday_mcu.adapters.discord.send_text", create=True) as mock_send, \
             mock.patch("friday_mcu.adapters.discord.mark_channel_read", create=True) as mock_read, \
             mock.patch("friday_mcu.watcher._execute_goal", return_value={
                 "status": "COMPLETED", "duration_s": 0.5, "_result": "done",
                 "steps": [{"step_id": 1, "primitive": "fake.echo", "status": "VERIFIED", "attempts": 1}],
             }) as mock_exec:
            detail = _run_text_trigger({"id": "dc", "schedule": {"type": "discord-text"}}, "run-1", "discord")
            self.assertEqual(detail["status"], "COMPLETED")
            mock_exec.assert_called_once()
            self.assertEqual(mock_send.call_count, 1)
            kwargs = mock_send.call_args.kwargs or {}
            self.assertNotIn("to", kwargs)
            self.assertEqual(kwargs.get("channel_id"), "ch-42")
            mock_read.assert_called_once_with("ch-42", "2001")


class TestPhonePlannerContext(unittest.TestCase):
    """Phone telemetry surfaces in the planner's context block."""

    def test_phone_context_in_full_context(self):
        from friday_mcu.brain.context import ContextManager

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "phone_state.json"
            state_file.write_text(json.dumps({
                "device": "Pixel", "activity": "at desk", "battery": 77, "last_seen": 9999999999,
            }), encoding="utf-8")
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                ctx = ContextManager()
                ctx.set_goal("check my calendar")
                text = ctx.build_full_context()
                self.assertIn("CURRENT STATE", text)
                self.assertIn("check my calendar", text)
                self.assertIn("PHONE:", text)
                self.assertIn("Pixel", text)
                self.assertIn("at desk", text)


class TestPhoneApiEndpoints(unittest.TestCase):
    """/v1/phone endpoints (skipped when FastAPI is not installed)."""

    def _has_fastapi(self) -> bool:
        try:
            import fastapi  # noqa: F401
            return True
        except ImportError:
            return False

    def test_phone_get_post(self):
        if not self._has_fastapi():
            self.skipTest("fastapi not installed")
        try:
            from fastapi.testclient import TestClient
        except ImportError:
            self.skipTest("starlette test client not installed")

        from friday_mcu.api.server import create_app

        with tempfile.TemporaryDirectory() as tmp:
            state_file = Path(tmp) / "phone_state.json"
            with mock.patch.dict("os.environ", {"FRIDAY_PHONE_STATE_FILE": str(state_file)}):
                app = create_app()
                client = TestClient(app)
                r = client.get("/v1/phone")
                self.assertEqual(r.status_code, 200)
                self.assertFalse(r.json()["paired"])

                r = client.post("/v1/phone", json={"device": "Pixel", "battery": 50})
                self.assertEqual(r.status_code, 200)
                self.assertTrue(r.json()["paired"])
                self.assertEqual(r.json()["state"]["battery"], 50)

                r = client.get("/v1/phone")
                self.assertTrue(r.json()["paired"])
                self.assertEqual(r.json()["state"]["device"], "Pixel")


if __name__ == "__main__":
    unittest.main()
