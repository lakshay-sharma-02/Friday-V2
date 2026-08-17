"""browser primitives, exercised through a fake page object - no real
browser is ever launched. Covers the locator fallback chain (selector ->
attribute -> label -> role -> text), no-page preconditions, and the
Task-7 credential-logging regression (login's _fill_field must stay
silent while type_text logs its text)."""

from __future__ import annotations

import json
import unittest
from unittest import mock

from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeout

from friday.errors import PreconditionError, PrimitiveError
from friday.l1 import browser
from tests.helpers import EnvTestCase


class FakeLocator:
    def __init__(self, name: str, visible: bool = True):
        self.name = name
        self.visible = visible
        self.calls: list = []

    @property
    def first(self):
        return self

    def wait_for(self, **kwargs):
        if not self.visible:
            raise PlaywrightTimeout(f"{self.name} not visible")

    def fill(self, text, **kwargs):
        self.calls.append(("fill", text))

    def click(self, **kwargs):
        self.calls.append(("click",))

    def press_sequentially(self, text):
        self.calls.append(("seq", text))


class FakePage:
    """A page whose strategy methods resolve from a per-strategy map; every
    unresolved query yields an invisible locator so find_locator falls
    through the chain in order."""

    def __init__(self, resolved: dict | None = None, inner_text: str = ""):
        self.resolved = resolved or {}
        self.inner_text = inner_text
        self.url = ""

    def locator(self, what):
        return self.resolved.get("selector", {}).get(
            what, FakeLocator(f"sel:{what}", visible=False)
        )

    def get_by_label(self, what, exact=False):
        return self.resolved.get("label", {}).get(what, FakeLocator(f"label:{what}", visible=False))

    def get_by_role(self, role, name=None):
        return self.resolved.get("role", {}).get(role, FakeLocator(f"role:{role}", visible=False))

    def get_by_text(self, what, exact=False):
        return self.resolved.get("text", {}).get(what, FakeLocator(f"text:{what}", visible=False))

    def evaluate(self, expr):
        return self.inner_text


class FakeRaisingPage(FakePage):
    """A page whose locator() raises PlaywrightError for one specific query
    (a malformed selector), mimicking the real page: find_locator must fall
    through the chain instead of aborting."""

    def __init__(self, bad_selector: str, **kw):
        super().__init__(**kw)
        self.bad_selector = bad_selector

    def locator(self, what):
        if what == self.bad_selector:
            raise PlaywrightError(f"malformed selector: {what}")
        return super().locator(what)


class BrowserTestCase(EnvTestCase):
    def setUp(self):
        super().setUp()
        self._old_page = browser._page
        self._old_pw = browser._pw
        self._old_context = browser._context
        self._log = self.mktmp() / "log.jsonl"
        self.set_env(FRIDAY_LOG_FILE=str(self._log))

    def tearDown(self):
        browser._page = self._old_page
        browser._pw = self._old_pw
        browser._context = self._old_context
        super().tearDown()

    def _lines(self):
        if not self._log.exists():
            return []
        return [json.loads(l) for l in open(self._log, encoding="utf-8") if l.strip()]


class TestFindLocator(BrowserTestCase):
    def test_no_page_raises(self):
        browser._page = None
        with self.assertRaises(PrimitiveError) as ctx:
            browser.find_locator("anything")
        self.assertIn("no browser page", str(ctx.exception))

    def test_empty_query_precondition(self):
        browser._page = FakePage()
        with self.assertRaises(PreconditionError):
            browser.find_locator("   ")

    def test_falls_through_chain_to_text(self):
        found = FakeLocator("found")
        browser._page = FakePage(resolved={"text": {"continue": found}})
        loc = browser.find_locator("continue")
        self.assertIs(loc, found)

    def test_selector_wins_when_visible(self):
        sel = FakeLocator("sel")
        text = FakeLocator("text")
        browser._page = FakePage(
            resolved={"selector": {"button.continue": sel}, "text": {"button.continue": text}}
        )
        loc = browser.find_locator("button.continue")  # has a selector hint
        self.assertIs(loc, sel)

    def test_nothing_matches_raises_with_tried_list(self):
        browser._page = FakePage()
        with self.assertRaises(PrimitiveError) as ctx:
            browser.find_locator("ghost")
        self.assertIn("no element found", str(ctx.exception))
        self.assertIn("tried:", str(ctx.exception))

    def test_malformed_selector_falls_through_chain(self):
        """A locator() that raises (malformed selector) must fall through to
        the rest of the chain, not abort find_locator."""
        found = FakeLocator("found")
        browser._page = FakeRaisingPage("input[name=", resolved={"text": {"input[name=": found}})
        loc = browser.find_locator("input[name=")  # looks like a selector, but is malformed
        self.assertIs(loc, found)

    def test_malformed_selector_then_nothing_matches(self):
        browser._page = FakeRaisingPage("input[name=")
        with self.assertRaises(PrimitiveError) as ctx:
            browser.find_locator("input[name=")
        self.assertIn("tried:", str(ctx.exception))
        self.assertIn("selector:input[name=", str(ctx.exception))


class TestReadPageText(BrowserTestCase):
    def test_returns_inner_text(self):
        browser._page = FakePage(inner_text="Hello Example Domain")
        self.assertEqual(browser.read_page_text(), "Hello Example Domain")

    def test_no_page_raises(self):
        browser._page = None
        with self.assertRaises(PrimitiveError):
            browser.read_page_text()


class TestTypingAndSecretDiscipline(BrowserTestCase):
    """Regression guard for the Task-7 finding: type_text's text arg lands in
    the L0 log, but login's credential fill (via _fill_field) must not."""

    def _page_with_field(self):
        field = FakeLocator("field")
        browser._page = FakePage(resolved={"text": {"field": field}})
        return field

    def test_type_text_logs_its_text_argument(self):
        self._page_with_field()
        browser.type_text("field", "visible-typed-text")
        prims = [l for l in self._lines() if l.get("primitive") == "browser.type_text"]
        self.assertEqual(len(prims), 1)
        self.assertEqual(prims[0]["args"]["text"], "visible-typed-text")

    def test_fill_field_is_silent(self):
        """The credential fill path emits NO line carrying the secret - the
        value passed to _fill_field must never appear anywhere in the log.
        (find_locator does log a line of its own: it is a registered
        read-only primitive and its args hold no secret.)"""
        self._page_with_field()
        browser._fill_field("field", "SUPER-SECRET-VALUE", _caller="login")
        dump = "\n".join(json.dumps(l) for l in self._lines())
        self.assertNotIn("SUPER-SECRET-VALUE", dump)
        self.assertNotIn("browser._fill_field", dump)

    def test_fill_field_actually_fills(self):
        field = self._page_with_field()
        browser._fill_field("field", "value", _caller="login")
        self.assertIn(("fill", "value"), field.calls)


class TestTypeTextFallback(BrowserTestCase):
    def test_fill_failure_falls_back_to_click_and_keystrokes(self):
        """When loc.fill raises (not a fillable input), type_text clicks the
        field and presses the text sequentially - and the public primitive
        still logs its text arg (only the credential _fill_field path is
        silent)."""

        class FillFailingLocator(FakeLocator):
            def fill(self, text, **kwargs):
                raise PlaywrightError("not an input element")

        loc = FillFailingLocator("field")
        browser._page = FakePage(resolved={"text": {"field": loc}})
        browser.type_text("field", "typed-via-keys")
        self.assertIn(("click",), loc.calls)
        self.assertIn(("seq", "typed-via-keys"), loc.calls)


class TestClickNavigationSettle(BrowserTestCase):
    """The Task-7 behaviour: a click that times out MAY have landed if the
    page navigated. click() must then report success (with a note) so the
    step's L2 verify gets to arbitrate - never fail outright."""

    class _NavigatingTimeoutLocator(FakeLocator):
        def __init__(self, page, message="click timed out"):
            super().__init__("nav")
            self.page = page
            self.message = message

        def click(self, **kwargs):
            self.page.url = "https://example.com/done"
            raise PlaywrightTimeout(self.message)

    def _navigating_page(self):
        page = FakePage()
        page.url = "https://example.com/start"
        loc = self._NavigatingTimeoutLocator(page)
        page.resolved = {"text": {"go": loc}}
        return page

    def test_timed_out_click_that_navigated_is_reported_navigated(self):
        browser._page = self._navigating_page()
        with mock.patch.object(browser, "_settle_navigation"):
            out = browser.click("go")
        self.assertEqual(out["note"], "navigated")
        self.assertEqual(out["url"], "https://example.com/done")

    def test_timed_out_click_without_navigation_raises(self):
        browser._page = self._navigating_page()

        class NoNavTimeoutLocator(FakeLocator):
            def click(self, **kwargs):
                raise PlaywrightTimeout("stuck")

        browser._page.resolved = {"text": {"go": NoNavTimeoutLocator("go")}}
        with self.assertRaises(PrimitiveError) as ctx:
            browser.click("go")
        self.assertIn("no navigation followed", str(ctx.exception))

    def test_click_context_destroyed_counts_as_navigated(self):
        browser._page = self._navigating_page()

        class DestroyedLocator(FakeLocator):
            def __init__(self, page):
                super().__init__("d")
                self.page = page

            def click(self, **kwargs):
                self.page.url = "https://example.com/done"
                raise PlaywrightError("Execution context was destroyed")

        browser._page.resolved = {"text": {"go": DestroyedLocator(browser._page)}}
        with mock.patch.object(browser, "_settle_navigation"):
            out = browser.click("go")
        self.assertEqual(out["note"], "navigated")


class TestGotoAndUpload(BrowserTestCase):
    def test_goto_rejects_non_http(self):
        browser._page = FakePage()
        with self.assertRaises(PreconditionError):
            browser.goto("example.com")

    def test_upload_file_missing_path(self):
        browser._page = FakePage()
        with self.assertRaises(PreconditionError):
            browser.upload_file(None, "/no/such/file.pdf")


if __name__ == "__main__":
    unittest.main()
