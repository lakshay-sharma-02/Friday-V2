"""Goal templates — pre-built plans for common goals.

These skip the LLM entirely, reducing planning time from ~12s to ~0s.
Templates are matched by keyword scoring against the goal string.
"""

from __future__ import annotations

import copy
import re
from typing import Any


# ── Template definitions

TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "check_email",
        "keywords": ["check", "email", "mail", "inbox", "unread"],
        "min_score": 2,
        "plan": {
            "goal": "check my unread emails",
            "confidence": 0.95,
            "steps": [
                {
                    "primitive": "gmail.list_unread",
                    "args": {"max_results": 10},
                    "verify": {
                        "check": "checks.call_succeeded",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                }
            ],
        },
    },
    {
        "name": "check_email_summarize",
        "keywords": ["check", "email", "summarize", "latest", "summary"],
        "min_score": 3,
        "plan": {
            "goal": "check my email and summarize the latest one",
            "confidence": 0.9,
            "steps": [
                {
                    "primitive": "gmail.list_unread",
                    "args": {"max_results": 5},
                    "verify": {
                        "check": "checks.call_succeeded",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.get_message",
                    "args": {"message_id": "$steps.1.result[0].message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.2.result.body"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "gmail.summarize",
                    "args": {"message_id": "$steps.1.result[0].message_id"},
                    "verify": {
                        "check": "checks.text_nonempty",
                        "args": {"value": "$steps.3.result"},
                        "expect": True,
                    },
                },
            ],
        },
    },
    {
        "name": "send_discord",
        "keywords": ["send", "discord"],
        "min_score": 2,
        "plan_template": True,  # needs message extraction
    },
    {
        "name": "send_telegram",
        "keywords": ["send", "telegram"],
        "min_score": 2,
        "plan_template": True,
    },
    {
        "name": "send_whatsapp",
        "keywords": ["send", "whatsapp"],
        "min_score": 2,
        "plan_template": True,
    },
    {
        "name": "screenshot_send_discord",
        "keywords": ["screenshot", "discord"],
        "min_score": 2,
        "plan": {
            "goal": "take a screenshot and send it on discord",
            "confidence": 0.9,
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "discord.send_file",
                    "args": {"file_path": "$steps.1.result", "caption": "Screenshot from MCU Friday"},
                    "verify": {
                        "check": "checks.call_succeeded",
                        "args": {"value": "$steps.2.result"},
                        "expect": True,
                    },
                },
            ],
        },
    },
    {
        "name": "screenshot_send_whatsapp",
        "keywords": ["screenshot", "whatsapp"],
        "min_score": 2,
        "plan": {
            "goal": "take a screenshot and send it on whatsapp",
            "confidence": 0.9,
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "whatsapp.send_document",
                    "args": {"file_path": "$steps.1.result", "body": "Screenshot from MCU Friday"},
                    "verify": {
                        "check": "checks.call_succeeded",
                        "args": {"value": "$steps.2.result"},
                        "expect": True,
                    },
                },
            ],
        },
    },
    {
        "name": "screenshot_send_telegram",
        "keywords": ["screenshot", "telegram"],
        "min_score": 2,
        "plan": {
            "goal": "take a screenshot and send it on telegram",
            "confidence": 0.9,
            "steps": [
                {
                    "primitive": "screenshot.capture",
                    "args": {},
                    "verify": {
                        "check": "checks.file_exists",
                        "args": {"path": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "telegram.send_document",
                    "args": {"file_path": "$steps.1.result", "caption": "Screenshot from MCU Friday"},
                    "verify": {
                        "check": "checks.call_succeeded",
                        "args": {"value": "$steps.2.result"},
                        "expect": True,
                    },
                },
            ],
        },
    },
    {
        "name": "system_info",
        "keywords": ["system", "info", "info"],
        "min_score": 2,
        "plan": {
            "goal": "what is my system info",
            "confidence": 0.9,
            "steps": [
                {
                    "primitive": "system.cpu_info",
                    "args": {},
                    "verify": {
                        "check": "checks.call_succeeded",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                },
                {
                    "primitive": "system.memory_info",
                    "args": {},
                    "verify": {
                        "check": "checks.call_succeeded",
                        "args": {"value": "$steps.2.result"},
                        "expect": True,
                    },
                },
            ],
        },
    },
    {
        "name": "list_files",
        "keywords": ["list", "files", "directory", "folder", "what's in"],
        "min_score": 2,
        "plan": {
            "goal": "list files in the current directory",
            "confidence": 0.95,
            "steps": [
                {
                    "primitive": "files.list_dir",
                    "args": {"path": "."},
                    "verify": {
                        "check": "checks.call_succeeded",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                }
            ],
        },
    },
    {
        "name": "git_log",
        "keywords": ["git", "commits", "recent", "history"],
        "min_score": 2,
        "plan": {
            "goal": "show recent git commits",
            "confidence": 0.95,
            "steps": [
                {
                    "primitive": "git.log",
                    "args": {"count": 10},
                    "verify": {
                        "check": "checks.list_nonempty",
                        "args": {"value": "$steps.1.result"},
                        "expect": True,
                    },
                }
            ],
        },
    },
]


def _score_goal(goal: str, keywords: list[str]) -> int:
    """Count how many keywords appear in the goal."""
    goal_lower = goal.lower()
    return sum(1 for kw in keywords if kw in goal_lower)


def _extract_send_message(goal: str) -> str | None:
    """Extract the message text from a 'send X on platform' goal.

    Returns None when the message cannot be reliably extracted — the caller
    then falls through to the LLM instead of sending a fabricated default.
    """
    # Try quoted strings first
    m = re.search(r'["\']([^"\']+)["\']', goal)
    if m:
        return m.group(1)
    # Try "send X on Y" pattern
    m = re.search(r"send\s+(.+?)\s+on\s+\w+", goal, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None


def match_template(goal: str) -> dict[str, Any] | None:
    """Match a goal against known templates.

    Returns the plan dict if a template matches, None otherwise.
    """
    goal_lower = goal.lower().strip()
    best_match = None
    best_score = 0

    for tmpl in TEMPLATES:
        score = _score_goal(goal_lower, tmpl["keywords"])
        if score >= tmpl["min_score"] and score > best_score:
            best_match = tmpl
            best_score = score

    if best_match is None:
        return None

    # Handle dynamic templates (send messages with extracted text)
    if best_match.get("plan_template"):
        platform = None
        if "discord" in goal_lower:
            platform = "discord"
        elif "telegram" in goal_lower:
            platform = "telegram"
        elif "whatsapp" in goal_lower:
            platform = "whatsapp"

        if platform:
            message = _extract_send_message(goal)
            if not message:
                return None  # can't extract reliably — let the LLM plan it
            return {
                "goal": goal,
                "confidence": 0.95,
                "steps": [
                    {
                        "primitive": f"{platform}.send_text",
                        "args": {"text": message},
                        "verify": {
                            "check": "checks.call_succeeded",
                            "args": {"value": "$steps.1.result"},
                            "expect": True,
                        },
                    }
                ],
            }
        return None

    # Static template — deep-copy the plan and set the actual goal so one
    # match can never mutate the shared TEMPLATES structure for the next.
    plan = copy.deepcopy(best_match["plan"])
    plan["goal"] = goal
    return plan
