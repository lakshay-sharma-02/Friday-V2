"""L2 - Verification checks.

Every function here is side-effect-free: it reads current real-world state
through a primitive's READ-ONLY accessor and returns True/False (or a
scalar) against a specific claim. Import discipline: only `idempotent`
(read-only) primitive functions are imported - never mutators. This is
enforced mechanically by gates/gate3_proof.py, which fails the gate if any
imported primitive's contract is not `idempotent`.

Each check emits one L0 log line with layer="L2" through the observe()
decorator, so verification activity is traceable like everything else.
"""

from __future__ import annotations

from pathlib import Path

from friday.errors import PrimitiveError
from friday.l1 import media, window  # (read-only accessors only)
from friday.l1.browser import find_locator, read_page_text
from friday.l1.gmail import get_message as gmail_message, list_unread as gmail_unread
from friday.l1.whatsapp import get_me as whatsapp_identity
from friday.observability import observe

# NOTE: window.list_clients, media.is_playing, browser.read_page_text,
# whatsapp.get_me and the gmail accessors (get_message, list_unread) are all
# contract idempotency=idempotent (read-only). No mutator (open_app,
# close_window, play_for, send_text, ...) is imported here, and the gate-3
# proof enforces that mechanically.


@observe(layer="L2")
def window_client_count() -> int:
    """Claim: 'there are N windows open right now'. Read-only."""
    return len(window.list_clients())


@observe(layer="L2")
def window_has_class(cls: str) -> bool:
    """Claim: 'at least one open window has class X'. Read-only."""
    cls = cls.lower()
    return any(cls in str(c.get("class", "")).lower() for c in window.list_clients())


@observe(layer="L2")
def window_has_title(substring: str) -> bool:
    """Claim: 'an open window's title contains X'. Read-only."""
    substring = substring.lower()
    return any(substring in str(c.get("title", "")).lower() for c in window.list_clients())


@observe(layer="L2")
def active_window_class() -> str | None:
    """Claim: 'the focused window's class is X'. Read-only."""
    active = window.get_active_window()
    return str(active.get("class", "")) if active else None


def _class_haystack(c: dict) -> str:
    """The same class/title haystack the window primitives resolve against,
    so a check and a primitive can never disagree about what a window is.
    Deliberately mirrors window._client_haystack rather than importing the
    private helper (checks may import only read-only accessors) - keep the
    four fields in sync if either side changes."""
    return " ".join(
        str(c.get(k, "")) for k in ("class", "initialClass", "title", "initialTitle")
    ).lower()


@observe(layer="L2")
def window_focused(cls: str) -> bool:
    """Claim: 'the currently focused window is a X'. Read-only: matches the
    active window's class/title haystack, same as the focus primitive."""
    active = window.get_active_window()
    return bool(active) and cls.lower() in _class_haystack(active)


@observe(layer="L2")
def window_on_workspace(cls: str, workspace_id: int) -> bool:
    """Claim: 'at least one open window with class X sits on workspace N'.
    Read-only, from list_clients."""
    return any(
        cls.lower() in _class_haystack(c)
        and int(c.get("workspace", {}).get("id", -1)) == workspace_id
        for c in window.list_clients()
    )


@observe(layer="L2")
def window_only_classes(classes: list[str]) -> bool:
    """Claim: 'every open window's class is in the allowed set'. Read-only.
    The exact SUFFICIENT condition for a window.close_all(exclude_classes=...)
    step: afterwards, no client with a class outside the excluded set may
    remain. Mirrors close_all's own loop - class-only matching (never
    initialClass/title), every client (mapped or hidden), vacuously true on
    an empty desktop - so check and primitive cannot disagree. Contrast
    window_focused, which proves only WHERE focus landed and would pass on
    a partial close."""
    allowed = {c.lower() for c in (classes or [])}
    return all(
        str(c.get("class", "")).lower() in allowed for c in window.list_clients()
    )


@observe(layer="L2")
def media_playing() -> bool:
    """Claim: 'media is currently playing'. Read-only."""
    return bool(media.is_playing())


@observe(layer="L2")
def browser_has_text(substring: str) -> bool:
    """Claim: 'the open page's visible text contains X'. Read-only. If no
    browser page is open (the legitimate no-page state), the claim is
    simply false - but a genuinely broken page/context propagates as an
    error rather than masquerading as a false verdict."""
    try:
        return substring in read_page_text()
    except PrimitiveError as exc:
        if "no browser page" in str(exc):
            return False
        raise


@observe(layer="L2")
def browser_input_has_value(what: str, value: str) -> bool:
    """Claim: 'the field resolved by `what` currently contains exactly the
    text `value`'. Read-only. Resolves through the same fallback chain as
    browser.click/type_text and reads the input's value - the only honest
    way to verify that typed text landed. If the resolved element is a
    wrapper carrying the label (common on real sites), the value of the
    first contained input/textarea/select is read instead. A missing
    field or a locator that died between resolve and read is a false
    verdict, never a crash."""
    try:
        loc = find_locator(what)
    except PrimitiveError as exc:
        if "no browser page" in str(exc):
            return False
        raise

    def _read(candidate: Locator) -> str | None:
        try:
            return candidate.input_value()
        except Exception:
            return None

    direct = _read(loc)
    if direct is not None:
        return direct == value
    try:
        inner = loc.locator("input, textarea, select").first
        return _read(inner) == value
    except Exception:
        return False


@observe(layer="L2")
def file_exists(path: str) -> bool:
    """Claim: 'a file exists at path'. Read-only filesystem check."""
    return Path(path).exists()


@observe(layer="L2")
def whatsapp_identity_ok() -> bool:
    """Claim: 'the whatsapp credentials resolve to a real account'.
    Read-only API identity check. Auth/network failures propagate as
    errors - a rejected credential is a failure, not a false verdict."""
    return bool(whatsapp_identity())


@observe(layer="L2")
@observe(layer="L2")
def gmail_unread_exists(sender: str) -> bool:
    """Claim: 'there is at least one unread message from this sender'.
    Read-only API query (gmail.list_unread is idempotent). An empty
    mailbox is a FALSE verdict, never an error; an auth failure propagates
    as an error - rejected credentials are not a verdict."""
    return bool(gmail_unread(sender, max_results=1))


@observe(layer="L2")
def gmail_message_matches(message_id: str, expected_sender_substring: str) -> bool:
    """Claim: 'the fetched message's From header contains the expected
    sender substring'. Read-only, case-insensitive. This catches the
    failure mode where list_unread silently returns the WRONG sender's
    email (e.g. a substring-match false positive) even though no exception
    fired anywhere in the chain. Auth/fetch errors propagate, never
    masquerade as a verdict."""
    msg = gmail_message(message_id)
    sender = str(msg.get("sender", ""))
    needle = expected_sender_substring.lower()
    return bool(needle and needle in sender.lower())


@observe(layer="L2")
def message_sent(platform: str, message_id: str) -> bool:
    """Claim: 'the messaging platform acknowledged a message with this id'.
    The message id is real-world state returned by the platform's API when
    it accepted a message - this check validates it is present and
    well-formed for the platform (whatsapp wamid, telegram/discord numeric
    ids). A send that returned no id fails here. Read-only pure function:
    never touches the network."""
    if not message_id:
        return False
    p = platform.lower()
    if p == "whatsapp":
        # WhatsApp wamids are "wamid.HBg..." (the dot form is standard, but
        # some API revisions return a bare "wamid..." - accept both).
        return message_id.startswith("wamid")
    if p == "telegram":
        return message_id.isdigit()
    if p == "discord":
        return message_id.isdigit() and len(message_id) >= 17
    return False
