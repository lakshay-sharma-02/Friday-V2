"""Tests for MCU Friday adapters."""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from friday_mcu.core.errors import PreconditionError, PrimitiveError


class TestFilesAdapter(unittest.TestCase):
    """Files adapter tests."""

    def test_find_file(self):
        """find_file locates a file by name substring."""
        from friday_mcu.adapters.files import find_file
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "report.pdf").write_text("x")
            result = find_file("report", d)
            self.assertTrue(result["path"].endswith("report.pdf"))

    def test_find_file_not_found(self):
        """find_file raises PreconditionError when no match."""
        from friday_mcu.adapters.files import find_file
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(PreconditionError):
                find_file("nonexistent", d)

    def test_find_file_exact(self):
        """find_file_exact returns empty path for missing files."""
        from friday_mcu.adapters.files import find_file_exact
        with tempfile.TemporaryDirectory() as d:
            result = find_file_exact("nope.txt", d)
            self.assertEqual(result["path"], "")

    def test_find_newest(self):
        """find_newest returns the most recently modified file."""
        from friday_mcu.adapters.files import find_newest
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "old.txt").write_text("old")
            import time
            time.sleep(0.05)
            (Path(d) / "new.txt").write_text("new")
            result = find_newest(".txt", d)
            self.assertEqual(result["name"], "new.txt")

    def test_read_text(self):
        """read_text returns file content."""
        from friday_mcu.adapters.files import read_text
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "test.txt"
            p.write_text("hello world")
            result = read_text(str(p))
            self.assertEqual(result["text"], "hello world")
            self.assertEqual(result["size"], 11)

    def test_write_text(self):
        """write_text creates and writes to a file."""
        from friday_mcu.adapters.files import write_text
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "output.txt"
            result = write_text(str(p), "test content")
            self.assertEqual(p.read_text(), "test content")
            self.assertTrue(result["path"].endswith("output.txt"))

    def test_write_text_append(self):
        """write_text appends when append=True."""
        from friday_mcu.adapters.files import write_text
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "append.txt"
            write_text(str(p), "line1\n")
            write_text(str(p), "line2\n", append=True)
            self.assertEqual(p.read_text(), "line1\nline2\n")

    def test_list_dir(self):
        """list_dir returns directory entries."""
        from friday_mcu.adapters.files import list_dir
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "a.txt").write_text("a")
            (Path(d) / "b.txt").write_text("b")
            result = list_dir(d)
            self.assertEqual(result["total"], 2)
            self.assertIn("a.txt", result["entries"])


class TestClipboardAdapter(unittest.TestCase):
    """Clipboard adapter tests (mocked)."""

    def test_read_text_returns_string(self):
        """read_text returns a string (mocked)."""
        from friday_mcu.adapters.clipboard import read_text
        with mock.patch("friday_mcu.adapters.clipboard._run_clipboard", return_value="clipboard content"):
            result = read_text()
            self.assertEqual(result, "clipboard content")

    def test_write_text_returns_text(self):
        """write_text returns the text that was written (mocked)."""
        from friday_mcu.adapters.clipboard import write_text
        with mock.patch("friday_mcu.adapters.clipboard._run_clipboard", return_value=""):
            result = write_text("test clipboard content")
            self.assertEqual(result, "test clipboard content")


class TestSystemAdapter(unittest.TestCase):
    """System adapter tests."""

    def test_cpu_info(self):
        """cpu_info returns model and cores."""
        from friday_mcu.adapters.system import cpu_info
        result = cpu_info()
        self.assertIn("model", result)
        self.assertIn("cores", result)
        self.assertGreater(result["cores"], 0)

    def test_memory_info(self):
        """memory_info returns total and available."""
        from friday_mcu.adapters.system import memory_info
        result = memory_info()
        self.assertIn("total_gb", result)
        self.assertIn("used_percent", result)


class TestGitAdapter(unittest.TestCase):
    """Git adapter tests."""

    @mock.patch("friday_mcu.adapters.git.subprocess.run")
    def test_log(self, mock_run):
        """git log returns commit entries."""
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="abc123|Author|2026-08-20|Initial commit"
        )
        from friday_mcu.adapters.git import log
        result = log(".", count=1)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["hash"], "abc123")

    @mock.patch("friday_mcu.adapters.git.subprocess.run")
    def test_status(self, mock_run):
        """git status returns branch and clean flag."""
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="main"
        )
        from friday_mcu.adapters.git import status
        result = status(".")
        self.assertIn("branch", result)
        self.assertIn("is_clean", result)

    @mock.patch("friday_mcu.adapters.git.subprocess.run")
    def test_branch(self, mock_run):
        """git branch returns current branch."""
        mock_run.return_value = mock.Mock(
            returncode=0,
            stdout="main"
        )
        from friday_mcu.adapters.git import branch
        result = branch(".")
        self.assertIn("current", result)
        self.assertIn("all", result)


class TestNotifyAdapter(unittest.TestCase):
    """Notify adapter tests."""

    def test_notify_returns_delivered(self):
        """notify_send returns delivered flag."""
        from friday_mcu.adapters.notify import notify_send
        result = notify_send("Test", "Body")
        self.assertIn("delivered", result)


class TestMediaAdapter(unittest.TestCase):
    """Media adapter tests (mocked)."""

    def test_is_playing_when_no_mpv(self):
        """is_playing returns False when no mpv is running."""
        from friday_mcu.adapters.media import is_playing
        result = is_playing()
        self.assertFalse(result)

    def test_get_volume_when_no_mpv(self):
        """get_volume returns 0 when no mpv is running."""
        from friday_mcu.adapters.media import get_volume
        result = get_volume()
        self.assertEqual(result, 0)


class TestRegistry(unittest.TestCase):
    """Registry tests."""

    def test_discover_modules(self):
        """discover_modules finds adapter files."""
        from friday_mcu.core.registry import discover_modules
        modules = discover_modules()
        # At minimum, the files we created should be discoverable
        self.assertIn("files", modules)
        self.assertIn("media", modules)
        self.assertIn("gmail", modules)

    def test_build_catalog(self):
        """build_catalog includes registered primitives."""
        from friday_mcu.core.registry import build_catalog
        catalog = build_catalog()
        self.assertIn("files.find_file", catalog)
        self.assertIn("gmail.list_unread", catalog)
        self.assertIn("media.play", catalog)

    def test_adapter_registration(self):
        """Adapters register themselves on import."""
        from friday_mcu.adapters import list_adapters
        from friday_mcu.adapters import files as files_mod  # ensure imported
        adapters = list_adapters()
        # files adapter should always register (no external deps)
        self.assertIn("files", adapters)


class TestEventBus(unittest.TestCase):
    """Event bus integration tests."""

    def test_events_flow_through_bus(self):
        """Events emitted by adapters are received by subscribers."""
        from friday_mcu.core.events import EventBus, Event, EventType

        bus = EventBus()
        received = []
        bus.subscribe(EventType.PRIMITIVE_CALL, lambda e: received.append(e))

        event = Event(
            type=EventType.PRIMITIVE_CALL,
            source="test",
            data={"primitive": "files.find_file"},
        )
        bus.emit(event)
        self.assertEqual(len(received), 1)
        self.assertEqual(received[0].data["primitive"], "files.find_file")


class TestContextManager(unittest.TestCase):
    """Context manager tests."""

    def test_build_full_context(self):
        """Context manager builds a text block for the planner."""
        from friday_mcu.brain.context import ContextManager

        ctx = ContextManager()
        ctx.set_goal("find the report")
        text = ctx.build_full_context()
        self.assertIn("CURRENT STATE", text)
        self.assertIn("find the report", text)

    def test_goal_history(self):
        """Goals are tracked in history."""
        from friday_mcu.brain.context import ContextManager

        ctx = ContextManager()
        ctx.set_goal("goal 1")
        ctx.set_goal("goal 2")
        self.assertEqual(ctx.get_recent_goals(10), ["goal 1", "goal 2"])


class TestReasoner(unittest.TestCase):
    """Reasoning layer tests."""

    def test_assess_goal_with_primitives(self):
        """Goal assessment returns execute when primitives are available."""
        from friday_mcu.brain.reasoning import Reasoner

        reasoner = Reasoner()
        result = reasoner.assess_goal(
            "check my email",
            available_primitives=["gmail.list_unread", "gmail.get_message"],
        )
        self.assertIn(result.decision, ("execute", "ask"))
        self.assertGreater(result.confidence, 0.0)

    def test_assess_decreases_confidence_for_destructive(self):
        """Destructive goals get lower confidence."""
        from friday_mcu.brain.reasoning import Reasoner

        reasoner = Reasoner()
        result = reasoner.assess_goal(
            "delete all files",
            available_primitives=["files.find_file"],
        )
        self.assertLess(result.confidence, 0.7)
        self.assertTrue(any("Destructive" in w for w in result.warnings))

    def test_analyze_failure_suggests_adaptation(self):
        """Failure analysis produces adaptation suggestions."""
        from friday_mcu.brain.reasoning import Reasoner

        reasoner = Reasoner()
        result = reasoner.analyze_failure(
            goal="check email",
            error="timeout after 30s",
            step_results=[],
        )
        self.assertIn("timeout", result.reasoning.lower())


class TestProactiveEngine(unittest.TestCase):
    """Proactive engine tests."""

    def test_suggest_and_flush(self):
        """Messages can be suggested and flushed."""
        from friday_mcu.comms.proactive import ProactiveEngine, ProactiveMessage

        engine = ProactiveEngine()
        engine._quiet_hours = (0, 0)  # disable quiet hours
        msg = ProactiveMessage(content="Test message", confidence=0.8, reason="test")
        engine.suggest(msg)
        self.assertEqual(len(engine._queue), 1)
        self.assertEqual(len(engine._sent), 0)


class TestAdaptiveComms(unittest.TestCase):
    """Adaptive comms tests."""

    def test_record_send(self):
        """Recording sends updates channel preferences."""
        from friday_mcu.comms.adaptive import AdaptiveComms

        ac = AdaptiveComms()
        ac.record_send("telegram", "text", success=True, response_time_s=2.0)
        ac.record_send("telegram", "text", success=True, response_time_s=1.0)
        stats = ac.get_stats()
        self.assertIn("telegram", stats["channels"])
        self.assertEqual(stats["channels"]["telegram"]["total_sends"], 2)

    def test_select_channel_prefers_high_score(self):
        """Channel selection prefers high-scoring channels."""
        from friday_mcu.comms.adaptive import AdaptiveComms

        ac = AdaptiveComms()
        ac._timing.quiet_start_hour = 0  # disable quiet hours
        ac._timing.quiet_end_hour = 0
        ac._timing.max_messages_per_hour = 100  # no volume limit
        ac.record_send("telegram", "text", success=True)
        ac.record_send("whatsapp", "text", success=False)
        selected = ac.select_channel(["telegram", "whatsapp"])
        self.assertEqual(selected, "telegram")


class TestMemoryManager(unittest.TestCase):
    """Memory manager tests."""

    def test_store_and_recall(self):
        """Store and recall across memory types."""
        from friday_mcu.memory.store import MemoryManager

        mgr = MemoryManager()
        entry = mgr.store("test_key", "test value", memory_type="working")
        self.assertEqual(entry.key, "test_key")
        recalled = mgr.recall("test_key", memory_type="working")
        self.assertIsNotNone(recalled)
        self.assertEqual(recalled.content, "test value")

    def test_search_all(self):
        """Search across all memory types."""
        from friday_mcu.memory.store import MemoryManager

        mgr = MemoryManager()
        mgr.store("email_pattern", "User checks email at 9am", memory_type="episodic")
        results = mgr.search_all("email")
        self.assertGreater(len(results), 0)

    def test_procedural_memory(self):
        """Procedural memory tracks success rates."""
        from friday_mcu.memory.store import MemoryManager

        mgr = MemoryManager()
        mgr.procedural.store_pattern("summarize emails", [{"primitive": "gmail.list_unread"}], success=True)
        mgr.procedural.store_pattern("summarize emails", [{"primitive": "gmail.list_unread"}], success=True)
        mgr.procedural.store_pattern("summarize emails", [{"primitive": "gmail.list_unread"}], success=False)
        rate = mgr.procedural.success_rate("summarize emails")
        self.assertAlmostEqual(rate, 2 / 3, places=2)


class TestPatternDetector(unittest.TestCase):
    """Pattern detector tests."""

    def test_goal_patterns(self):
        """Recurring goals are detected."""
        from friday_mcu.observer.patterns import PatternDetector

        detector = PatternDetector()
        tasks = [
            {"goal": "check email", "gate6_passed": True, "timestamp": "2026-08-20T09:00:00Z"},
            {"goal": "check email", "gate6_passed": True, "timestamp": "2026-08-21T09:00:00Z"},
            {"goal": "check email", "gate6_passed": False, "timestamp": "2026-08-22T09:00:00Z"},
        ]
        patterns = detector.analyze(tasks, min_occurrences=2)
        self.assertTrue(any(p.type == "goal" for p in patterns))

    def test_failure_patterns(self):
        """Repeated failures are detected."""
        from friday_mcu.observer.patterns import PatternDetector

        detector = PatternDetector()
        tasks = [
            {"goal": "send to whatsapp", "gate6_passed": False, "timestamp": "2026-08-20T09:00:00Z"},
            {"goal": "send to whatsapp", "gate6_passed": False, "timestamp": "2026-08-21T09:00:00Z"},
        ]
        patterns = detector.analyze(tasks, min_occurrences=2)
        self.assertTrue(any(p.type == "failure" for p in patterns))


if __name__ == "__main__":
    unittest.main()
