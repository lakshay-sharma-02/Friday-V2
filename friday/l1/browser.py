"""L1 primitive: browser (Playwright, persistent context).

DOM / accessibility-tree based, NOT screenshots. This is what makes "find
the chat named X" a generic query instead of per-site code: elements are
resolved through the fallback chain
    exact selector -> attribute relaxation -> substring ->
    accessible-name -> visible text.

Secrets: credentials come from `pass` (GPG-encrypted password store) at the
path `friday/<service>`. Never hardcoded, never logged in plaintext. This
module is where the secrets mechanism is actually called - dead imports are
not allowed to look "done".
"""

from __future__ import annotations

import contextlib
import os
import re
import signal
import subprocess
import time
from pathlib import Path
from typing import Any, cast

from playwright.sync_api import (
    Error as PlaywrightError,
    Locator,
    TimeoutError as PlaywrightTimeout,
    sync_playwright,
)

from friday.contracts import Idempotency, contract
from friday.errors import PreconditionError, PrimitiveError

# Windows-port flag (2026-08-17): the orphan sweep has no pgrep on
# Windows, so it shells to PowerShell instead.
_IS_WINDOWS = os.name == "nt"

PROFILE_DIR = Path(__file__).resolve().parents[2] / "var" / "browser_profile"
DEFAULT_NAV_TIMEOUT_MS = 30_000

_pw = None
_context = None
_page = None


# ---------------------------------------------------------------- internals


def _sweep_windows(pattern: str) -> int:
    """Windows orphan sweep: there is no pgrep, and os.kill would be a hard
    TerminateProcess, so list processes by command line (Get-CimInstance)
    and Stop-Process them. Best-effort like the POSIX path - never raises."""
    escaped = pattern.replace("'", "''")
    ps = (
        "Get-CimInstance Win32_Process | "
        f"Where-Object {{ $_.CommandLine -like '*{escaped}*' }} | "
        "ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
    )
    try:
        subprocess.run(
            ["powershell", "-NoProfile", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=15,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0
    return 0


def _sweep_orphans() -> int:
    """Kill any orphaned browser instance still holding the automation
    profile before launching - a locked profile makes Playwright fail with
    a cryptic error. POSIX: pgrep -f + SIGTERM; Windows: PowerShell."""
    pattern = f"--user-data-dir={PROFILE_DIR}"
    if _IS_WINDOWS:
        return _sweep_windows(pattern)
    try:
        out = subprocess.run(
            ["pgrep", "-f", re.escape(pattern)], capture_output=True, text=True, timeout=5
        )
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return 0
    pids = [int(p) for p in out.stdout.split() if p.strip().isdigit()]
    for pid in pids:
        with contextlib.suppress(ProcessLookupError):
            os.kill(pid, signal.SIGTERM)
    if pids:
        time.sleep(1.0)
    return len(pids)


def _ensure_launched() -> None:
    global _pw, _context, _page
    if _context is not None:
        return
    _sweep_orphans()
    PROFILE_DIR.mkdir(parents=True, exist_ok=True)
    try:
        _pw = sync_playwright().start()
        binary = os.environ.get("FRIDAY_BROWSER_BINARY")  # e.g. /usr/bin/brave
        _context = _pw.chromium.launch_persistent_context(
            user_data_dir=str(PROFILE_DIR),
            headless=False,
            args=["--ozone-platform-hint=auto"],
            executable_path=binary or None,
        )
    except PlaywrightError as exc:
        raise PrimitiveError(
            f"playwright chromium failed to launch: {exc}",
            state="no browser running",
        ) from exc
    _page = _context.pages[0] if _context.pages else _context.new_page()


_SELECTOR_HINT = re.compile(r"[#.\[\]:>]")
_ATTRS = ("data-testid", "aria-label", "placeholder", "name", "title", "alt")
_ROLES = ("button", "link", "menuitem", "tab")


def _first_visible(locator: Locator, wait_ms: int) -> Locator | None:
    try:
        locator.first.wait_for(state="visible", timeout=wait_ms)
        return locator.first
    except PlaywrightTimeout:
        return None


# ------------------------------------------------------------------ public


@contract(
    precondition="url is an http(s):// URL.",
    postcondition="The persistent-context page navigates to url (domcontentloaded).",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError on navigation failure (bad URL, offline, timeout); a failed "
    "navigation leaves the page on its previous or partial URL.",
    returns="dict: {url, title}.",
)
def goto(url: str, timeout_ms: int = DEFAULT_NAV_TIMEOUT_MS) -> dict[str, str]:
    if not url.startswith(("http://", "https://")):
        raise PreconditionError("goto requires an http(s) URL")
    _ensure_launched()
    assert _page is not None  # _ensure_launched guarantees a live page
    try:
        _page.goto(url, wait_until="domcontentloaded", timeout=timeout_ms)
    except (PlaywrightTimeout, PlaywrightError) as exc:
        raise PrimitiveError(
            f"goto({url}) failed: {exc}",
            state=f"page may be partially loaded; current url: {_page.url if _page else 'none'}",
        ) from exc
    return {"url": _page.url, "title": _page.title()}


@contract(
    precondition="A page is loaded.",
    postcondition="Makes no state changes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if no page exists (call goto() first) or the context died.",
    returns="str: the page's visible text.",
)
def read_page_text() -> str:
    if _page is None:
        raise PrimitiveError("no browser page; call goto() first", state="no browser running")
    try:
        return str(_page.evaluate("() => document.body ? document.body.innerText : ''"))
    except PlaywrightError as exc:
        raise PrimitiveError(f"read_page_text failed: {exc}", state="page may be closed") from exc


@contract(
    precondition="A page is loaded and 'what' is a non-empty query string.",
    postcondition="Makes no state changes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if nothing resolves through the whole chain (exact selector -> "
    "attribute relaxation -> accessible-name -> visible text).",
    returns="Locator: the first matching element.",
)
def find_locator(what: str, wait_ms: int = 2000) -> Locator:
    if not what or not what.strip():
        raise PreconditionError("find_locator requires a non-empty query")
    if _page is None:
        raise PrimitiveError("no browser page; call goto() first", state="no browser running")
    tried: list[str] = []

    if _SELECTOR_HINT.search(what):  # 1. exact selector
        tried.append(f"selector:{what}")
        try:
            loc = _first_visible(_page.locator(what), wait_ms)
        except PlaywrightError:  # malformed selector: fall through the chain
            loc = None
        if loc:
            return loc

    for attr in _ATTRS:  # 2. attribute relaxation (case-insensitive substring)
        tried.append(f"attr[{attr}*={what} i]")
        loc = _first_visible(_page.locator(f'[{attr}*="{what}" i]'), wait_ms)
        if loc:
            return loc

    tried.append(f"label:{what}")  # 3. accessible-name via label/aria
    loc = _first_visible(_page.get_by_label(what, exact=False), wait_ms)
    if loc:
        return loc

    for role in _ROLES:
        tried.append(f"role:{role}(name~{what})")
        # the playwright stubs type role as a Literal; _ROLES is a runtime
        # allowlist of valid roles, so the cast is safe
        loc = _first_visible(
            _page.get_by_role(cast(Any, role), name=re.compile(re.escape(what), re.I)), wait_ms
        )
        if loc:
            return loc

    tried.append(f"text:{what}")  # 5. visible text (substring)
    loc = _first_visible(_page.get_by_text(what, exact=False), wait_ms)
    if loc:
        return loc

    raise PrimitiveError(
        f"no element found for {what!r}; tried: {', '.join(tried)}",
        state="read-only; nothing clicked",
    )


@contract(
    precondition="A page is loaded and 'what' resolves through the fallback chain.",
    postcondition="The resolved element is clicked; the page may navigate.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if nothing resolves or the click times out; a timed-out click "
    "may have landed, so verify effects with L2.",
    returns="dict: {clicked, url}.",
)
def click(what: str, timeout_ms: int = 10_000) -> dict[str, str]:
    loc = find_locator(what)
    assert _page is not None  # find_locator raises when no page is live
    before = _page.url
    try:
        loc.click(timeout=timeout_ms)
    except PlaywrightTimeout as exc:
        # A click that starts a navigation (submit buttons, links) can time
        # out on its post-click wait even though the click LANDED - the
        # Task 7 composite hit this on GitHub's "Sign in" button. The
        # contract says a timed-out click may have landed and L2 verifies
        # effects: resolve the ambiguity here when the page demonstrably
        # moved on (url changed / navigation consumed the context) so the
        # step's L2 verify gets to arbitrate instead of the whole step
        # failing before verification runs.
        if _page.url != before:
            _settle_navigation(timeout_ms)
            return {"clicked": what, "url": _page.url, "note": "navigated"}
        raise PrimitiveError(
            f"click({what!r}) timed out and no navigation followed",
            state="element was found but the click did not land",
        ) from exc
    except PlaywrightError as exc:
        if "Execution context was destroyed" in str(exc):
            # the navigation tore the page away mid-click - the click landed
            _settle_navigation(timeout_ms)
            return {"clicked": what, "url": _page.url, "note": "navigated"}
        raise
    return {"clicked": what, "url": _page.url if _page else ""}


def _fill_field(
    what: str, text: str, timeout_ms: int = 10_000, _caller: str = "fill"
) -> dict[str, object]:
    """Fill 'text' into the field resolved by 'what' WITHOUT emitting an L0
    line (unregistered private helper). login() uses it for the credential
    values: a secret must never ride a logged argument - the Task 7
    bring-up found type_text's 'text' arg carrying the password into the
    log, so the credential fill path is deliberately silent."""
    loc = find_locator(what)
    try:
        try:
            loc.fill(text, timeout=timeout_ms)
        except PlaywrightError:
            loc.click(timeout=timeout_ms)
            loc.press_sequentially(text)
    except PlaywrightTimeout as exc:
        raise PrimitiveError(
            f"{_caller}({what!r}) failed", state="field may be partially filled"
        ) from exc
    return {"typed_into": what, "length": len(text)}


@contract(
    precondition="A page is loaded, 'what' resolves, and text is a string.",
    postcondition="The resolved field contains text (fill preferred; keystrokes as fallback).",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if the element can neither be filled nor typed into; the "
    "field may be partially filled.",
    returns="dict: {typed_into, length}.",
)
def type_text(what: str, text: str, timeout_ms: int = 10_000) -> dict[str, object]:
    return _fill_field(what, text, timeout_ms, _caller="type_text")


@contract(
    precondition="A page is loaded.",
    postcondition="The key is pressed on the resolved element, or globally if 'what' is None.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if 'what' is given but does not resolve.",
    returns="dict: {key}.",
)
def press_key(what: str | None, key: str) -> dict[str, str]:
    if _page is None:
        raise PrimitiveError("no browser page; call goto() first", state="no browser running")
    if what:
        find_locator(what).press(key)
    else:
        _page.keyboard.press(key)
    return {"key": key}


def _settle_navigation(timeout_ms: int) -> None:
    """Wait (bounded) for a navigation started by a click to settle, so the
    returned url and any L2 check run against the new page, not mid-flight.
    Never raises - a still-loading page is left for L2 polling to handle."""
    assert _page is not None  # called only after a click on a live page
    with contextlib.suppress(PlaywrightTimeout, PlaywrightError):
        _page.wait_for_load_state("domcontentloaded", timeout=min(timeout_ms, 10_000))


@contract(
    precondition="A page is loaded and a file input exists (or 'what' resolves to one).",
    postcondition="The local file is attached to the file input; nothing is submitted yet.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError if no file input is found, the path is missing, or "
    "set_input_files fails. The attachment may be partially registered - verify via L2.",
    returns="dict: {path, input_count}.",
)
def upload_file(what: str | None, path: str, timeout_ms: int = 10_000) -> dict[str, object]:
    if not path or not os.path.exists(path):
        raise PreconditionError(f"upload_file requires an existing file path, got {path!r}")
    _ensure_launched()
    assert _page is not None  # _ensure_launched guarantees a live page
    selector = what or "input[type=file]"
    try:
        loc = _page.locator(selector).first
        # File inputs are hidden by design; wait for attachment, not visibility.
        loc.wait_for(state="attached", timeout=timeout_ms)
        loc.set_input_files(str(path))
    except (PlaywrightTimeout, PlaywrightError) as exc:
        raise PrimitiveError(
            f"upload_file({path!r}) failed: {exc}",
            state="no file was attached",
        ) from exc
    return {"path": path, "input_count": _page.locator("input[type=file]").count()}


@contract(
    precondition="pass is installed and a friday/<service> entry exists "
    '(e.g. `pass insert -m friday/gmail` storing JSON {"username", "password"}).',
    postcondition="Makes no state changes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if pass is missing, the entry is missing, or the entry is not "
    "JSON or two-line user/pass. Never logs the contents.",
    returns="dict: {username, password}.",
    # The return value IS the credential dict - the whole result is a
    # secret, so it is written to the L0 log as <redacted> (found in the
    # Task 7 bring-up: key-name redaction alone is not enough when the
    # entire result is sensitive).
    redact_result=True,
)
def credentials(service: str) -> dict[str, str]:
    from friday.secrets import get_credentials

    return get_credentials(service)


@contract(
    precondition="Credentials for the service exist in pass and the page is at its login form.",
    postcondition="Credentials are filled and the submit control is clicked.",
    idempotency=Idempotency.AT_MOST_ONCE,
    failure_mode="PrimitiveError from any sub-step; partial fill is possible, so verify the "
    "resulting state with L2.",
    returns="dict: {service, url}.",
)
def login(service: str, username_sel: str, password_sel: str, submit_sel: str) -> dict[str, str]:
    creds = credentials(service)
    # _fill_field (NOT type_text): the credential VALUES are secrets and
    # must never be written to the log as a typed 'text' argument. login's
    # own L0 line carries only service + the selector strings.
    _fill_field(username_sel, creds["username"])
    _fill_field(password_sel, creds["password"])
    click(submit_sel)
    return {"service": service, "url": _page.url if _page else ""}


@contract(
    precondition="None.",
    postcondition="Browser context closed and playwright stopped; the persistent profile is "
    "preserved for the next run.",
    idempotency=Idempotency.COMMUTATIVE_SAFE,
    failure_mode="Swallows closure errors; nothing left running.",
    returns="None",
)
def close() -> None:
    global _pw, _context, _page
    try:
        if _context is not None:
            _context.close()
    except PlaywrightError:
        pass
    if _pw is not None:
        _pw.stop()
    _pw = _context = _page = None
