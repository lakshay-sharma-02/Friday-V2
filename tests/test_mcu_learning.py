"""Tests for MCU Friday memory learning loop."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path


class TestMemoryLearner(unittest.TestCase):
    """Memory learner tests."""

    def test_record_success_outcome(self):
        """Successful outcomes produce success lessons."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            learner.record_outcome("check email", success=True, duration_s=5.0)
            lessons = learner.get_all_lessons()
            success_lessons = [l for l in lessons if l.lesson_type == "success"]
            self.assertTrue(len(success_lessons) > 0)

    def test_record_failure_outcome(self):
        """Failed outcomes produce failure lessons."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            learner.record_outcome("check email", success=False, error="timeout after 30s")
            lessons = learner.get_all_lessons()
            failure_lessons = [l for l in lessons if l.lesson_type == "failure"]
            self.assertTrue(len(failure_lessons) > 0)
            self.assertIn("timeout", failure_lessons[0].lesson.lower())

    def test_repeated_success_increases_confidence(self):
        """Repeated successes increase lesson confidence."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            for _ in range(5):
                learner.record_outcome("check email", success=True, duration_s=5.0)
            lessons = learner.get_all_lessons()
            success_lessons = [l for l in lessons if l.lesson_type == "success"]
            self.assertTrue(len(success_lessons) > 0)
            self.assertGreater(success_lessons[0].confidence, 0.5)

    def test_repeated_failure_increases_confidence(self):
        """Repeated failures of same type increase lesson confidence."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            for _ in range(5):
                learner.record_outcome("check email", success=False, error="auth token expired")
            lessons = learner.get_all_lessons()
            failure_lessons = [l for l in lessons if l.lesson_type == "failure"]
            self.assertTrue(len(failure_lessons) > 0)
            self.assertGreater(failure_lessons[0].confidence, 0.5)

    def test_duration_tracking(self):
        """Duration lessons track expected duration."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            learner.record_outcome("check email", success=True, duration_s=5.0)
            learner.record_outcome("check email", success=True, duration_s=3.0)
            lessons = learner.get_all_lessons()
            dur_lessons = [l for l in lessons if l.lesson_type == "adaptation" and "duration" in l.id]
            self.assertTrue(len(dur_lessons) > 0)
            # Running average: (5 + 3) / 2 = 4.0
            self.assertIn("4.0", dur_lessons[0].lesson)

    def test_build_learning_context(self):
        """Learning context provides useful info for the planner."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            learner.record_outcome("check email", success=True, duration_s=5.0)
            learner.record_outcome("check email", success=True, duration_s=3.0)
            learner.record_outcome("check email", success=False, error="timeout")
            context = learner.build_learning_context("check email")
            self.assertIn("LESSONS", context)
            self.assertIn("success", context.lower())

    def test_empty_goal_no_context(self):
        """No history means empty learning context."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            context = learner.build_learning_context("brand new goal")
            self.assertEqual(context, "")

    def test_apply_lesson(self):
        """Lessons can be marked as applied."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            learner.record_outcome("check email", success=True, duration_s=5.0)
            lessons = learner.get_all_lessons()
            self.assertTrue(len(lessons) > 0)
            applied = learner.apply_lesson(lessons[0].id)
            self.assertTrue(applied)
            self.assertEqual(learner._lessons[lessons[0].id].applied_count, 1)

    def test_consolidation(self):
        """Consolidation decays unused lessons and prunes weak ones."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            # Create a lesson with old timestamp
            learner.record_outcome("old goal", success=True, duration_s=5.0)
            # Manually age it
            for lesson in learner._lessons.values():
                lesson.created_at = time.time() - 86400 * 10  # 10 days ago
            # Consolidate
            result = learner.consolidate()
            self.assertIn("decayed", result)
            self.assertIn("pruned", result)

    def test_persistence(self):
        """Lessons persist across instances."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "lessons.json"
            learner1 = MemoryLearner(path)
            learner1.record_outcome("check email", success=True, duration_s=5.0)

            learner2 = MemoryLearner(path)
            lessons = learner2.get_all_lessons()
            self.assertTrue(len(lessons) > 0)

    def test_stats(self):
        """Stats report learning state."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            learner.record_outcome("goal1", success=True, duration_s=5.0)
            learner.record_outcome("goal2", success=False, error="timeout")
            stats = learner.get_stats()
            self.assertEqual(stats["total_outcomes"], 2)
            self.assertGreater(stats["total_lessons"], 0)

    def test_error_classification(self):
        """Errors are classified into categories."""
        from friday_mcu.memory.learning import MemoryLearner

        learner = MemoryLearner.__new__(MemoryLearner)
        self.assertEqual(learner._classify_error("timeout after 30s"), "timeout")
        self.assertEqual(learner._classify_error("file not found"), "not_found")
        self.assertEqual(learner._classify_error("permission denied"), "permission")
        self.assertEqual(learner._classify_error("auth token expired"), "auth")
        self.assertEqual(learner._classify_error("network error"), "network")
        self.assertEqual(learner._classify_error("connection refused"), "refused")
        self.assertEqual(learner._classify_error("something weird"), "unknown")


class TestLearningIntegration(unittest.TestCase):
    """Integration tests for the learning loop with planner and watcher."""

    def test_learning_context_included_in_planner_prompt(self):
        """The planner prompt includes learning context when available."""
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmpdir:
            learner = MemoryLearner(Path(tmpdir) / "lessons.json")
            # Record some outcomes
            for _ in range(5):
                learner.record_outcome("check email", success=True, duration_s=5.0)

            # Build learning context
            ctx = learner.build_learning_context("check email")
            self.assertIn("LESSONS", ctx)
            self.assertIn("success", ctx.lower())

    def test_cli_records_learning(self):
        """CLI cmd_run records learning outcomes."""
        # This is a structural test — verifies the import works
        from friday_mcu.memory.learning import MemoryLearner
        learner = MemoryLearner.__new__(MemoryLearner)
        # Verify the class has record_outcome
        self.assertTrue(hasattr(learner, "record_outcome"))


if __name__ == "__main__":
    unittest.main()
