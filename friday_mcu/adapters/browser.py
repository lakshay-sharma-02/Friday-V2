"""Browser adapter — Playwright-based web automation.

Ported from V8 l1/browser.py with the same contract-registered primitives.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any

from friday_mcu.adapters import Adapter, register_adapter
from friday_mcu.core.contracts import Idempotency, contract
from friday_mcu.core.errors import PreconditionError, PrimitiveError

# Playwright lazy import
_playwright = None
_browser = None
_page = None


def _get_playwright():
    global _playwright
    if _playwright is None:
        try:
            from playwright.sync_api import sync_playwright
            _playwright = sync_playwright().start()
        except ImportError as exc:
            raise PrimitiveError("playwright not installed: pip install playwright") from exc
    return _playwright


def _get_page():
    global _browser, _page
    if _page is not None and not _page.is_closed():
        return _page
    pw = _get_playwright()
    profile_dir = Path.home() / ".config" / "friday" / "browser_profile"
    profile_dir.mkdir(parents=True, exist_ok=True)
    _browser = pw.chromium.launch_persistent_context(
        str(profile_dir),
        headless=True,
        args=["--no-sandbox"],
    )
    if _browser.pages:
        _page = _browser.pages[0]
    else:
        _page = _browser.new_page()
    return _page


@contract(
    precondition="url is a valid http(s) URL.",
    postcondition="Page is navigated to the URL.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if navigation fails.",
    returns="dict: {url: str, title: str}.",
)
def goto(url: str) -> dict[str, str]:
    """Navigate to a URL."""
    if not url or not url.startswith(("http://", "https://")):
        raise PreconditionError("goto requires a full http(s) URL")
    try:
        page = _get_page()
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        return {"url": page.url, "title": page.title()}
    except Exception as exc:
        raise PrimitiveError(f"navigation to {url} failed: {exc}") from exc


@contract(
    precondition="A browser page is open.",
    postcondition="Returns the visible text content of the page.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if no page is open.",
    returns="str: the page text.",
)
def read_page_text() -> str:
    """Read the visible text content of the current page."""
    try:
        page = _get_page()
        if page is None or page.is_closed():
            raise PrimitiveError("no browser page open", state="open a page with goto first")
        text = page.inner_text("body")
        return text[:50000]  # bounded
    except PrimitiveError:
        raise
    except Exception as exc:
        raise PrimitiveError(f"failed to read page text: {exc}") from exc


@contract(
    precondition="A browser page is open.",
    postcondition="Clicks the element matching the description.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if element not found.",
    returns="dict: {clicked: str, url: str}.",
)
def click(what: str) -> dict[str, str]:
    """Click an element on the current page by visible text."""
    if not what:
        raise PreconditionError("click requires a non-empty 'what' description")
    try:
        page = _get_page()
        # Try multiple locator strategies
        locator = page.get_by_text(what, exact=False).first
        if not locator.is_visible(timeout=5000):
            locator = page.locator(f"text={what}").first
        locator.click(timeout=5000)
        return {"clicked": what, "url": page.url}
    except Exception as exc:
        raise PrimitiveError(f"could not click '{what}': {exc}") from exc


@contract(
    precondition="A browser page is open with an input field.",
    postcondition="Text is typed into the matched input.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if input not found.",
    returns="dict: {typed: str, field: str}.",
)
def type_text(what: str, text: str) -> dict[str, str]:
    """Type text into an input field on the current page."""
    if not what:
        raise PreconditionError("type_text requires a non-empty 'what' description")
    try:
        page = _get_page()
        locator = page.get_by_placeholder(what, exact=False).first
        if not locator.is_visible(timeout=3000):
            locator = page.get_by_label(what, exact=False).first
        if not locator.is_visible(timeout=3000):
            locator = page.locator(f"input[placeholder*='{what}']").first
        locator.fill(text, timeout=5000)
        return {"typed": text, "field": what}
    except Exception as exc:
        raise PrimitiveError(f"could not type into '{what}': {exc}") from exc


@contract(
    precondition="A browser page is open.",
    postcondition="A key is pressed on the page.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if key press fails.",
    returns="dict: {key: str}.",
)
def press_key(key: str) -> dict[str, str]:
    """Press a key on the current page (e.g. 'Enter', 'Tab')."""
    try:
        page = _get_page()
        page.keyboard.press(key)
        return {"key": key}
    except Exception as exc:
        raise PrimitiveError(f"could not press key '{key}': {exc}") from exc


@contract(
    precondition="A browser page is open.",
    postcondition="Browser is closed.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="None expected.",
    returns="None",
)
def close() -> None:
    """Close the browser context."""
    global _browser, _page
    try:
        if _browser:
            _browser.close()
    except Exception:
        pass
    _browser = None
    _page = None


class BrowserAdapter(Adapter):
    """Browser adapter."""

    @property
    def name(self) -> str:
        return "browser"

    @property
    def capabilities(self) -> list[str]:
        return ["goto", "read_page_text", "click", "type_text", "press_key", "close"]

    async def initialize(self) -> None:
        pass  # Playwright is initialized on-demand

    async def execute(self, action: str, **kwargs: Any) -> Any:
        actions = {
            "goto": goto,
            "read_page_text": read_page_text,
            "click": click,
            "type_text": type_text,
            "press_key": press_key,
            "close": close,
        }
        fn = actions.get(action)
        if fn is None:
            raise PrimitiveError(f"Unknown browser action: {action}")
        return fn(**kwargs)

    async def observe(self) -> list:
        return []

    def health_check(self) -> bool:
        try:
            from playwright.sync_api import sync_playwright
            return True
        except ImportError:
            return False


try:
    register_adapter(BrowserAdapter())
except Exception:
    pass
