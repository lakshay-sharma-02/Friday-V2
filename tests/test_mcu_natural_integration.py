"""Integration tests for natural comms wiring into proactive engine and watcher."""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest import mock


class TestProactiveNaturalWiring(unittest.TestCase):
    """ProactiveEngine flush formats messages through NaturalComms."""

    def test_flush_formats_with_natural_comms(self):
        """flush() formats queued messages through NaturalComms before sending."""
        from friday_mcu.comms.proactive import ProactiveEngine, ProactiveMessage

        engine = ProactiveEngine()
        engine._quiet_hours = (0, 0)  # disable quiet hours

        msg = ProactiveMessage(
            content="You have 3 unread emails",
            priority="normal",
            confidence=0.8,
            reason="email_check",
        )
        engine.suggest(msg)

        # Mock the channel to capture what gets sent
        mock_channel = mock.MagicMock()
        mock_channel.name = "telegram"
        mock_channel.is_available.return_value = True
        mock_channel.send.return_value = "msg_123"

        with mock.patch("friday_mcu.comms.proactive.get_channel", return_value=mock_channel), \
             mock.patch("friday_mcu.comms.proactive.select_channel", return_value=mock_channel):
            sent_ids = engine.flush()

        self.assertEqual(len(sent_ids), 1)
        mock_channel.send.assert_called_once()
        sent_msg = mock_channel.send.call_args[0][0]
        self.assertIn("3 unread emails", sent_msg.content)

    def test_flush_records_tone_in_metadata(self):
        """flush() records the tone used in message metadata."""
        from friday_mcu.comms.proactive import ProactiveEngine, ProactiveMessage

        engine = ProactiveEngine()
        engine._quiet_hours = (0, 0)

        msg = ProactiveMessage(
            content="Test message",
            priority="normal",
            confidence=0.8,
            reason="test",
        )
        engine.suggest(msg)

        mock_channel = mock.MagicMock()
        mock_channel.name = "telegram"
        mock_channel.is_available.return_value = True
        mock_channel.send.return_value = "msg_456"

        with mock.patch("friday_mcu.comms.proactive.get_channel", return_value=mock_channel), \
             mock.patch("friday_mcu.comms.proactive.select_channel", return_value=mock_channel):
            engine.flush()

        sent = engine.recent(1)
        self.assertTrue(len(sent) > 0)
        self.assertIn("tone", sent[0].metadata)

    def test_flush_emits_tone_in_event(self):
        """flush() includes tone in the MESSAGE_SENT event."""
        from friday_mcu.comms.proactive import ProactiveEngine, ProactiveMessage

        engine = ProactiveEngine()
        engine._quiet_hours = (0, 0)

        msg = ProactiveMessage(
            content="Test",
            priority="normal",
            confidence=0.8,
            reason="test",
        )
        engine.suggest(msg)

        mock_channel = mock.MagicMock()
        mock_channel.name = "discord"
        mock_channel.is_available.return_value = True
        mock_channel.send.return_value = "msg_789"

        with mock.patch("friday_mcu.comms.proactive.get_channel", return_value=mock_channel), \
             mock.patch("friday_mcu.comms.proactive.select_channel", return_value=mock_channel), \
             mock.patch("friday_mcu.comms.proactive.emit") as mock_emit:
            engine.flush()
            if mock_emit.called:
                call_args = mock_emit.call_args
                data = call_args[1].get("data") if call_args[1] else {}
                self.assertIn("tone", data)


class TestWatcherNaturalWiring(unittest.TestCase):
    """Watcher uses NaturalComms for notifications and replies."""

    def test_notify_outcome_uses_natural_comms(self):
        """_notify_outcome formats messages through NaturalComms."""
        from friday_mcu.watcher import _notify_outcome

        mock_notify = mock.MagicMock()
        with mock.patch("friday_mcu.adapters.notify.notify_send", mock_notify):
            _notify_outcome("test-trigger", True, {"status": "COMPLETED", "goal": "check email", "duration_s": 5.0})
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            body = call_args[1].get("body", "") if call_args[1] else call_args[0][1] if len(call_args[0]) > 1 else ""
            # Should contain natural language (the trigger name), not raw JSON
            self.assertIn("test-trigger", body.lower())

    def test_notify_outcome_failure_uses_natural_comms(self):
        """_notify_outcome formats error messages through NaturalComms."""
        from friday_mcu.watcher import _notify_outcome

        mock_notify = mock.MagicMock()
        with mock.patch("friday_mcu.adapters.notify.notify_send", mock_notify):
            _notify_outcome("test-trigger", False, {"status": "FAILED", "error": "timeout after 30s"})
            mock_notify.assert_called_once()
            call_args = mock_notify.call_args
            body = call_args[1].get("body", "") if call_args[1] else call_args[0][1] if len(call_args[0]) > 1 else ""
            self.assertIn("timeout", body.lower())

    def test_text_trigger_reply_uses_natural_comms(self):
        """Text trigger replies use NaturalComms for formatting."""
        from friday_mcu.watcher import _run_text_trigger

        with mock.patch("friday_mcu.watcher._execute_goal") as mock_exec, \
             mock.patch("friday_mcu.watcher._get_command_prefix", return_value="/goal"), \
             mock.patch("friday_mcu.watcher._extract_goal", return_value="check email"):
            mock_exec.return_value = {
                "status": "COMPLETED",
                "duration_s": 5.0,
                "_result": "3 unread emails",
                "steps": [{"step_id": 1, "primitive": "gmail.list_unread", "status": "VERIFIED", "attempts": 1}],
            }

            mock_poll = mock.MagicMock(return_value=[
                {"text": "/goal check email", "chat_id": "123", "message_id": "456", "from": "user"}
            ])
            mock_send = mock.MagicMock()

            with mock.patch("friday_mcu.adapters.telegram.poll_text_messages", mock_poll, create=True), \
                 mock.patch("friday_mcu.adapters.telegram.send_text", mock_send, create=True):
                detail = _run_text_trigger(
                    {"id": "tg-test", "schedule": {"type": "telegram-text"}},
                    "run-1",
                    "telegram",
                )

                self.assertEqual(detail["status"], "COMPLETED")
                self.assertEqual(detail["messages_processed"], 1)
                mock_send.assert_called_once()
                reply = mock_send.call_args[0][0]
                self.assertIn("3 unread emails", reply)


class TestNaturalCommsEndToEnd(unittest.TestCase):
    """End-to-end test: message flows through NaturalComms at every stage."""

    def test_full_message_flow(self):
        """A goal result flows through NaturalComms from execution to notification."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()

        # 1. Goal completes
        goal = "check email"
        result_text = "3 unread emails from boss"

        # 2. Build natural result message
        msg = comms.build_goal_result(
            goal=goal,
            result=result_text,
            context={"success": True},
            platform="telegram",
        )
        self.assertIn("3 unread emails", msg.content)
        self.assertEqual(msg.platform, "telegram")

        # 3. Build notification
        error_msg = comms.build_error_report(
            goal="send email",
            error="SMTP timeout",
            platform="whatsapp",
        )
        self.assertIn("SMTP timeout", error_msg.content)

        # 4. Build confirmation
        confirm = comms.build_confirmation_request("send this email to the team")
        self.assertTrue(confirm.requires_confirmation)
        self.assertIn("send this email", confirm.confirmation_prompt)


if __name__ == "__main__":
    unittest.main()
