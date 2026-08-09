"""Contract registry + EXECUTOR_BLOCKED."""

from __future__ import annotations

import unittest

from friday.contracts import EXECUTOR_BLOCKED, REGISTRY, Idempotency, contract

# Ensure every L1 module registers its contracts (same as the planner does).
from friday.l1 import browser, dev, discord, files, gmail, media, notify, telegram, whatsapp, window  # noqa: F401
from friday.l1.window import shutdown  # noqa: F401


class TestRegistry(unittest.TestCase):
    def test_known_primitives_registered(self):
        for qualified in (
            "window.open_app", "window.close_all", "media.play_for", "browser.login",
            "files.find_file", "whatsapp.send_text", "telegram.send_document",
            "discord.send_file", "gmail.list_unread", "dev.run", "notify.notify_send",
        ):
            self.assertIn(qualified, REGISTRY, qualified)

    def test_registry_keys_are_module_qualified(self):
        # send_text exists in three modules; bare names must not collide.
        self.assertIn("whatsapp.send_text", REGISTRY)
        self.assertIn("telegram.send_text", REGISTRY)
        self.assertIn("discord.send_text", REGISTRY)

    def test_contract_carries_idempotency_and_docs(self):
        c = REGISTRY["whatsapp.send_text"]
        self.assertEqual(c.idempotency, Idempotency.AT_MOST_ONCE)
        self.assertTrue(c.precondition and c.postcondition and c.failure_mode)

    def test_read_only_primitives_are_idempotent(self):
        for q in ("window.list_clients", "media.is_playing", "files.find_file", "browser.read_page_text"):
            self.assertEqual(REGISTRY[q].idempotency, Idempotency.IDEMPOTENT, q)

    def test_blocked_primitive_still_registered(self):
        # window.shutdown keeps its contract (direct script calls work) but is
        # in EXECUTOR_BLOCKED so no plan path can reach it.
        self.assertIn("window.shutdown", REGISTRY)
        self.assertIn("window.shutdown", EXECUTOR_BLOCKED)

    def test_decorator_rejects_private_function_names(self):
        def _private():
            pass

        with self.assertRaises(TypeError):
            contract()(_private)

    def test_contract_wraps_and_attaches_contract(self):
        @contract(precondition="p", postcondition="q", idempotency=Idempotency.IDEMPOTENT, failure_mode="f")
        def dummy_primitive() -> str:
            """A docstring."""
            return "x"

        # The decoration registers into the process-wide REGISTRY; clean up
        # so a future test that iterates REGISTRY (e.g. a catalog snapshot)
        # never sees the ghost entry, and re-running discovery in-process
        # cannot accumulate duplicates.
        self.addCleanup(REGISTRY.pop, "test_registry.dummy_primitive", None)

        self.assertTrue(hasattr(dummy_primitive, "__contract__"))
        self.assertEqual(dummy_primitive.__contract__.name, "test_registry.dummy_primitive")
        self.assertEqual(REGISTRY["test_registry.dummy_primitive"].precondition, "p")


if __name__ == "__main__":
    unittest.main()
