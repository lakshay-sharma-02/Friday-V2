"""Goal Templates — pre-written plans for common patterns.

Instead of paying for an LLM call every time, common goals can use
a template plan that skips L4 and goes straight to L3. This is:
  - Faster (no LLM latency — 0ms vs 10-60s)
  - Cheaper (no API cost)
  - Deterministic (same input = same output)

Templates are matched by normalized goal text. Each template has:
  - pattern: regex match for the goal
  - plan: a complete plan dict ready for L3

Simple goals (single action) AND compound goals (multiple actions)
can both be templated. The LLM planner is only used for truly novel goals.

Usage:
    from friday.templates import match_template
    plan = match_template("pause whatever is playing")
    if plan:
        result = run_plan(plan)  # skip L4 entirely
    else:
        plan = plan_from_llm(goal)  # fall back to L4
"""

from __future__ import annotations

import re
from typing import Any


class GoalTemplate:
    """A pre-written plan for a common goal pattern."""

    def __init__(
        self,
        name: str,
        pattern: str,
        plan: dict[str, Any],
        description: str = "",
    ):
        self.name = name
        self.pattern = re.compile(pattern, re.IGNORECASE)
        self.plan = plan
        self.description = description

    def matches(self, goal: str) -> bool:
        """Check if a goal matches this template."""
        return bool(self.pattern.search(goal))


# --------------------------------------------------------- built-in templates

_TEMPLATES: list[GoalTemplate] = [
    # ── Simple: Media ──
    GoalTemplate(
        name="pause_media",
        pattern=r"pause.*(playing|audio|music|media)",
        plan={
            "goal": "pause whatever is playing",
            "steps": [
                {
                    "primitive": "media.is_playing",
                    "args": {},
                    "verify": {
                        "check": "checks.media_playing",
                        "args": {},
                        "expect": True,
                    },
                },
                {
                    "primitive": "media.pause",
                    "args": {},
                    "verify": {
                        "check": "checks.media_playing",
                        "args": {},
                        "expect": False,
                    },
                },
            ],
        },
        description="Pause any currently playing media",
    ),
    GoalTemplate(
        name="stop_media",
        pattern=r"stop.*(playing|audio|music|media)",
        plan={
            "goal": "stop all media playback",
            "steps": [
                {
                    "primitive": "media.stop",
                    "args": {},
                    "verify": {
                        "check": "checks.media_playing",
                        "args": {},
                        "expect": False,
                    },
                },
            ],
        },
        description="Stop all media playback",
    ),
    GoalTemplate(
        name="volume_up",
        pattern=r"(turn|crank|raise|increase|up).*(volume|sound)",
        plan={
            "goal": "turn volume up",
            "steps": [
                {
                    "primitive": "media.get_volume",
                    "args": {},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Get current volume (read-only)",
    ),
    GoalTemplate(
        name="volume_down",
        pattern=r"(turn|lower|decrease|down).*(volume|sound)",
        plan={
            "goal": "turn volume down",
            "steps": [
                {
                    "primitive": "media.get_volume",
                    "args": {},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Get current volume (read-only)",
    ),
    # ── Simple: Windows ──
    GoalTemplate(
        name="list_windows",
        pattern=r"\b(show|list|what)\b.*(\bwindows?\b|\bapps?\b|\bapplications?\b)",
        plan={
            "goal": "list all open windows",
            "steps": [
                {
                    "primitive": "window.list_clients",
                    "args": {},
                    "verify": {
                        "check": "checks.list_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="List all open windows and applications",
    ),
    GoalTemplate(
        name="open_firefox",
        pattern=r"open.*(firefox|browser)",
        plan={
            "goal": "open firefox",
            "steps": [
                {
                    "primitive": "window.open_app",
                    "args": {"command": "firefox"},
                    "verify": {
                        "check": "checks.window_has_class",
                        "args": {"cls": "firefox"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Open Firefox browser",
    ),
    GoalTemplate(
        name="open_terminal",
        pattern=r"open.*(terminal|kitty|console)",
        plan={
            "goal": "open terminal",
            "steps": [
                {
                    "primitive": "window.open_app",
                    "args": {"command": "kitty"},
                    "verify": {
                        "check": "checks.window_has_class",
                        "args": {"cls": "kitty"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Open a terminal window",
    ),
    GoalTemplate(
        name="close_all_except_terminal",
        pattern=r"close.*(every|all|everything).*(window|app|except|terminal|kitty)",
        plan={
            "goal": "close every window except terminal",
            "steps": [
                {
                    "primitive": "window.close_all",
                    "args": {"exclude_classes": ["kitty"]},
                    "verify": {
                        "check": "checks.window_only_classes",
                        "args": {"classes": ["kitty"]},
                        "expect": True,
                    },
                },
            ],
        },
        description="Close all windows except kitty terminals",
    ),
    # ── Simple: Email ──
    GoalTemplate(
        name="check_gmail",
        pattern=r"(check|show|any).*(unread|emails?|gmail|inbox)",
        plan={
            "goal": "check for unread emails",
            "steps": [
                {
                    "primitive": "gmail.list_unread",
                    "args": {"max_results": 5},
                    "verify": {
                        "check": "checks.gmail_unread_exists",
                        "args": {"sender": ""},
                        "expect": True,
                    },
                },
            ],
        },
        description="Check for unread emails in Gmail",
    ),
    # ── Simple: Clipboard ──
    GoalTemplate(
        name="clipboard_content",
        pattern=r"(show|read|what).*(clipboard|copied|paste)",
        plan={
            "goal": "read the clipboard content",
            "steps": [
                {
                    "primitive": "clipboard.read_text",
                    "args": {},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Read and display the current clipboard content",
    ),
    # ── Simple: Screenshot ──
    GoalTemplate(
        name="screenshot_only",
        pattern=r"^(take|capture|get|snap)\s+(a\s+)?screenshot\s*$",
        plan={
            "goal": "take a screenshot",
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {"target": "full"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Capture a full screenshot (no describe)",
    ),
    # ── Simple: System ──
    GoalTemplate(
        name="system_info",
        pattern=r"(show|what|how).*(system|cpu|ram|memory|disk|battery|uptime)",
        plan={
            "goal": "show system information",
            "steps": [
                {
                    "primitive": "system.cpu_info",
                    "args": {},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.1.result.get('model', '')"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "system.memory_info",
                    "args": {},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.get('total_human', '')"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Show CPU, RAM, and disk information",
    ),
    # ══════════════════════════════════════════════════════════════
    # COMPOUND TEMPLATES — multiple actions in one goal
    # ══════════════════════════════════════════════════════════════
    # ── Screenshot + Describe ──
    GoalTemplate(
        name="screenshot_describe",
        pattern=r"(screenshot|screen ?shot).*(describe|tell|what|explain|look|see|show me)",
        plan={
            "goal": "screenshot and describe",
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {"target": "full"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "vision.describe",
                    "args": {"image_path": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Capture screenshot then describe what you see",
    ),
    # ── Screenshot + Send WhatsApp ──
    GoalTemplate(
        name="screenshot_send_whatsapp",
        pattern=r"(screenshot|screen ?shot).*(send|share|whatsapp|wa)(?!t)",
        plan={
            "goal": "screenshot and send on whatsapp",
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {"target": "full"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "whatsapp.send_document",
                    "args": {"file_path": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Capture screenshot then send via WhatsApp",
    ),
    # ── Screenshot + Send Telegram ──
    GoalTemplate(
        name="screenshot_send_telegram",
        pattern=r"(screenshot|screen ?shot).*(send|share|telegram)",
        plan={
            "goal": "screenshot and send on telegram",
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {"target": "full"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "telegram.send_document",
                    "args": {"file_path": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Capture screenshot then send via Telegram",
    ),
    # ── Screenshot + Send Discord ──
    GoalTemplate(
        name="screenshot_send_discord",
        pattern=r"(screenshot|screen ?shot).*(send|share|discord)",
        plan={
            "goal": "screenshot and send on discord",
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {"target": "full"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "discord.send_file",
                    "args": {"file_path": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Capture screenshot then send via Discord",
    ),
    # ── Check email + summarize ──
    GoalTemplate(
        name="check_summarize_email",
        pattern=r"(check|read|summarize|latest).*(email|mail).*(summarize|summary|latest|recent)",
        plan={
            "goal": "check and summarize latest email",
            "steps": [
                {
                    "primitive": "gmail.list_unread",
                    "args": {"max_results": 1},
                    "verify": {
                        "check": "checks.gmail_unread_exists",
                        "args": {"sender": ""},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.get_message",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.body"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.summarize",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.3.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="List unread emails, get latest, summarize it",
    ),
    # ── Calendar + clipboard ──
    GoalTemplate(
        name="calendar_clipboard",
        pattern=r"(calendar|events?|schedule).*(clipboard|copy|paste)",
        plan={
            "goal": "copy calendar to clipboard",
            "steps": [
                {
                    "primitive": "calendar.list_upcoming",
                    "args": {"days": 1},
                    "verify": {
                        "check": "checks.list_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "clipboard.write_text",
                    "args": {"text": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Get today's calendar and copy to clipboard",
    ),
    # ── Screenshot + OCR (free, no LLM) ──
    GoalTemplate(
        name="screenshot_ocr",
        pattern=r"(screenshot|screen ?shot).*(ocr|read|text|extract)",
        plan={
            "goal": "screenshot and extract text",
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {"target": "full"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "vision.extract_text",
                    "args": {"image_path": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.text"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Capture screenshot then extract text via OCR",
    ),
    # ── Read clipboard + send on messaging ──
    GoalTemplate(
        name="clipboard_send_whatsapp",
        pattern=r"(clipboard|copied|paste).*(send|share|whatsapp|wa)",
        plan={
            "goal": "send clipboard on whatsapp",
            "steps": [
                {
                    "primitive": "clipboard.read_text",
                    "args": {},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "whatsapp.send_text",
                    "args": {"text": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Read clipboard then send text via WhatsApp",
    ),
    GoalTemplate(
        name="clipboard_send_telegram",
        pattern=r"(clipboard|copied|paste).*(send|share|telegram)",
        plan={
            "goal": "send clipboard on telegram",
            "steps": [
                {
                    "primitive": "clipboard.read_text",
                    "args": {},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "telegram.send_text",
                    "args": {"text": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Read clipboard then send text via Telegram",
    ),
    # ── Find file + send on messaging ──
    GoalTemplate(
        name="find_file_send_whatsapp",
        pattern=r"(find|search|locate).*(file|pdf|doc).*(send|share|whatsapp|wa)",
        plan={
            "goal": "find file and send on whatsapp",
            "steps": [
                {
                    "primitive": "files.find_newest",
                    "args": {"name": ".pdf", "directory": "~/Downloads"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "whatsapp.send_document",
                    "args": {"file_path": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Find newest file in Downloads then send via WhatsApp",
    ),
    # ── Git status ──
    GoalTemplate(
        name="git_status",
        pattern=r"(show|what|check|git).*(status|branch|clean|dirty)",
        plan={
            "goal": "show git status",
            "steps": [
                {
                    "primitive": "git.status",
                    "args": {"repo_path": "."},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.1.result.branch"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Show git repository status",
    ),
    # ── Git log ──
    GoalTemplate(
        name="git_log",
        pattern=r"(show|what|git).*(log|history|commits?)",
        plan={
            "goal": "show git log",
            "steps": [
                {
                    "primitive": "git.log",
                    "args": {"repo_path": ".", "count": 10},
                    "verify": {
                        "check": "checks.list_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Show recent git commits",
    ),
    # ── HTTP request ──
    GoalTemplate(
        name="http_get",
        pattern=r"(fetch|get|request|curl|http).*(url|api|endpoint)",
        plan={
            "goal": "make HTTP request",
            "steps": [
                {
                    "primitive": "http.request",
                    "args": {"url": "https://httpbin.org/get", "method": "GET"},
                    "verify": {
                        "check": "checks.http_status_ok",
                        "args": {"response": "$steps.1.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Make a GET request to httpbin",
    ),
    # ── Clipboard → Discord ──
    GoalTemplate(
        name="clipboard_send_discord",
        pattern=r"(clipboard|copied|paste).*(send|share|discord)",
        plan={
            "goal": "send clipboard on discord",
            "steps": [
                {
                    "primitive": "clipboard.read_text",
                    "args": {},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "discord.send_text",
                    "args": {"text": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Read clipboard then send text via Discord",
    ),
    # ── Email summary → desktop notification ──
    GoalTemplate(
        name="email_summary_notify",
        pattern=r"(summarize|summary|latest|recent).*(email|mail).*(notify|notification|ping|alert)",
        plan={
            "goal": "summarize latest email and notify",
            "steps": [
                {
                    "primitive": "gmail.list_unread",
                    "args": {"max_results": 1},
                    "verify": {
                        "check": "checks.gmail_unread_exists",
                        "args": {"sender": ""},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.get_message",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.body"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.summarize",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.3.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "notify.notify_send",
                    "args": {
                        "title": "Friday: Email Summary",
                        "body": "$steps.3.result",
                    },
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.4.result.body"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Summarize latest unread email and send a desktop notification",
    ),
    # ── Email summary → clipboard ──
    GoalTemplate(
        name="email_summary_clipboard",
        pattern=r"(summarize|summary|latest|recent).*(email|mail).*(clipboard|copy)",
        plan={
            "goal": "summarize latest email and copy to clipboard",
            "steps": [
                {
                    "primitive": "gmail.list_unread",
                    "args": {"max_results": 1},
                    "verify": {
                        "check": "checks.gmail_unread_exists",
                        "args": {"sender": ""},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.get_message",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.body"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.summarize",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.3.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "clipboard.write_text",
                    "args": {"text": "$steps.3.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.4.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Summarize latest unread email and copy the summary to clipboard",
    ),
    # ── Email summary → Telegram ──
    GoalTemplate(
        name="email_summary_telegram",
        pattern=r"(summarize|summary|latest|recent).*(email|mail).*(send|share|telegram)",
        plan={
            "goal": "summarize latest email and send to telegram",
            "steps": [
                {
                    "primitive": "gmail.list_unread",
                    "args": {"max_results": 1},
                    "verify": {
                        "check": "checks.gmail_unread_exists",
                        "args": {"sender": ""},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.get_message",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.body"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.summarize",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.3.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "telegram.send_text",
                    "args": {"text": "$steps.3.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.4.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Summarize latest unread email and send the summary via Telegram",
    ),
    # ── Email summary → WhatsApp ──
    GoalTemplate(
        name="email_summary_whatsapp",
        pattern=r"(summarize|summary|latest|recent).*(email|mail).*(send|share|whatsapp|wa)(?!t)",
        plan={
            "goal": "summarize latest email and send to whatsapp",
            "steps": [
                {
                    "primitive": "gmail.list_unread",
                    "args": {"max_results": 1},
                    "verify": {
                        "check": "checks.gmail_unread_exists",
                        "args": {"sender": ""},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.get_message",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.body"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.summarize",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.3.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "whatsapp.send_text",
                    "args": {"text": "$steps.3.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.4.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Summarize latest unread email and send the summary via WhatsApp",
    ),
    # ── Calendar → Telegram ──
    GoalTemplate(
        name="calendar_telegram",
        pattern=r"(calendar|events?|schedule).*(send|share|telegram)",
        plan={
            "goal": "send calendar to telegram",
            "steps": [
                {
                    "primitive": "calendar.list_upcoming",
                    "args": {"days": 1},
                    "verify": {
                        "check": "checks.list_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "telegram.send_text",
                    "args": {"text": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Get today's calendar events and send them via Telegram",
    ),
    # ── Calendar → WhatsApp ──
    GoalTemplate(
        name="calendar_whatsapp",
        pattern=r"(calendar|events?|schedule).*(send|share|whatsapp|wa)(?!t)",
        plan={
            "goal": "send calendar to whatsapp",
            "steps": [
                {
                    "primitive": "calendar.list_upcoming",
                    "args": {"days": 1},
                    "verify": {
                        "check": "checks.list_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "whatsapp.send_text",
                    "args": {"text": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Get today's calendar events and send them via WhatsApp",
    ),
    # ── Calendar → Discord ──
    GoalTemplate(
        name="calendar_discord",
        pattern=r"(calendar|events?|schedule).*(send|share|discord)",
        plan={
            "goal": "send calendar to discord",
            "steps": [
                {
                    "primitive": "calendar.list_upcoming",
                    "args": {"days": 1},
                    "verify": {
                        "check": "checks.list_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "discord.send_text",
                    "args": {"text": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Get today's calendar events and send them via Discord",
    ),
    # ── Calendar → notify ──
    GoalTemplate(
        name="calendar_notify",
        pattern=r"((calendar|events?|schedule).*(notify|notification|ping|alert|remind)|(notify|notification|ping|alert|remind).*(calendar|events?|schedule))",
        plan={
            "goal": "notify with calendar events",
            "steps": [
                {
                    "primitive": "calendar.list_upcoming",
                    "args": {"days": 1},
                    "verify": {
                        "check": "checks.list_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "notify.notify_send",
                    "args": {
                        "title": "Friday: Today's Calendar",
                        "body": "$steps.1.result",
                    },
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.body"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Get today's calendar and show a desktop notification",
    ),
    # ── Find file → Telegram ──
    GoalTemplate(
        name="find_file_send_telegram",
        pattern=r"(find|search|locate).*(file|pdf|doc).*(send|share|telegram)",
        plan={
            "goal": "find file and send on telegram",
            "steps": [
                {
                    "primitive": "files.find_newest",
                    "args": {"name": ".pdf", "directory": "~/Downloads"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "telegram.send_document",
                    "args": {"file_path": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Find newest PDF in Downloads then send via Telegram",
    ),
    # ── Find file → Discord ──
    GoalTemplate(
        name="find_file_send_discord",
        pattern=r"(find|search|locate).*(file|pdf|doc).*(send|share|discord)",
        plan={
            "goal": "find file and send on discord",
            "steps": [
                {
                    "primitive": "files.find_newest",
                    "args": {"name": ".pdf", "directory": "~/Downloads"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "discord.send_file",
                    "args": {"file_path": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Find newest PDF in Downloads then send via Discord",
    ),
    # ── Screenshot + send to clipboard ──
    GoalTemplate(
        name="screenshot_to_clipboard",
        pattern=r"(screenshot|screen ?shot).*(clipboard|copy)",
        plan={
            "goal": "screenshot and copy path to clipboard",
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {"target": "full"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "clipboard.write_text",
                    "args": {"text": "$steps.1.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Capture screenshot then copy its file path to clipboard",
    ),
    # ── Screenshot + notify ──
    GoalTemplate(
        name="screenshot_notify",
        pattern=r"(screenshot|screen ?shot).*(notify|notification|ping|alert)",
        plan={
            "goal": "screenshot and notify",
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {"target": "full"},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "notify.notify_send",
                    "args": {
                        "title": "Friday: Screenshot Captured",
                        "body": "$steps.1.result",
                    },
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.body"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Capture screenshot and show a desktop notification with the path",
    ),
    # ── Clipboard → notify ──
    GoalTemplate(
        name="clipboard_notify",
        pattern=r"(clipboard|copied|paste).*(notify|notification|ping|alert)",
        plan={
            "goal": "read clipboard and notify",
            "steps": [
                {
                    "primitive": "clipboard.read_text",
                    "args": {},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "notify.notify_send",
                    "args": {
                        "title": "Friday: Clipboard",
                        "body": "$steps.1.result",
                    },
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.body"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Read clipboard content and show it in a desktop notification",
    ),
    # ── Summarize email → send to all platforms ──
    GoalTemplate(
        name="email_summary_all",
        pattern=r"(summarize|summary|latest|recent).*(email|mail).*(all|every|everywhere)",
        plan={
            "goal": "summarize latest email and send to all platforms",
            "steps": [
                {
                    "primitive": "gmail.list_unread",
                    "args": {"max_results": 1},
                    "verify": {
                        "check": "checks.gmail_unread_exists",
                        "args": {"sender": ""},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.get_message",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.body"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.summarize",
                    "args": {"message_id": "$steps.1.result.0.message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.3.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "telegram.send_text",
                    "args": {"text": "$steps.3.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.4.result.message_id"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "discord.send_text",
                    "args": {"text": "$steps.3.result"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.5.result.message_id"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Summarize latest unread email and broadcast to Telegram and Discord",
    ),
    # ── Memory: store something ──
    GoalTemplate(
        name="remember_something",
        pattern=r"(remember|store|save|note).*(this|that|it|the following)",
        plan={
            "goal": "store a memory",
            "steps": [
                {
                    "primitive": "clipboard.read_text",
                    "args": {},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "memory.store",
                    "args": {
                        "key": "$steps.1.result",
                        "value": "$steps.1.result",
                        "category": "facts",
                    },
                    "verify": {
                        "check": "checks.memory_store_status",
                        "args": {"status": "$steps.2.result.status"},
                        "expect": "stored",
                    },
                },
            ],
        },
        description="Copy the current clipboard content into long-term memory",
    ),
    # ── Memory: recall something ──
    GoalTemplate(
        name="recall_something",
        pattern=r"(remember|recall|what do you know|retrieve).*(about|regarding|concerning)",
        plan={
            "goal": "recall a memory",
            "steps": [
                {
                    "primitive": "memory.retrieve",
                    "args": {"query": "user query", "limit": 5},
                    "verify": {
                        "check": "checks.memory_retrieval_ok",
                        "args": {"query": "user query"},
                        "expect": True,
                    },
                },
            ],
        },
        description="Search long-term memory for stored information",
    ),
]


def match_template(goal: str) -> dict[str, Any] | None:
    """Try to match a goal against known templates.

    Returns the plan dict if matched, None if no template fits.
    Both simple and compound goals can match templates — this skips
    the expensive LLM planner entirely (0ms vs 10-120s).
    """
    for tmpl in _TEMPLATES:
        if tmpl.matches(goal):
            # Deep copy the plan so modifications don't affect the template
            import copy
            plan = copy.deepcopy(tmpl.plan)
            # Ensure the goal is set correctly
            plan["goal"] = goal
            return plan
    return None


def list_templates() -> list[dict[str, str]]:
    """List all available templates with their patterns and descriptions."""
    return [
        {
            "name": t.name,
            "pattern": t.pattern.pattern,
            "description": t.description,
        }
        for t in _TEMPLATES
    ]


def register_template(template: GoalTemplate) -> None:
    """Register a custom template at runtime."""
    _TEMPLATES.append(template)
