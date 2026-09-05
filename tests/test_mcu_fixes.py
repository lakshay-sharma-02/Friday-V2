"""Regression tests for the correctness-fix pass.

Covers:
- Executor verification discipline (a failed verify or an unresolvable
  $steps reference must ABORT loudly, never report COMPLETED).
- dev.run subprocess invocation (no POSIX shell=True list bug).
- L2 checks reading real state through read-only module accessors.
- Planner arg-signature validation, template hardening, cache isolation.
- Memory decay/prune persistence and learner matching/duration fixes.
- Watcher inline deterministic plans execute without the LLM; file-trigger
  seen state survives restarts.
- Telegram offset commit model + Discord channel watermark.
- Event bus thread safety and unsubscribe.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import threading
import time
import types
import unittest
from pathlib import Path
from unittest import mock

from friday_mcu.core.contracts import REGISTRY, Contract, Idempotency
from friday_mcu.core.errors import FridayError


# ---------------------------------------------------------------------------
# Test double primitives (module-level, contract-registered, executor-callable)
# ---------------------------------------------------------------------------

_FAKE_MOD = types.ModuleType("friday_mcu.adapters.fake")


def _fake_touch(path: str) -> dict:
    """Write the file AND return a truthy dict — used to prove that a lying
    return value can no longer pass a failing verify."""
    Path(path).write_text("x", encoding="utf-8")
    return {"ok": True, "path": path}


def _fake_echo(**kwargs) -> dict:
    return dict(kwargs)


_fake_touch.__contract__ = Contract(
    name="fake.touch",
    precondition="",
    postcondition="",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="",
)
_fake_echo.__contract__ = Contract(
    name="fake.echo",
    precondition="",
    postcondition="",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="",
)
REGISTRY["fake.touch"] = _fake_touch.__contract__
REGISTRY["fake.echo"] = _fake_echo.__contract__
_FAKE_MOD.touch = _fake_touch
_FAKE_MOD.echo = _fake_echo
sys.modules[_FAKE_MOD.__name__] = _FAKE_MOD


def _small_plan(path: str, nonexistent: str) -> dict:
    """Write `path`, but verify a DIFFERENT file that will never exist."""
    return {
        "goal": "write config file",
        "steps": [
            {
                "primitive": "fake.touch",
                "args": {"path": path},
                "verify_wait_s": 0.1,
                "verify": {
                    "check": "checks.file_exists",
                    "args": {"path": nonexistent},
                    "expect": True,
                },
            }
        ],
    }


class TestExecutorVerifyDiscipline(unittest.TestCase):
    """A step may only end VERIFIED; failed verifies and dead refs ABORT."""

    def test_failed_verify_aborts_not_completes(self):
        from friday_mcu.brain.executor import run_plan

        with tempfile.TemporaryDirectory() as tmp:
            written = str(Path(tmp) / "real.txt")
            phantom = str(Path(tmp) / "phantom.txt")
            with self.assertRaises(FridayError) as ctx:
                run_plan(_small_plan(written, phantom))
            self.assertIn("aborted", str(ctx.exception).lower())
            # The primitive DID run (file written) but the goal must not pass.
            self.assertTrue(Path(written).exists())
            self.assertFalse(Path(phantom).exists())

    def test_passing_verify_verifies(self):
        from friday_mcu.brain.executor import run_plan

        with tempfile.TemporaryDirectory() as tmp:
            written = str(Path(tmp) / "real.txt")
            plan = {
                "goal": "write config file",
                "steps": [
                    {
                        "primitive": "fake.touch",
                        "args": {"path": written},
                        "verify_wait_s": 0.1,
                        "verify": {
                            "check": "checks.file_exists",
                            "args": {"path": written},
                            "expect": True,
                        },
                    }
                ],
            }
            result = run_plan(plan)
            self.assertEqual(result.status, "COMPLETED")
            self.assertEqual(result.steps[0].status, "VERIFIED")

    def test_unresolvable_ref_aborts(self):
        from friday_mcu.brain.executor import run_plan

        plan = {
            "goal": "chain on missing data",
            "steps": [
                {
                    "primitive": "fake.echo",
                    "args": {"a": 1},
                    "verify": {"check": "checks.call_succeeded", "args": {"value": "$steps.1.result"}, "expect": True},
                },
                {
                    "primitive": "fake.echo",
                    "args": {"b": "$steps.1.result.nope"},
                    "verify": {"check": "checks.call_succeeded", "args": {"value": "$steps.2.result"}, "expect": True},
                },
            ],
        }
        with self.assertRaises(FridayError) as ctx:
            run_plan(plan)
        self.assertIn("aborted", str(ctx.exception).lower())


class TestDevRunInvocation(unittest.TestCase):
    """dev.run must exec claude directly on POSIX (never shell=True + list)."""

    def _fake_completed(self, stdout: str):
        return subprocess.CompletedProcess(args=[], returncode=0, stdout=stdout, stderr="")

    def test_posix_no_shell_and_flags_preserved(self):
        import friday_mcu.adapters.dev as dev

        with mock.patch.object(dev.sys, "platform", "linux"), \
             mock.patch.object(dev.subprocess, "run", return_value=self._fake_completed('{"result":"ok","is_error":false}')) as mrun:
            result = dev.run("say hi", model="haiku")
        self.assertEqual(result["result"], "ok")
        args, kwargs = mrun.call_args
        # List form, executed directly — no shell=True dropping the flags.
        self.assertIsInstance(args[0], list)
        self.assertNotIn("shell", kwargs)
        joined = " ".join(args[0])
        self.assertIn("-p", joined)
        self.assertIn("--output-format", joined)
        self.assertIn("--model haiku", joined)

    def test_windows_uses_shell_with_joined_command(self):
        import friday_mcu.adapters.dev as dev

        with mock.patch.object(dev.sys, "platform", "win32"), \
             mock.patch.object(dev.subprocess, "run", return_value=self._fake_completed('{"result":"ok","is_error":false}')) as mrun:
            dev.run("say hi", model="opus")
        args, kwargs = mrun.call_args
        self.assertIsInstance(args[0], str)
        self.assertTrue(kwargs.get("shell"))

    def test_bypass_requires_dangerous_env(self):
        import friday_mcu.adapters.dev as dev
        from friday_mcu.core.errors import PreconditionError

        with mock.patch.dict("os.environ", {"FRIDAY_ALLOW_DANGEROUS": ""}):
            with self.assertRaises(PreconditionError):
                dev.run("hi", allow_bypass_permissions=True)


class TestChecksReadRealState(unittest.TestCase):
    """Checks must call read-only module accessors, not the phantom
    adapter.execute_sync path that never existed."""

    def test_window_checks_read_live_clients(self):
        from friday_mcu.brain import checks

        clients = [{"class": "kitty", "address": "0x1"}, {"class": "firefox", "address": "0x2"}]
        with mock.patch("friday_mcu.adapters.window.list_clients", return_value=clients):
            self.assertEqual(checks.window_client_count(), 2)
            self.assertTrue(checks.window_has_class("kitty"))
            self.assertFalse(checks.window_has_class("emacs"))

    def test_gmail_check_uses_module_primitive(self):
        from friday_mcu.brain import checks

        with mock.patch("friday_mcu.adapters.gmail.list_unread", return_value=[{"message_id": "m1"}]) as m:
            self.assertTrue(checks.gmail_unread_exists(sender="boss@x.com"))
            m.assert_called_once_with(sender="boss@x.com", max_results=1)

        with mock.patch("friday_mcu.adapters.gmail.list_unread", side_effect=Exception("boom")):
            self.assertFalse(checks.gmail_unread_exists())


class TestPlannerValidationAndTemplates(unittest.TestCase):
    """Arg names must be validated against real signatures; templates must be
    executable and never fabricate messages."""

    def test_validate_rejects_unknown_arg(self):
        from friday_mcu.brain.planner import validate_plan

        plan = {
            "goal": "git log",
            "steps": [
                {
                    "primitive": "git.log",
                    "args": {"max_count": 10},
                    "verify": {"check": "checks.list_nonempty", "args": {"value": "$steps.1.result"}, "expect": True},
                }
            ],
        }
        ok, errors = validate_plan(plan)
        self.assertFalse(ok)
        self.assertTrue(any("max_count" in e for e in errors))

    def test_validate_rejects_missing_required_arg(self):
        from friday_mcu.brain.planner import validate_plan

        plan = {
            "goal": "open app",
            "steps": [
                {
                    "primitive": "window.open_app",
                    "args": {},
                    "verify": {"check": "checks.call_succeeded", "args": {"value": "$steps.1.result"}, "expect": True},
                }
            ],
        }
        ok, errors = validate_plan(plan)
        self.assertFalse(ok)
        self.assertTrue(any("command" in e for e in errors))

    def test_git_template_uses_correct_arg(self):
        from friday_mcu.brain.planner import validate_plan
        from friday_mcu.brain.templates import match_template

        plan = match_template("show recent git commits")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["steps"][0]["args"], {"count": 10})
        ok, errors = validate_plan(plan)
        self.assertTrue(ok, errors)

    def test_system_template_valid(self):
        from friday_mcu.brain.planner import validate_plan
        from friday_mcu.brain.templates import match_template

        plan = match_template("what is my system info")
        self.assertIsNotNone(plan)
        prims = [s["primitive"] for s in plan["steps"]]
        self.assertEqual(prims, ["system.cpu_info", "system.memory_info"])
        ok, errors = validate_plan(plan)
        self.assertTrue(ok, errors)

    def test_send_template_never_fabricates_default(self):
        from friday_mcu.brain.templates import match_template

        # No extractable message + no 'on' pattern -> fall through to the LLM.
        self.assertIsNone(match_template("send hi to discord"))
        # Quoted message extracts cleanly.
        plan = match_template("send 'hello world' to discord")
        self.assertIsNotNone(plan)
        self.assertEqual(plan["steps"][0]["primitive"], "discord.send_text")
        self.assertEqual(plan["steps"][0]["args"], {"text": "hello world"})

    def test_cache_returns_isolated_copies(self):
        from friday_mcu.brain import planner

        key = planner._cache_key("g")
        entry = {
            "plan": {"goal": "g", "confidence": 0.9, "steps": [{"primitive": "git.log", "args": {"count": 5}}]},
            "timestamp": time.time(),
            "hits": 0,
        }
        planner._PLAN_CACHE[key] = entry
        try:
            first = planner._get_cached_plan("g")
            first.steps[0]["args"]["count"] = 999
            second = planner._get_cached_plan("g")
            self.assertEqual(second.steps[0]["args"]["count"], 5)
        finally:
            planner._PLAN_CACHE.pop(key, None)


class TestMemoryPersistence(unittest.TestCase):
    """Decay and prune must survive a reload."""

    def test_consolidate_decay_persisted(self):
        from friday_mcu.memory.store import EpisodicMemory

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "episodic.jsonl"
            mem = EpisodicMemory(path)
            entry = mem.store("k1", "old content")
            entry.created_at = time.time() - 86400 * 60  # 60 days old
            mem.consolidate()

            reloaded = EpisodicMemory(path)
            self.assertLess(reloaded.recall("k1").strength, 1.0)

    def test_prune_persisted(self):
        from friday_mcu.memory.store import EpisodicMemory

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "episodic.jsonl"
            mem = EpisodicMemory(path)
            weak = mem.store("weak", "x")
            weak.strength = 0.01
            mem.store("strong", "y")
            removed = mem.prune(threshold=0.5)
            self.assertEqual(removed, 1)

            reloaded = EpisodicMemory(path)
            self.assertIsNone(reloaded.recall("weak"))
            self.assertIsNotNone(reloaded.recall("strong"))


class TestLearnerFixes(unittest.TestCase):
    """get_lessons confidence floor applies to both match directions; duration
    lesson text renders without duplication."""

    def test_confidence_floor_applies_to_substring_matches(self):
        from friday_mcu.memory.learning import Lesson, MemoryLearner

        with tempfile.TemporaryDirectory() as tmp:
            learner = MemoryLearner(Path(tmp) / "lessons.json")
            learner._lessons["low"] = Lesson(
                id="low",
                goal_pattern="check email",
                lesson="weak",
                lesson_type="failure",
                confidence=0.05,
            )
            learner._lessons["high"] = Lesson(
                id="high",
                goal_pattern="check email",
                lesson="strong",
                lesson_type="success",
                confidence=0.9,
            )
            found = learner.get_lessons("check email", min_confidence=0.3)
            ids = {l.id for l in found}
            self.assertIn("high", ids)
            self.assertNotIn("low", ids)

    def test_duration_lesson_no_duplicate_prefix(self):
        from friday_mcu.memory.learning import MemoryLearner

        with tempfile.TemporaryDirectory() as tmp:
            learner = MemoryLearner(Path(tmp) / "lessons.json")
            learner.record_outcome("check email", success=True, duration_s=5.0)
            learner.record_outcome("check email", success=True, duration_s=3.0)
            context = learner.build_learning_context("check email")
            self.assertEqual(context.count("Expected duration:"), 1)
            self.assertIn("Expected duration: 4.0s", context)


class TestTelegramCommitModel(unittest.TestCase):
    """commit=False must not advance the offset; poll_media returns media."""

    def _fake_response(self, updates):
        resp = mock.MagicMock()
        resp.json.return_value = {"result": updates}
        resp.raise_for_status.return_value = None
        return resp

    def test_poll_updates_commit_semantics(self):
        from friday_mcu.adapters import telegram

        updates = [
            {"update_id": 11, "message": {"message_id": 1, "chat": {"id": 9}, "text": "/goal hi", "from": {"username": "u"}}},
            {"update_id": 12, "message": {"message_id": 2, "chat": {"id": 9}, "text": "ignored", "from": {"username": "u"}}},
        ]
        with mock.patch.object(telegram, "_load_offset", return_value=10), \
             mock.patch.object(telegram.requests, "get", return_value=self._fake_response(updates)), \
             mock.patch.object(telegram, "_save_offset") as save:
            msgs = telegram.poll_updates(limit=10, commit=False)
            save.assert_not_called()
            self.assertEqual([m["message_id"] for m in msgs], ["1", "2"])

            telegram.poll_updates(limit=10, commit=True)
            save.assert_called_once_with(13)  # max update_id + 1

    def test_poll_media_only_returns_media(self):
        from friday_mcu.adapters import telegram

        updates = [
            {"update_id": 21, "message": {"message_id": 1, "chat": {"id": 9}, "text": "hi", "from": {"username": "u"}}},
            {"update_id": 22, "message": {"message_id": 2, "chat": {"id": 9}, "document": {"file_id": "FILE1", "file_name": "a.pdf"}, "from": {"username": "u"}}},
        ]
        with mock.patch.object(telegram, "_load_offset", return_value=20), \
             mock.patch.object(telegram.requests, "get", return_value=self._fake_response(updates)), \
             mock.patch.object(telegram, "_save_offset"):
            media = telegram.poll_media(limit=10, commit=False)
        self.assertEqual(len(media), 1)
        self.assertEqual(media[0]["file_id"], "FILE1")
        self.assertEqual(media[0]["update_id"], 22)

    def test_mark_read_only_advances(self):
        from friday_mcu.adapters import telegram

        with mock.patch.object(telegram, "_load_offset", return_value=10), \
             mock.patch.object(telegram, "_save_offset") as save:
            telegram.mark_read([15])
            save.assert_called_once_with(16)
            save.reset_mock()
            telegram.mark_read([5])  # below current offset — no-op
            save.assert_not_called()


class TestDiscordWatermark(unittest.TestCase):
    """poll_messages returns only messages newer than the watermark and never
    re-yields handled ones."""

    def _fake_response(self, messages):
        resp = mock.MagicMock()
        resp.json.return_value = messages
        resp.raise_for_status.return_value = None
        return resp

    def test_poll_filters_by_watermark(self):
        from friday_mcu.adapters import discord

        raw = [
            {"id": "30", "content": "old /goal x", "author": {"username": "u"}},
            {"id": "40", "content": "new /goal y", "author": {"username": "u"}},
        ]
        with mock.patch.dict("os.environ", {"DISCORD_BOT_TOKEN": "t", "DISCORD_CHANNEL_ID": "C1"}):
            with mock.patch.object(discord, "_load_watermarks", return_value={"C1": 25}), \
                 mock.patch.object(discord.requests, "get", return_value=self._fake_response(raw)), \
                 mock.patch.object(discord, "_save_watermarks") as save:
                msgs = discord.poll_messages(limit=10)
                save.assert_not_called()  # presence/read must not consume
                self.assertEqual([m["id"] for m in msgs], ["30", "40"])

                discord.mark_channel_read("C1", "40")
                save.assert_called_once_with({"C1": 40})

            with mock.patch.object(discord, "_load_watermarks", return_value={"C1": 40}), \
                 mock.patch.object(discord.requests, "get", return_value=self._fake_response(raw)):
                msgs = discord.poll_messages(limit=10)
                self.assertEqual(msgs, [])


class TestWatcherSemantics(unittest.TestCase):
    """File-trigger seen state persists across restarts; inline plans bypass
    the LLM."""

    def _config(self, triggers):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"triggers": triggers}, f)
            f.flush()
            return f.name

    def test_file_seen_state_survives_restart(self):
        from friday_mcu.watcher import run_watcher

        with tempfile.TemporaryDirectory() as tmp:
            watch_dir = Path(tmp) / "downloads"
            watch_dir.mkdir()
            (watch_dir / "report.pdf").write_text("x", encoding="utf-8")
            config = self._config([
                {
                    "id": "file-trig",
                    "goal": "handle file",
                    "plan": {"goal": "handle file", "steps": [
                        {"primitive": "fake.echo", "args": {"p": "$none"}, "verify": {"check": "checks.call_succeeded", "args": {"value": "$steps.1.result"}, "expect": True}},
                    ]},
                    "schedule": {"type": "file", "directory": str(watch_dir), "name": ".pdf"},
                    "enabled": True,
                    "notify": False,
                }
            ])
            fired_path = Path(tmp) / "fired.json"
            tasks_path = Path(tmp) / "tasks.jsonl"
            seen_path = Path(tmp) / "seen.json"

            def _ok_plan(*_a, **_k):
                return {"status": "COMPLETED", "duration_s": 0.0, "_result": "", "steps": []}

            hermetic = [
                mock.patch("friday_mcu.watcher._fired_state_file", return_value=fired_path),
                mock.patch("friday_mcu.watcher._tasks_file", return_value=tasks_path),
                mock.patch("friday_mcu.watcher._file_seen_file", return_value=seen_path),
                mock.patch("friday_mcu.watcher._notify_outcome"),
                # Keep the daemon run free of real proactive/network effects and
                # of real-memory consolidation writes.
                mock.patch("friday_mcu.watcher._run_proactive_tick"),
                mock.patch("friday_mcu.memory.store.MemoryManager.consolidate", return_value={}),
                mock.patch("friday_mcu.memory.learning.MemoryLearner.consolidate", return_value={}),
                mock.patch.dict("os.environ", {
                    "TELEGRAM_BOT_TOKEN": "", "DISCORD_BOT_TOKEN": "", "WHATSAPP_ACCESS_TOKEN": "", "WHATSAPP_PHONE_NUMBER_ID": "",
                }),
            ]
            for p in hermetic:
                p.start()
            try:
                # First daemon run fires the trigger...
                with mock.patch("friday_mcu.watcher._execute_plan", side_effect=_ok_plan) as exec1:
                    run_watcher(config, once=True, poll_s=0.1)
                    self.assertEqual(exec1.call_count, 1)

                # ...and a restart must NOT re-fire it (persisted seen state).
                with mock.patch("friday_mcu.watcher._execute_plan", side_effect=_ok_plan) as exec2:
                    run_watcher(config, once=True, poll_s=0.1)
                    exec2.assert_not_called()
            finally:
                for p in hermetic:
                    p.stop()

    def test_inline_plan_runs_without_llm(self):
        from friday_mcu.watcher import run_watcher

        with tempfile.TemporaryDirectory() as tmp:
            config = self._config([
                {
                    "id": "inline",
                    "goal": "test",
                    "plan": {"goal": "test", "steps": [
                        {"primitive": "fake.echo", "args": {"x": 1}, "verify": {"check": "checks.call_succeeded", "args": {"value": "$steps.1.result"}, "expect": True}},
                    ]},
                    "schedule": {"type": "time", "at": "00:00"},
                    "enabled": True,
                    "notify": False,
                }
            ])
            fired_path = Path(tmp) / "fired.json"
            tasks_path = Path(tmp) / "tasks.jsonl"
            seen_path = Path(tmp) / "seen.json"

            with mock.patch("friday_mcu.watcher._fired_state_file", return_value=fired_path), \
                 mock.patch("friday_mcu.watcher._tasks_file", return_value=tasks_path), \
                 mock.patch("friday_mcu.watcher._file_seen_file", return_value=seen_path), \
                 mock.patch("friday_mcu.watcher._run_proactive_tick"), \
                 mock.patch("friday_mcu.memory.store.MemoryManager.consolidate", return_value={}), \
                 mock.patch("friday_mcu.memory.learning.MemoryLearner.consolidate", return_value={}), \
                 mock.patch("friday_mcu.watcher._execute_goal") as goal_exec, \
                 mock.patch("friday_mcu.watcher._execute_plan", return_value={"status": "COMPLETED", "duration_s": 0.1, "_result": "", "steps": []}) as plan_exec, \
                 mock.patch("friday_mcu.watcher._notify_outcome"):
                run_watcher(config, once=True, poll_s=0.1)
                plan_exec.assert_called_once()
                goal_exec.assert_not_called()  # the LLM path was never touched


class TestEventBusThreadSafety(unittest.TestCase):
    def test_unsubscribe_stops_delivery(self):
        from friday_mcu.core.events import Event, EventBus, EventType

        bus = EventBus()
        seen = []
        cb = lambda e: seen.append(e)  # noqa: E731
        bus.subscribe(EventType.GOAL_COMPLETE, cb)
        bus.emit(Event(type=EventType.GOAL_COMPLETE))
        bus.unsubscribe(EventType.GOAL_COMPLETE, cb)
        bus.emit(Event(type=EventType.GOAL_COMPLETE))
        self.assertEqual(len(seen), 1)

    def test_raising_subscriber_does_not_break_bus(self):
        from friday_mcu.core.events import Event, EventBus, EventType

        bus = EventBus()
        seen = []
        bus.subscribe(EventType.GOAL_COMPLETE, lambda e: 1 / 0)
        bus.subscribe(EventType.GOAL_COMPLETE, lambda e: seen.append(e))
        bus.emit(Event(type=EventType.GOAL_COMPLETE))  # must not raise
        self.assertEqual(len(seen), 1)

    def test_concurrent_emit(self):
        from friday_mcu.core.events import Event, EventBus, EventType

        bus = EventBus()
        counter = []
        lock = threading.Lock()

        def add(e):
            with lock:
                counter.append(e)

        bus.subscribe(EventType.SYSTEM_HEALTH, add)
        threads = [
            threading.Thread(target=lambda: [bus.emit(Event(type=EventType.SYSTEM_HEALTH)) for _ in range(100)])
            for _ in range(4)
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        self.assertEqual(len(counter), 400)


class TestCredentialLoader(unittest.TestCase):
    """config/credentials.json is mapped onto the env vars adapters read."""

    def test_loads_sections_into_env(self):
        import friday_mcu.env as env

        with tempfile.TemporaryDirectory() as tmp:
            cred = Path(tmp) / "credentials.json"
            cred.write_text(json.dumps({
                "telegram": {"bot_token": "tok-a", "chat_id": "123"},
                "discord": {"bot_token": "tok-b", "channel_id": "456"},
                "whatsapp": {"access_token": "tok-c", "phone_number_id": "789", "default_phone": "+1"},
                "gmail": {"client_id": "cid", "client_secret": "sec", "refresh_token": "ref"},
            }), encoding="utf-8")
            with mock.patch.object(env, "credentials_file", return_value=cred), \
                 mock.patch.dict("os.environ", {}, clear=True):
                loaded = env.load_credentials()
                self.assertIn("TELEGRAM_BOT_TOKEN", loaded)
                self.assertEqual(os.environ.get("TELEGRAM_DEFAULT_CHAT"), "123")
                self.assertEqual(os.environ.get("DISCORD_BOT_TOKEN"), "tok-b")
                self.assertEqual(os.environ.get("WHATSAPP_PHONE_NUMBER_ID"), "789")
                self.assertEqual(os.environ.get("GMAIL_REFRESH_TOKEN"), "ref")

    def test_existing_env_wins(self):
        import friday_mcu.env as env

        with tempfile.TemporaryDirectory() as tmp:
            cred = Path(tmp) / "credentials.json"
            cred.write_text(json.dumps({"telegram": {"bot_token": "from-file"}}), encoding="utf-8")
            with mock.patch.object(env, "credentials_file", return_value=cred), \
                 mock.patch.dict("os.environ", {"TELEGRAM_BOT_TOKEN": "from-env"}, clear=True):
                loaded = env.load_credentials()
                self.assertEqual(os.environ["TELEGRAM_BOT_TOKEN"], "from-env")
                self.assertNotIn("TELEGRAM_BOT_TOKEN", loaded)

    def test_missing_file_is_noop(self):
        import friday_mcu.env as env

        with mock.patch.object(env, "credentials_file", return_value=Path("/nonexistent/creds.json")):
            self.assertEqual(env.load_credentials(), set())


class TestBuiltinChannels(unittest.TestCase):
    """Channels register only for platforms with credentials and can send."""

    @staticmethod
    def _only_telegram_env():
        return mock.patch.dict("os.environ", {
            "TELEGRAM_BOT_TOKEN": "tok",
            "DISCORD_BOT_TOKEN": "",
            "WHATSAPP_ACCESS_TOKEN": "",
            "WHATSAPP_PHONE_NUMBER_ID": "",
        })

    def test_registers_only_credentialed_platforms(self):
        from friday_mcu.comms import channels as chans
        from friday_mcu.comms.builtin_channels import register_builtin_channels

        # A FRESH registry so no real (credential-backed) channel from this
        # machine can leak into the test or out of it.
        with mock.patch.object(chans, "_CHANNELS", new={}), self._only_telegram_env():
            register_builtin_channels()
            self.assertEqual(set(chans.list_channels().keys()), {"telegram"})

    def test_channel_send_delivers_via_adapter(self):
        from friday_mcu.comms.builtin_channels import TelegramChannel
        from friday_mcu.comms.channels import Message

        with self._only_telegram_env():
            channel = TelegramChannel()
            with mock.patch("friday_mcu.adapters.telegram.send_text", return_value={"message_id": "m1"}) as send:
                mid = channel.send(Message(channel="telegram", recipient="", content="hello"))
            self.assertEqual(mid, "m1")
            send.assert_called_once_with("hello", to="")


class TestProactiveChannelDelivery(unittest.TestCase):
    """ProactiveEngine suggestions actually reach a channel now."""

    def test_flush_sends_and_records_learning(self):
        from friday_mcu.comms import channels as chans
        from friday_mcu.comms.adaptive import get_shared
        from friday_mcu.comms.builtin_channels import register_builtin_channels
        from friday_mcu.comms.proactive import ProactiveEngine, ProactiveMessage

        baseline = get_shared().get_stats()["total_sends"]
        # Fresh registry + fake env: the only channel that can exist is a
        # Telegram one whose send is mocked below — never the real network.
        with mock.patch.object(chans, "_CHANNELS", new={}), TestBuiltinChannels._only_telegram_env():
            register_builtin_channels()
            engine = ProactiveEngine()
            engine._quiet_hours = (0, 0)
            with mock.patch("friday_mcu.adapters.telegram.send_text", return_value={"message_id": "pro-1"}):
                ok = engine.suggest(ProactiveMessage(content="Your inbox summary", confidence=0.9, reason="digest"))
                self.assertTrue(ok)
                sent = engine.flush()
            self.assertEqual(sent, ["pro-1"])
        self.assertGreater(get_shared().get_stats()["total_sends"], baseline)


class TestWatcherMcuConfig(unittest.TestCase):
    """The MCU watcher has its own config; sample triggers are inert + valid."""

    def test_default_config_is_mcu_specific(self):
        from friday_mcu.watcher import DEFAULT_CONFIG
        self.assertEqual(DEFAULT_CONFIG.name, "watcher_mcu.json")

    def test_sample_triggers_load_and_are_inert(self):
        from friday_mcu.watcher import DEFAULT_CONFIG, load_config

        triggers = load_config(DEFAULT_CONFIG)
        self.assertTrue(len(triggers) >= 1)
        for t in triggers:
            self.assertFalse(t.get("enabled", True), t["id"])

    def test_inline_calendar_plan_validates(self):
        from friday_mcu.brain.planner import validate_plan
        from friday_mcu.watcher import DEFAULT_CONFIG, load_config

        for t in load_config(DEFAULT_CONFIG):
            if t.get("plan"):
                ok, errors = validate_plan(t["plan"])
                self.assertTrue(ok, f"{t['id']}: {errors}")


class TestExecutorLogging(unittest.TestCase):
    """Correlated runs emit one L0 line per attempt; bare runs stay quiet."""

    def _plan(self, path: str) -> dict:
        return {
            "goal": "write",
            "steps": [{
                "primitive": "fake.touch",
                "args": {"path": path},
                "verify_wait_s": 0.1,
                "verify": {"check": "checks.file_exists", "args": {"path": path}, "expect": True},
            }],
        }

    def test_logs_when_run_id_given(self):
        from friday_mcu.brain.executor import run_plan

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "f.txt")
            with mock.patch("friday_mcu.core.observability.emit_log") as mlog:
                run_plan(self._plan(path), run_id="run-1")
            self.assertTrue(mlog.called)
            extra = mlog.call_args.kwargs["extra"]
            self.assertEqual(extra["run_id"], "run-1")
            self.assertEqual(extra["outcome"], "verified")

    def test_no_log_without_run_id(self):
        from friday_mcu.brain.executor import run_plan

        with tempfile.TemporaryDirectory() as tmp:
            path = str(Path(tmp) / "f.txt")
            with mock.patch("friday_mcu.core.observability.emit_log") as mlog:
                run_plan(self._plan(path))
            mlog.assert_not_called()


if __name__ == "__main__":
    unittest.main()
