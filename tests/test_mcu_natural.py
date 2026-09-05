"""Tests for MCU Friday natural communication module."""

from __future__ import annotations

import unittest


class TestToneProfiles(unittest.TestCase):
    """Tone profile tests."""

    def test_all_profiles_exist(self):
        """All predefined tone profiles exist."""
        from friday_mcu.comms.natural import TONE_PROFILES

        self.assertIn("formal", TONE_PROFILES)
        self.assertIn("casual", TONE_PROFILES)
        self.assertIn("work", TONE_PROFILES)
        self.assertIn("personal", TONE_PROFILES)
        self.assertIn("neutral", TONE_PROFILES)

    def test_formal_tone_has_no_emoji(self):
        """Formal tone has no emoji."""
        from friday_mcu.comms.natural import TONE_PROFILES

        self.assertEqual(TONE_PROFILES["formal"].emoji_style, "none")
        self.assertEqual(TONE_PROFILES["formal"].formality, "formal")

    def test_casual_tone_has_emoji(self):
        """Casual tone has emoji."""
        from friday_mcu.comms.natural import TONE_PROFILES

        self.assertEqual(TONE_PROFILES["casual"].emoji_style, "minimal")
        self.assertEqual(TONE_PROFILES["casual"].formality, "casual")

    def test_profile_to_dict(self):
        """Profile serialization works."""
        from friday_mcu.comms.natural import TONE_PROFILES

        d = TONE_PROFILES["formal"].to_dict()
        self.assertEqual(d["name"], "formal")
        self.assertEqual(d["formality"], "formal")


class TestNaturalComms(unittest.TestCase):
    """Natural comms tests."""

    def test_build_goal_result_success(self):
        """Success messages are natural and informative."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_goal_result(
            goal="check email",
            result="3 unread emails",
            context={"success": True, "tone": "neutral"},
        )
        self.assertIn("3 unread emails", msg.content)
        self.assertFalse(msg.requires_confirmation)
        self.assertEqual(msg.tone, "neutral")

    def test_build_goal_result_failure(self):
        """Failure messages include the error."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_goal_result(
            goal="check email",
            result="",
            context={"success": False, "error": "timeout", "tone": "neutral"},
        )
        self.assertIn("timeout", msg.content)
        self.assertIn("Failed", msg.content)

    def test_build_goal_result_with_details(self):
        """Details are included in full content."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_goal_result(
            goal="check email",
            result="3 unread",
            details="From: boss\nFrom: mom",
        )
        self.assertIn("From: boss", msg.content)
        self.assertEqual(msg.details, "From: boss\nFrom: mom")

    def test_build_goal_result_progressive_disclosure(self):
        """Summary is separate from full content."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_goal_result(
            goal="check email",
            result="3 unread",
            details="Long details here",
        )
        self.assertEqual(msg.summary, msg.content.split("\n\nDetails:")[0])

    def test_build_proactive_suggestion(self):
        """Proactive suggestions are natural."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_proactive_suggestion(
            suggestion="You usually check email at 9am",
            reason="Pattern detected",
        )
        self.assertIn("You usually check email at 9am", msg.content)
        self.assertIn("Pattern detected", msg.content)

    def test_build_confirmation_request(self):
        """Confirmation requests ask before acting."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_confirmation_request("send this email")
        self.assertTrue(msg.requires_confirmation)
        self.assertIn("send this email", msg.confirmation_prompt)

    def test_build_confirmation_formal(self):
        """Formal confirmation is more formal."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_confirmation_request(
            "send this email",
            context={"tone": "formal"},
        )
        self.assertIn("I am about to", msg.content)

    def test_build_error_report(self):
        """Error reports are clear."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_error_report("check email", "timeout after 30s")
        self.assertIn("timeout", msg.content)
        self.assertIn("check email", msg.content)

    def test_build_error_report_with_attempts(self):
        """Error reports include attempt count."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_error_report(
            "check email",
            "timeout",
            context={"attempts": 3},
        )
        self.assertIn("3 attempts", msg.content)

    def test_build_daily_briefing(self):
        """Daily briefings are formatted nicely."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        items = [
            {"title": "Email check", "summary": "3 unread", "priority": "medium"},
            {"title": "Urgent meeting", "summary": "In 5 min", "priority": "urgent"},
        ]
        msg = comms.build_daily_briefing(items)
        self.assertIn("Email check", msg.content)
        self.assertIn("Urgent meeting", msg.content)
        self.assertEqual(msg.summary, "2 items (1 urgent)")

    def test_daily_briefing_empty(self):
        """Empty briefing still produces output."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_daily_briefing([])
        self.assertEqual(msg.summary, "0 items")


class TestToneSelection(unittest.TestCase):
    """Tone selection tests."""

    def test_explicit_tone_overrides(self):
        """Explicit tone in context overrides everything."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        tone = comms.get_tone(context={"tone": "formal"})
        self.assertEqual(tone.name, "formal")

    def test_work_hours_use_work_tone(self):
        """Work hours default to work tone."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        tone = comms.get_tone(context={"hour": 14})
        self.assertEqual(tone.name, "work")

    def test_evening_use_personal_tone(self):
        """Evening hours default to personal tone."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        tone = comms.get_tone(context={"hour": 20})
        self.assertEqual(tone.name, "personal")

    def test_platform_tone_override(self):
        """Platform-specific tone overrides time heuristic."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        comms.set_platform_tone("discord", "casual")
        tone = comms.get_tone(platform="discord", context={"hour": 14})
        self.assertEqual(tone.name, "casual")

    def test_neutral_default(self):
        """Unknown context defaults to neutral."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        tone = comms.get_tone(context={"hour": 5})
        self.assertEqual(tone.name, "neutral")


class TestPlatformFormatting(unittest.TestCase):
    """Platform formatting tests."""

    def test_whatsapp_strips_markdown(self):
        """WhatsApp strips markdown formatting."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_goal_result(
            goal="check email",
            result="**bold** text",
            platform="whatsapp",
        )
        self.assertNotIn("**", msg.content)
        self.assertIn("bold", msg.content)

    def test_telegram_keeps_markdown(self):
        """Telegram keeps markdown formatting."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_goal_result(
            goal="check email",
            result="**bold** text",
            platform="telegram",
        )
        self.assertIn("**bold**", msg.content)

    def test_discord_keeps_markdown(self):
        """Discord keeps markdown formatting."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        msg = comms.build_goal_result(
            goal="check email",
            result="**bold** text",
            platform="discord",
        )
        self.assertIn("**bold**", msg.content)


class TestLearning(unittest.TestCase):
    """Tone learning tests."""

    def test_record_and_get_preferred_tone(self):
        """Recorded tones influence preferred tone."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        comms.record_tone_choice("formal")
        comms.record_tone_choice("formal")
        comms.record_tone_choice("casual")
        self.assertEqual(comms.get_preferred_tone(), "formal")

    def test_empty_history_returns_neutral(self):
        """Empty history returns neutral tone."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        self.assertEqual(comms.get_preferred_tone(), "neutral")

    def test_stats(self):
        """Stats report communication state."""
        from friday_mcu.comms.natural import NaturalComms

        comms = NaturalComms()
        comms.set_platform_tone("discord", "casual")
        comms.record_tone_choice("work")
        stats = comms.get_stats()
        self.assertEqual(stats["tone_history"], 1)
        self.assertEqual(stats["platform_tones"]["discord"], "casual")


class TestMessageToDict(unittest.TestCase):
    """Message serialization tests."""

    def test_to_dict(self):
        """NaturalMessage serialization works."""
        from friday_mcu.comms.natural import NaturalMessage

        msg = NaturalMessage(
            content="test content",
            tone="formal",
            summary="test",
            details="long details",
            requires_confirmation=True,
            platform="telegram",
        )
        d = msg.to_dict()
        self.assertEqual(d["content"], "test content")
        self.assertEqual(d["tone"], "formal")
        self.assertTrue(d["has_details"])
        self.assertTrue(d["requires_confirmation"])


if __name__ == "__main__":
    unittest.main()
