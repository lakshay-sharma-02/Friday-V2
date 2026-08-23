"""Goal Templates — pre-written plans for common patterns.

Instead of paying for an LLM call every time, common goals can use
a template plan that skips L4 and goes straight to L3. This is:
  - Faster (no LLM latency)
  - Cheaper (no API cost)
  - Deterministic (same input = same output)

Templates are matched by normalized goal text. Each template has:
  - pattern: regex or keyword match for the goal
  - plan: a complete plan dict ready for L3
  - variables: parts of the goal that get substituted into the plan

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
        name="list_windows",
        pattern=r"(show|list|what).*(windows?|apps?|applications?)",
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
    GoalTemplate(
        name="screenshot_full",
        pattern=r"(take|capture|get).*(screenshot|screen ?shot)",
        plan={
            "goal": "take a full screenshot",
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
        description="Capture a full screenshot of the desktop",
    ),
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
]


def match_template(goal: str) -> dict[str, Any] | None:
    """Try to match a goal against known templates.

    Returns the plan dict if matched, None if no template fits.
    The planner should call this BEFORE making an LLM call.
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
