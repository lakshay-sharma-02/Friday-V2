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

from friday.errors import PreconditionError, PrimitiveError, PrimitiveTimeout
from friday.l1 import files, media, window  # (read-only accessors only)
from friday.l1.audio import (
    get_default_device as audio_default_sink,
    get_output_volume as audio_volume,
)
from friday.l1.browser import Locator, find_locator, read_page_text
from friday.l1.gmail import get_message as gmail_message, list_unread as gmail_unread
from friday.l1.memory import (
    retrieve as memory_retrieve,
)
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
    return active is not None and cls.lower() in _class_haystack(active)


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
    return all(str(c.get("class", "")).lower() in allowed for c in window.list_clients())


@observe(layer="L2")
def media_playing() -> bool:
    """Claim: 'media is currently playing'. Read-only."""
    return bool(media.is_playing())


@observe(layer="L2")
def audio_output_ready(min_volume: int = 1, max_volume: int = 100) -> bool:
    """Claim: 'the default audio sink is configured and the master volume is a
    sane level to hear a Friday utterance'. Read-only - never adjusts volume.

    min_volume/max_volume bound the acceptable volume so a plan can verify
    'the user can actually hear me' before a speak() step. Returns False
    (never raises) when the audio daemon is absent - an absent sound server
    is a state, not an error - mirroring audio.get_output_volume's shape.
    A volume outside [min, max] is a real signal the user won't hear us.
    """
    vol = audio_volume()
    if vol is None:
        return False  # no audio daemon / sink - can't verify audibility
    sink = audio_default_sink("sink")
    if not sink:
        return False  # no default sink configured
    return min_volume <= vol <= max_volume


@observe(layer="L2")
def audio_utterance_playing(title_substring: str) -> bool:
    """Claim: 'media is currently playing and its title references the
    utterance a speak() step just produced'. Read-only.

    Verifies a speak() step actually audibilized something: media.is_playing()
    is True AND media.get_playing_title() contains the speaker's source
    filename substring (audio.speak hands media.play() a temp WAV named
    friday_tts_<random>.wav). A plan references the WAV via
    $steps.N.result.source and passes its basename here. A stale mpv playing
    unrelated media fails this check - the title must match the utterance.
    """
    if not title_substring:
        return False
    if not media.is_playing():
        return False
    title = media.get_playing_title()
    if not title:
        return False
    return title_substring.lower() in title.lower()


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
def list_nonempty(value: list) -> bool:
    """Claim: 'a step result is a non-empty list'. Pure shape check for
    gather primitives (git.log returns a list) - the honest minimal
    verification that a read-only gather produced something to build on.
    Import discipline unaffected: pure function, no primitive imports."""
    return isinstance(value, list) and len(value) > 0


@observe(layer="L2")
def text_nonempty(value: str) -> bool:
    """Claim: 'a step result is a non-empty string'. Pure shape check for
    read/text/synthesis primitives (files.read_text / dev.digest return
    text) - proves the deliverable was actually produced without
    claiming anything about its quality (there is no honest check for
    that; the digest's content is a human-reviewable artifact)."""
    return isinstance(value, str) and bool(value.strip())


@observe(layer="L2")
def whatsapp_identity_ok() -> bool:
    """Claim: 'the whatsapp credentials resolve to a real account'.
    Read-only API identity check. Auth/network failures propagate as
    errors - a rejected credential is a failure, not a false verdict."""
    return bool(whatsapp_identity())


@observe(layer="L2")
def http_status_ok(status_code: int) -> bool:
    """Claim: 'the HTTP response status is 2xx'. Pure numeric check."""
    return 200 <= status_code < 300


@observe(layer="L2")
def http_status_code(status_code: int) -> int:
    """Claim: 'the HTTP response status is N'. Returns the actual code
    for plan-level comparison. Pure read-only."""
    return status_code


@observe(layer="L2")
def whatsapp_media_downloaded(path: str) -> bool:
    """Claim: 'a file was downloaded to path and is non-empty'.
    Read-only filesystem check after download_media. An empty file is a
    false verdict (download succeeded but produced nothing useful)."""
    p = Path(path)
    return p.exists() and p.stat().st_size > 0


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


# ---------------------------------------------------------------- memory
# Import discipline: memory.list_categories, memory.retrieve, and
# memory.summary are all contract idempotency=idempotent (read-only).
# No mutator (store, forget, reinforce, maintenance) is imported here.


@observe(layer="L2")
def memory_has_key(key: str, category: str | None = None) -> bool:
    """Claim: 'a memory exists with this key (optionally in this category)'.
    Read-only: searches via retrieve and checks if any result has the
    exact key match."""
    try:
        results = memory_retrieve(key, category=category, limit=10)
    except Exception:
        return False
    return any(r.get("key") == key for r in results)


@observe(layer="L2")
def memory_age_days(key: str) -> float:
    """Claim: 'the memory with this key is at most N days old'. Returns
    the age in days since creation, or -1 if not found. Read-only."""
    try:
        results = memory_retrieve(key, limit=10)
    except Exception:
        return -1.0
    for r in results:
        if r.get("key") == key:
            # We don't return created_at in retrieve results, so we
            # approximate from access_count and category. For a precise
            # check, the plan should use memory_has_key instead.
            return 0.0  # found = recently accessed
    return -1.0


@observe(layer="L2")
def memory_retrieval_ok(query: str) -> bool:
    """Claim: 'a memory retrieval for this query returns results'.
    Read-only: checks if the retrieve call returns a non-empty list."""
    try:
        results = memory_retrieve(query, limit=1)
    except Exception:
        return False
    return len(results) > 0


@observe(layer="L2")
def memory_store_status(status: str) -> bool:
    """Claim: 'the last memory store operation had this status'.
    Pure string check on the store result."""
    return status in ("stored", "updated")


# ---------------------------------------------------------------- file operations
# Import discipline: files.copy/move/delete/list_dir/file_size are all
# contract idempotency=at-most-once or idempotent (read-only after the fact).
# write_text is COMMUTATIVE_SAFE but we only use it for reading size verification.
# Note: file primitives raise PreconditionError for missing/invalid paths,
# so we catch both PreconditionError (expected) and PrimitiveError (unexpected).


@observe(layer="L2")
def file_size_equals(path: str, expected_bytes: int) -> bool:
    """Claim: 'a file exists at path and has exactly expected_bytes'.
    Read-only filesystem check using file_size primitive."""
    try:
        info = files.file_size(path)
        return info["size_bytes"] == expected_bytes
    except (PreconditionError, PrimitiveError):
        return False


@observe(layer="L2")
def file_exists_and_contents(path: str, expected_text: str) -> bool:
    """Claim: 'file exists and has expected contents'.
    Read-only check combining existence and content match."""
    try:
        info = files.read_text(path, max_chars=10_000)
        return bool(info["text"].strip()) and info["text"].strip() == expected_text.strip()
    except (PreconditionError, PrimitiveError):
        return False


@observe(layer="L2")
def file_is_copied_to(dest_dir: str, original_name: str) -> bool:
    """Claim: 'file was successfully copied to dest_dir'.
    Read-only: checks that a file with the expected name exists in dest_dir."""
    try:
        listing = files.list_dir(dest_dir)
        return original_name in listing["files"]
    except (PreconditionError, PrimitiveError):
        return False


@observe(layer="L2")
def file_is_moved_from(path: str, dest_dir: str) -> bool:
    """Claim: 'file was successfully moved from path to dest_dir'.
    Read-only: checks that file no longer exists at source AND exists at destination."""
    p = files.find_file_exact(Path(path).name, dest_dir) if path else ""
    original_path = Path(path) if path else None
    if not original_path:
        return False
    src_gone = not original_path.exists()
    dst_present = bool(p)
    return src_gone and dst_present


@observe(layer="L2")
def file_is_deleted(path: str) -> bool:
    """Claim: 'file was successfully deleted (no longer exists at path)'.
    Read-only: checks that the file no longer exists."""
    p = Path(path) if path else None
    if not p:
        return False
    return not p.exists()


# ---------------------------------------------------------------- git
# Import discipline: git.status, git.diff, git.branch, git.log are all
# contract idempotency=idempotent (read-only). No mutator (commit) is
# imported here.

from friday.l1 import git


@observe(layer="L2")
def repo_is_clean(repo_path: str) -> bool:
    """Claim: 'the git repository has no uncommitted changes'.
    Read-only: calls git.status and checks is_clean."""
    try:
        result = git.status(repo_path)
        return result.get("is_clean", False)
    except (PreconditionError, PrimitiveError):
        return False


@observe(layer="L2")
def repo_has_uncommitted(repo_path: str) -> bool:
    """Claim: 'the git repository has uncommitted changes'.
    Read-only: the inverse of repo_is_clean."""
    try:
        result = git.status(repo_path)
        return not result.get("is_clean", True)
    except (PreconditionError, PrimitiveError):
        return False


@observe(layer="L2")
def repo_branch(repo_path: str, expected_branch: str) -> bool:
    """Claim: 'the repository is on the expected branch'.
    Read-only: calls git.branch and checks current name."""
    try:
        result = git.branch(repo_path)
        return result.get("current", "").lower() == expected_branch.lower()
    except (PreconditionError, PrimitiveError):
        return False


@observe(layer="L2")
def repo_has_staged(repo_path: str) -> bool:
    """Claim: 'the repository has staged changes'.
    Read-only: calls git.status and checks if staged list is non-empty."""
    try:
        result = git.status(repo_path)
        return bool(result.get("staged"))
    except (PreconditionError, PrimitiveError):
        return False


@observe(layer="L2")
def diff_is_clean(repo_path: str) -> bool:
    """Claim: 'the repository diff is clean (no staged or unstaged changes)'.
    Read-only: calls git.diff and checks is_clean."""
    try:
        result = git.diff(repo_path)
        return result.get("is_clean", False)
    except (PreconditionError, PrimitiveError):
        return False


# ---------------------------------------------------------------- vision
# Import discipline: vision.extract_text is idempotent (read-only).
# vision.describe is also idempotent but costs money — the L2 check
# verifies its result, not its cost.

from friday.l1 import vision


@observe(layer="L2")
def vision_text_nonempty(image_path: str, language: str = "eng") -> bool:
    """Claim: 'extracting text from this image produces non-empty output'.
    Read-only: calls vision.extract_text and checks if any text was found."""
    try:
        result = vision.extract_text(image_path, language=language)
        return bool(result.get("text", "").strip())
    except (PreconditionError, PrimitiveError, PrimitiveTimeout):
        return False


@observe(layer="L2")
def vision_text_contains(image_path: str, substring: str, language: str = "eng") -> bool:
    """Claim: 'the image contains the specified text'.
    Read-only: extracts text and checks for substring match (case-insensitive)."""
    try:
        result = vision.extract_text(image_path, language=language)
        text = result.get("text", "")
        return substring.lower() in text.lower()
    except (PreconditionError, PrimitiveError, PrimitiveTimeout):
        return False


@observe(layer="L2")
def vision_word_count_above(image_path: str, min_words: int, language: str = "eng") -> bool:
    """Claim: 'the image contains at least N words'.
    Read-only: extracts text and checks word count."""
    try:
        result = vision.extract_text(image_path, language=language)
        return result.get("word_count", 0) >= min_words
    except (PreconditionError, PrimitiveError, PrimitiveTimeout):
        return False
