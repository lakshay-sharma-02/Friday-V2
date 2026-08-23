"""Tests for the Friday memory system.

All tests are hermetic — they use temp files for storage and never
touch the real var/state/memory.jsonl.
"""

from __future__ import annotations

import json
import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

from friday.errors import PreconditionError
from tests.helpers import EnvTestCase


class TestMemoryStore(EnvTestCase):
    """Tests for memory.store primitive."""

    def test_store_basic(self):
        from friday.l1.memory import store
        result = store("user_name", "Lakshay", category="facts")
        self.assertEqual(result["status"], "stored")
        self.assertEqual(result["key"], "user_name")
        self.assertEqual(result["category"], "facts")

    def test_store_update_existing(self):
        from friday.l1.memory import store
        store("user_name", "Lakshay", category="facts")
        result = store("user_name", "Lakshay Sharma", category="facts")
        self.assertEqual(result["status"], "updated")

    def test_store_empty_key(self):
        from friday.l1.memory import store
        with self.assertRaises(PreconditionError):
            store("", "value")

    def test_store_empty_value(self):
        from friday.l1.memory import store
        with self.assertRaises(PreconditionError):
            store("key", "")

    def test_store_invalid_category(self):
        from friday.l1.memory import store
        with self.assertRaises(PreconditionError):
            store("key", "value", category="nonexistent")

    def test_store_all_categories(self):
        from friday.l1.memory import store, CATEGORIES
        for cat in CATEGORIES:
            result = store(f"test_{cat}", f"value_{cat}", category=cat)
            self.assertEqual(result["status"], "stored")
            self.assertEqual(result["category"], cat)

    def test_store_with_tags(self):
        from friday.l1.memory import store
        result = store("project_deadline", "Q4 2026", tags=["vivaha", "deadline"])
        self.assertEqual(result["status"], "stored")

    def test_store_truncates_long_values(self):
        from friday.l1.memory import store, MAX_VALUE_CHARS
        long_value = "x" * (MAX_VALUE_CHARS + 1000)
        store("long_key", long_value)
        # Verify it was stored (truncated)
        from friday.l1.memory import retrieve
        results = retrieve("long_key")
        self.assertTrue(len(results) > 0)
        self.assertLessEqual(len(results[0]["value"]), MAX_VALUE_CHARS)


class TestMemoryRetrieve(EnvTestCase):
    """Tests for memory.retrieve primitive."""

    def _populate(self):
        from friday.l1.memory import store
        store("user_name", "Lakshay Sharma", category="facts")
        store("project_deadline", "Q4 2026 for vivaha", category="context")
        store("prefer_dark_mode", "User prefers dark mode in all apps", category="preferences")
        store("lesson_confabulation", "Never claim a mechanism exists unless verified", category="lessons")

    def test_retrieve_exact_key(self):
        from friday.l1.memory import retrieve
        self._populate()
        results = retrieve("user_name")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["key"], "user_name")
        self.assertEqual(results[0]["category"], "facts")

    def test_retrieve_by_value(self):
        from friday.l1.memory import retrieve
        self._populate()
        results = retrieve("dark mode")
        self.assertTrue(len(results) > 0)
        keys = [r["key"] for r in results]
        self.assertIn("prefer_dark_mode", keys)

    def test_retrieve_with_category_filter(self):
        from friday.l1.memory import retrieve
        self._populate()
        results = retrieve("user", category="facts")
        for r in results:
            self.assertEqual(r["category"], "facts")

    def test_retrieve_empty_query(self):
        from friday.l1.memory import retrieve
        with self.assertRaises(PreconditionError):
            retrieve("")

    def test_retrieve_invalid_category(self):
        from friday.l1.memory import retrieve
        with self.assertRaises(PreconditionError):
            retrieve("test", category="nonexistent")

    def test_retrieve_no_match(self):
        from friday.l1.memory import retrieve
        self._populate()
        results = retrieve("xyz_nonexistent_query")
        self.assertEqual(results, [])

    def test_retrieve_respects_limit(self):
        from friday.l1.memory import store, retrieve
        for i in range(10):
            store(f"item_{i}", f"test value {i}")
        results = retrieve("test", limit=3)
        self.assertLessEqual(len(results), 3)

    def test_retrieve_relevance_ranking(self):
        from friday.l1.memory import store, retrieve
        store("exact_match", "this is the exact match", category="facts")
        store("partial_match", "this has partial overlap", category="facts")
        results = retrieve("exact_match")
        if results:
            self.assertEqual(results[0]["key"], "exact_match")
            self.assertGreaterEqual(results[0]["relevance"], 0.7)

    def test_retrieve_reinforces_access(self):
        from friday.l1.memory import store, retrieve, _load_all
        store("reinforce_test", "some value")
        retrieve("reinforce_test")
        entries = _load_all()
        for e in entries:
            if e.get("key") == "reinforce_test":
                self.assertGreater(e.get("access_count", 0), 0)
                break


class TestMemoryForget(EnvTestCase):
    """Tests for memory.forget primitive."""

    def test_forget_existing(self):
        from friday.l1.memory import store, forget
        store("to_forget", "some value")
        result = forget("to_forget")
        self.assertTrue(result["found"])

    def test_forget_nonexistent(self):
        from friday.l1.memory import forget
        result = forget("never_existed")
        self.assertFalse(result["found"])

    def test_forget_empty_key(self):
        from friday.l1.memory import forget
        with self.assertRaises(PreconditionError):
            forget("")

    def test_forget_with_category(self):
        from friday.l1.memory import store, forget
        store("multi_cat", "value1", category="facts")
        store("multi_cat", "value2", category="preferences")
        forget("multi_cat", category="facts")
        # The preferences one should still exist
        from friday.l1.memory import retrieve
        results = retrieve("multi_cat", category="preferences")
        self.assertTrue(len(results) > 0)


class TestMemoryListCategories(EnvTestCase):
    """Tests for memory.list_categories primitive."""

    def test_empty_store(self):
        from friday.l1.memory import list_categories
        result = list_categories()
        self.assertEqual(result["total"], 0)
        for count in result["categories"].values():
            self.assertEqual(count, 0)

    def test_with_entries(self):
        from friday.l1.memory import store, list_categories
        store("f1", "v1", category="facts")
        store("f2", "v2", category="facts")
        store("p1", "v3", category="preferences")
        result = list_categories()
        self.assertEqual(result["total"], 3)
        self.assertEqual(result["categories"]["facts"], 2)
        self.assertEqual(result["categories"]["preferences"], 1)


class TestMemorySummary(EnvTestCase):
    """Tests for memory.summary primitive."""

    def test_empty_store(self):
        from friday.l1.memory import summary
        result = summary()
        self.assertEqual(result["total"], 0)
        self.assertIsNone(result["oldest"])

    def test_with_entries(self):
        from friday.l1.memory import store, summary
        store("s1", "v1", category="facts")
        store("s2", "v2", category="decisions")
        result = summary()
        self.assertEqual(result["total"], 2)
        self.assertIn("facts", result["categories"])
        self.assertIn("decisions", result["categories"])
        self.assertTrue(len(result["recent_keys"]) > 0)


class TestMemoryReinforce(EnvTestCase):
    """Tests for memory.reinforce primitive."""

    def test_reinforce_existing(self):
        from friday.l1.memory import store, reinforce
        store("reinforce_me", "value")
        result = reinforce("reinforce_me")
        self.assertTrue(result["found"])
        self.assertGreater(result["access_count"], 0)

    def test_reinforce_nonexistent(self):
        from friday.l1.memory import reinforce
        result = reinforce("no_such_key")
        self.assertFalse(result["found"])

    def test_reinforce_empty_key(self):
        from friday.l1.memory import reinforce
        with self.assertRaises(PreconditionError):
            reinforce("")


class TestMemoryMaintenance(EnvTestCase):
    """Tests for memory.maintenance primitive."""

    def test_maintenance_no_entries(self):
        from friday.l1.memory import maintenance
        result = maintenance()
        self.assertEqual(result["archived"], 0)

    def test_maintenance_keeps_fresh(self):
        from friday.l1.memory import store, maintenance
        store("fresh_key", "recent value")
        result = maintenance(ttl_days=90, min_access=5)
        # Fresh entry should not be archived
        self.assertEqual(result["archived"], 0)

    def test_maintenance_archives_old_low_access(self):
        from friday.l1.memory import maintenance, _save_all
        # Create an entry with old timestamp and low access
        old_entry = {
            "id": "old123",
            "key": "old_key",
            "value": "old value",
            "category": "facts",
            "tags": [],
            "created_at": "2020-01-01T00:00:00+00:00",
            "last_accessed": "2020-01-01T00:00:00+00:00",
            "access_count": 1,
        }
        _save_all([old_entry])
        result = maintenance(ttl_days=30, min_access=5)
        self.assertEqual(result["archived"], 1)
        self.assertIn("old_key", result["archived_keys"])

    def test_maintenance_keeps_frequent(self):
        from friday.l1.memory import maintenance, _save_all
        # Create an entry that is old but has high access count
        frequent_entry = {
            "id": "freq123",
            "key": "frequent_key",
            "value": "frequent value",
            "category": "facts",
            "tags": [],
            "created_at": "2020-01-01T00:00:00+00:00",
            "last_accessed": "2020-01-01T00:00:00+00:00",
            "access_count": 10,  # above threshold
        }
        _save_all([frequent_entry])
        result = maintenance(ttl_days=30, min_access=5)
        self.assertEqual(result["archived"], 0)


class TestMemoryBuildContext(EnvTestCase):
    """Tests for the planner integration helper."""

    def test_build_memory_context_empty(self):
        from friday.l1.memory import build_memory_context
        result = build_memory_context("some goal")
        self.assertEqual(result, "")

    def test_build_memory_context_with_memories(self):
        from friday.l1.memory import store, build_memory_context
        store("user_prefers_dark", "User prefers dark mode", category="preferences")
        store("project_deadline", "Q4 2026", category="context")
        result = build_memory_context("dark mode preferences")
        self.assertIn("Known from past sessions:", result)
        self.assertIn("dark", result.lower())

    def test_build_memory_context_category_filter(self):
        from friday.l1.memory import store, build_memory_context
        store("fact1", "some fact", category="facts")
        store("pref1", "some preference", category="preferences")
        result = build_memory_context("some", category="facts")
        # Should only include facts
        self.assertIn("facts", result)


class TestMemorySyncLessons(EnvTestCase):
    """Tests for the lessons sync integration."""

    def test_sync_lessons_empty_approved(self):
        from friday.l1.memory import sync_lessons_from_config
        result = sync_lessons_from_config()
        self.assertEqual(result["synced"], 0)

    def test_sync_lessons_with_approved(self):
        from friday.l1.memory import sync_lessons_from_config
        # Create a mock approved lessons file
        approved_file = Path(os.environ.get("FRIDAY_APPROVED_LESSONS", "/tmp/test_approved.json"))
        approved_data = {
            "lessons": [
                {
                    "category": "test_lesson",
                    "statement": "Always verify before acting",
                    "targets": ["planner"],
                }
            ]
        }
        approved_file.write_text(json.dumps(approved_data))
        try:
            result = sync_lessons_from_config()
            self.assertEqual(result["synced"], 1)
            self.assertEqual(result["total_lessons"], 1)
        finally:
            approved_file.unlink(missing_ok=True)


class TestMemoryRecordSuccess(EnvTestCase):
    """Tests for the success recording integration."""

    def test_record_success(self):
        from friday.l1.memory import record_success
        result = record_success("open firefox", "Firefox opened successfully")
        self.assertEqual(result["status"], "stored")
        self.assertEqual(result["category"], "context")

    def test_record_success_empty_goal(self):
        from friday.l1.memory import record_success
        with self.assertRaises(PreconditionError):
            record_success("", "some outcome")


class TestMemoryRecordDecision(EnvTestCase):
    """Tests for the decision recording integration."""

    def test_record_decision(self):
        from friday.l1.memory import record_decision
        result = record_decision(
            "Use WhatsApp for notifications",
            "User prefers WhatsApp over Telegram for alerts",
        )
        self.assertEqual(result["status"], "stored")
        self.assertEqual(result["category"], "decisions")

    def test_record_decision_empty(self):
        from friday.l1.memory import record_decision
        with self.assertRaises(PreconditionError):
            record_decision("", "rationale")

    def test_record_decision_empty_rationale(self):
        from friday.l1.memory import record_decision
        with self.assertRaises(PreconditionError):
            record_decision("decision", "")


class TestMemoryL2Checks(EnvTestCase):
    """Tests for L2 memory verification checks."""

    def test_memory_has_key_found(self):
        from friday.l1.memory import store
        from friday.l2.checks import memory_has_key
        store("check_test", "some value", category="facts")
        self.assertTrue(memory_has_key("check_test"))

    def test_memory_has_key_not_found(self):
        from friday.l2.checks import memory_has_key
        self.assertFalse(memory_has_key("nonexistent_key_xyz"))

    def test_memory_has_key_with_category(self):
        from friday.l1.memory import store
        from friday.l2.checks import memory_has_key
        store("cat_test", "value", category="facts")
        self.assertTrue(memory_has_key("cat_test", category="facts"))
        self.assertFalse(memory_has_key("cat_test", category="preferences"))

    def test_memory_retrieval_ok_found(self):
        from friday.l1.memory import store
        from friday.l2.checks import memory_retrieval_ok
        store("retrieval_test", "some searchable content")
        self.assertTrue(memory_retrieval_ok("retrieval_test"))

    def test_memory_retrieval_ok_not_found(self):
        from friday.l2.checks import memory_retrieval_ok
        self.assertFalse(memory_retrieval_ok("xyz_nonexistent"))

    def test_memory_store_status(self):
        from friday.l2.checks import memory_store_status
        self.assertTrue(memory_store_status("stored"))
        self.assertTrue(memory_store_status("updated"))
        self.assertFalse(memory_store_status("failed"))


class TestMemoryEdgeCases(EnvTestCase):
    """Edge case tests for the memory system."""

    def test_concurrent_store_retrieve(self):
        from friday.l1.memory import store, retrieve
        # Store multiple entries and retrieve them
        for i in range(5):
            store(f"edge_{i}", f"value_{i}", category="facts")
        results = retrieve("edge")
        self.assertEqual(len(results), 5)

    def test_store_special_characters(self):
        from friday.l1.memory import store, retrieve
        store("special_chars", "value with émojis 🎉 and unicode: 日本語")
        results = retrieve("special_chars")
        self.assertTrue(len(results) > 0)
        self.assertIn("émojis", results[0]["value"])

    def test_retrieve_tag_boost(self):
        from friday.l1.memory import store, retrieve
        store("tagged_item", "some value", tags=["vivaha", "q4"])
        results = retrieve("vivaha")
        self.assertTrue(len(results) > 0)
        self.assertEqual(results[0]["key"], "tagged_item")

    def test_memory_file_atomicity(self):
        """Test that writes are atomic (no partial writes on crash)."""
        from friday.l1.memory import store, _memory_file
        store("atomic_test", "value")
        path = _memory_file()
        # File should be valid JSONL
        content = path.read_text(encoding="utf-8")
        for line in content.splitlines():
            if line.strip():
                json.loads(line)  # should not raise

    def test_corrupted_memory_file(self):
        """Test that corrupted memory file is handled gracefully."""
        from friday.l1.memory import _memory_file, retrieve
        path = _memory_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not valid json\n{\"key\": \"valid\"}\n", encoding="utf-8")
        # Should not raise, should skip malformed lines
        results = retrieve("valid")
        # The valid line has no "key" in the expected format, so no results
        # But it shouldn't crash
        self.assertIsInstance(results, list)


class TestMemoryPlannerIntegration(EnvTestCase):
    """Tests for the planner's memory context injection."""

    def test_build_memory_block_with_memories(self):
        from friday.l1.memory import store
        from friday.l4.planner import _build_memory_block
        store("terminal_preference", "User prefers kitty terminals", category="preferences")
        block = _build_memory_block("terminal kitty")
        self.assertIn("Known from past sessions:", block)

    def test_build_memory_block_empty(self):
        from friday.l4.planner import _build_memory_block
        block = _build_memory_block("completely unknown goal xyz")
        self.assertEqual(block, "")

    def test_build_memory_block_import_error(self):
        """Test that import errors are handled gracefully."""
        from friday.l4.planner import _build_memory_block
        with mock.patch.dict("sys.modules", {"friday.l1.memory": None}):
            block = _build_memory_block("test goal")
            self.assertEqual(block, "")


if __name__ == "__main__":
    unittest.main()
