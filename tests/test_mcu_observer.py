"""Tests for MCU Friday observer modules."""

from __future__ import annotations

import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock


class TestPredictionEngine(unittest.TestCase):
    """Prediction engine tests."""

    def test_predict_next_goal(self):
        """Recurring goals produce predictions."""
        from friday_mcu.observer.predictions import PredictionEngine

        engine = PredictionEngine()
        tasks = [
            {"goal": "check email", "gate6_passed": True, "timestamp": f"2026-08-2{i}T09:00:00Z"}
            for i in range(5)
        ]
        predictions = engine.generate_predictions(tasks)
        goal_preds = [p for p in predictions if p.type == "goal"]
        self.assertTrue(len(goal_preds) > 0)
        self.assertGreater(goal_preds[0].confidence, 0.0)

    def test_predict_timing(self):
        """Repeated goals at the same hour produce timing predictions."""
        from friday_mcu.observer.predictions import PredictionEngine

        engine = PredictionEngine()
        tasks = [
            {"goal": "check email", "gate6_passed": True, "timestamp": f"2026-08-2{i}T09:00:00Z"}
            for i in range(5)
        ]
        predictions = engine.generate_predictions(tasks)
        timing_preds = [p for p in predictions if p.type == "timing"]
        self.assertTrue(len(timing_preds) > 0)

    def test_predict_success_rate(self):
        """Goals with mixed results produce success rate predictions."""
        from friday_mcu.observer.predictions import PredictionEngine

        engine = PredictionEngine()
        tasks = [
            {"goal": "send to whatsapp", "gate6_passed": True, "timestamp": "2026-08-20T09:00:00Z"},
            {"goal": "send to whatsapp", "gate6_passed": True, "timestamp": "2026-08-21T09:00:00Z"},
            {"goal": "send to whatsapp", "gate6_passed": False, "timestamp": "2026-08-22T09:00:00Z"},
            {"goal": "send to whatsapp", "gate6_passed": True, "timestamp": "2026-08-23T09:00:00Z"},
        ]
        predictions = engine.generate_predictions(tasks)
        success_preds = [p for p in predictions if p.type == "success_rate"]
        self.assertTrue(len(success_preds) > 0)
        # Predicted value is the success rate (3/4 = 0.75)
        self.assertAlmostEqual(success_preds[0].predicted_value, 0.75, places=2)

    def test_prediction_validity(self):
        """Predictions expire after their validity window."""
        from friday_mcu.observer.predictions import Prediction

        p = Prediction(
            id="test", type="goal", description="test",
            confidence=0.5, valid_until_s=0.1,
        )
        self.assertTrue(p.is_valid())
        time.sleep(0.15)
        self.assertFalse(p.is_valid())

    def test_empty_tasks_no_predictions(self):
        """Empty task list produces no predictions."""
        from friday_mcu.observer.predictions import PredictionEngine

        engine = PredictionEngine()
        predictions = engine.generate_predictions([])
        self.assertEqual(len(predictions), 0)

    def test_prediction_to_dict(self):
        """Prediction serialization works."""
        from friday_mcu.observer.predictions import Prediction

        p = Prediction(
            id="test", type="goal", description="test prediction",
            confidence=0.8, predicted_value="check email",
            evidence=["observed 5 times"],
        )
        d = p.to_dict()
        self.assertEqual(d["id"], "test")
        self.assertEqual(d["type"], "goal")
        self.assertEqual(d["confidence"], 0.8)


class TestUserModel(unittest.TestCase):
    """User model tests."""

    def test_record_and_get_preference(self):
        """Preferences can be recorded and retrieved."""
        from friday_mcu.observer.user_model import UserModel

        with tempfile.TemporaryDirectory() as tmpdir:
            model = UserModel(Path(tmpdir) / "model.json")
            model.record_preference("preferred_channel", "telegram")
            self.assertEqual(model.get_preference("preferred_channel"), "telegram")

    def test_preference_confidence_increase(self):
        """Repeated same-value observations increase confidence."""
        from friday_mcu.observer.user_model import UserModel

        with tempfile.TemporaryDirectory() as tmpdir:
            model = UserModel(Path(tmpdir) / "model.json")
            model.record_preference("pref", "value1")
            model.record_preference("pref", "value1")
            model.record_preference("pref", "value1")
            pref = model._preferences["pref"]
            self.assertGreater(pref.confidence, 0.5)
            self.assertEqual(pref.evidence_count, 3)

    def test_preference_new_value_replaces_if_higher_confidence(self):
        """Higher confidence new value replaces old."""
        from friday_mcu.observer.user_model import UserModel

        with tempfile.TemporaryDirectory() as tmpdir:
            model = UserModel(Path(tmpdir) / "model.json")
            model.record_preference("pref", "old", confidence=0.3)
            model.record_preference("pref", "new", confidence=0.8)
            self.assertEqual(model.get_preference("pref"), "new")

    def test_low_confidence_preference_returns_none(self):
        """Low confidence preferences are hidden."""
        from friday_mcu.observer.user_model import UserModel

        with tempfile.TemporaryDirectory() as tmpdir:
            model = UserModel(Path(tmpdir) / "model.json")
            model.record_preference("pref", "value", confidence=0.2)
            self.assertIsNone(model.get_preference("pref"))

    def test_observe_goal_records_history(self):
        """Goal observations are recorded."""
        from friday_mcu.observer.user_model import UserModel

        with tempfile.TemporaryDirectory() as tmpdir:
            model = UserModel(Path(tmpdir) / "model.json")
            model.observe_goal("check email", success=True, platform="telegram")
            self.assertEqual(len(model._goal_history), 1)
            self.assertEqual(model._goal_history[0]["goal"], "check email")

    def test_observe_goal_detects_habits(self):
        """Repeated goals at similar times create habits."""
        from friday_mcu.observer.user_model import UserModel

        with tempfile.TemporaryDirectory() as tmpdir:
            model = UserModel(Path(tmpdir) / "model.json")
            for i in range(5):
                model.observe_goal("check email", success=True)
            habits = model.get_habits()
            self.assertTrue(len(habits) > 0)

    def test_build_context(self):
        """Context builder produces text for the planner."""
        from friday_mcu.observer.user_model import UserModel

        with tempfile.TemporaryDirectory() as tmpdir:
            model = UserModel(Path(tmpdir) / "model.json")
            model.record_preference("preferred_channel", "telegram")
            ctx = model.build_context()
            self.assertIn("preferred_channel", ctx)
            self.assertIn("telegram", ctx)

    def test_persistence(self):
        """Model persists across instances."""
        from friday_mcu.observer.user_model import UserModel

        with tempfile.TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "model.json"
            model1 = UserModel(path)
            model1.record_preference("pref", "value")
            model1.observe_goal("test", success=True)

            model2 = UserModel(path)
            self.assertEqual(model2.get_preference("pref"), "value")
            self.assertEqual(len(model2._goal_history), 1)

    def test_stats(self):
        """Stats report model state."""
        from friday_mcu.observer.user_model import UserModel

        with tempfile.TemporaryDirectory() as tmpdir:
            model = UserModel(Path(tmpdir) / "model.json")
            model.record_preference("p1", "v1")
            model.record_preference("p2", "v2")
            stats = model.get_stats()
            self.assertEqual(stats["preferences"], 2)


class TestAnomalyDetector(unittest.TestCase):
    """Anomaly detector tests."""

    def test_failure_streak_detected(self):
        """Consecutive failures produce an anomaly."""
        from friday_mcu.observer.anomalies import AnomalyDetector

        detector = AnomalyDetector()
        tasks = [
            {"goal": "send to whatsapp", "gate6_passed": False, "timestamp": f"2026-08-2{i}T09:00:00Z"}
            for i in range(5)
        ]
        anomalies = detector.detect(tasks)
        streak_anomalies = [a for a in anomalies if a.type == "failure_streak"]
        self.assertTrue(len(streak_anomalies) > 0)
        self.assertIn("5 times", streak_anomalies[0].description)

    def test_no_streak_on_successes(self):
        """Successful goals don't produce failure streaks."""
        from friday_mcu.observer.anomalies import AnomalyDetector

        detector = AnomalyDetector()
        tasks = [
            {"goal": "check email", "gate6_passed": True, "timestamp": f"2026-08-2{i}T09:00:00Z"}
            for i in range(5)
        ]
        anomalies = detector.detect(tasks)
        streak_anomalies = [a for a in anomalies if a.type == "failure_streak"]
        self.assertEqual(len(streak_anomalies), 0)

    def test_performance_degradation(self):
        """Goals taking much longer than usual produce anomalies."""
        from friday_mcu.observer.anomalies import AnomalyDetector

        detector = AnomalyDetector()
        tasks = [
            {"goal": "check email", "gate6_passed": True, "duration_s": 5, "timestamp": f"2026-08-2{i}T09:00:00Z"}
            for i in range(5)
        ] + [
            {"goal": "check email", "gate6_passed": True, "duration_s": 60, "timestamp": "2026-08-25T09:00:00Z"}
        ]
        anomalies = detector.detect(tasks)
        perf_anomalies = [a for a in anomalies if a.type == "performance"]
        self.assertTrue(len(perf_anomalies) > 0)

    def test_anomaly_severity_sorting(self):
        """Anomalies are sorted by severity."""
        from friday_mcu.observer.anomalies import AnomalyDetector

        detector = AnomalyDetector()
        tasks = [
            {"goal": "fail1", "gate6_passed": False, "timestamp": f"2026-08-2{i}T09:00:00Z"}
            for i in range(5)
        ] + [
            {"goal": "fail2", "gate6_passed": False, "timestamp": f"2026-08-2{i}T10:00:00Z"}
            for i in range(8)
        ]
        anomalies = detector.detect(tasks)
        if len(anomalies) >= 2:
            severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
            for i in range(len(anomalies) - 1):
                self.assertLessEqual(
                    severity_order.get(anomalies[i].severity, 4),
                    severity_order.get(anomalies[i + 1].severity, 4),
                )

    def test_anomaly_to_dict(self):
        """Anomaly serialization works."""
        from friday_mcu.observer.anomalies import Anomaly

        a = Anomaly(
            id="test", type="failure_streak", severity="high",
            description="test anomaly", evidence=[{"key": "val"}],
        )
        d = a.to_dict()
        self.assertEqual(d["id"], "test")
        self.assertEqual(d["severity"], "high")

    def test_resolve_anomaly(self):
        """Anomalies can be marked as resolved."""
        from friday_mcu.observer.anomalies import AnomalyDetector

        detector = AnomalyDetector()
        tasks = [
            {"goal": "fail", "gate6_passed": False, "timestamp": f"2026-08-2{i}T09:00:00Z"}
            for i in range(5)
        ]
        anomalies = detector.detect(tasks)
        if anomalies:
            resolved = detector.resolve(anomalies[0].id)
            self.assertTrue(resolved)
            self.assertTrue(detector._anomalies[anomalies[0].id].auto_resolved)

    def test_empty_tasks_no_anomalies(self):
        """Empty task list produces no anomalies."""
        from friday_mcu.observer.anomalies import AnomalyDetector

        detector = AnomalyDetector()
        anomalies = detector.detect([])
        self.assertEqual(len(anomalies), 0)

    def test_stats(self):
        """Stats report detector state."""
        from friday_mcu.observer.anomalies import AnomalyDetector

        detector = AnomalyDetector()
        tasks = [
            {"goal": "fail", "gate6_passed": False, "timestamp": f"2026-08-2{i}T09:00:00Z"}
            for i in range(5)
        ]
        detector.detect(tasks)
        stats = detector.get_stats()
        self.assertGreater(stats["total_anomalies"], 0)


if __name__ == "__main__":
    unittest.main()
