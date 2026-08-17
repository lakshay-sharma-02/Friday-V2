"""L4 - Planning (LLM: goal -> plan JSON).

The only nondeterministic layer, built last on a proven substrate. Takes a
goal string and emits a plan dict in EXACTLY the schema friday.l3.executor
already consumes (goal + steps[{primitive, args, verify}]) - the executor
accepts it unmodified.

The LLM substrate is the L1 `dev` primitive (Claude Code CLI): the same
machine-tuned invocation the dev primitive already proves (MODEL_ALIAS),
so planning and execution share one substrate and every planning call is
L0-logged like any other primitive call.

Robustness: the LLM is nondeterministic, so plan() retries a bounded number
of times when the output is not parseable JSON or fails schema validation,
feeding the rejection reason back into the next attempt. A structurally
valid plan is then handed to the executor, which verifies every step
honestly - L4 never claims success, it only produces a plan.

Trust boundary: L4 output is NOT a trust boundary against hostile goals.
The executor gates every primitive through the contract registry, but a
malicious goal string could steer the LLM toward valid-but-destructive
compositions of registered primitives (e.g. dev.run with
allow_bypass_permissions). Goals are trusted user input by design; keep
this layer out of any API that accepts untrusted text.
"""

from __future__ import annotations

import importlib
import inspect
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from friday.contracts import EXECUTOR_BLOCKED, REGISTRY
from friday.errors import FridayError
from friday.lessons import record_lesson_event, render_known_mistakes
from friday.observability import emit_event, set_run_id

PROJECT_ROOT = Path(__file__).resolve().parents[2]

# Environment facts are user-editable configuration, not code: edit
# config/planner_facts.json (or point FRIDAY_FACTS_FILE elsewhere, or pass
# facts=/file_paths=/recipients= per call). The *_DEFAULT constants are
# only the fallback when no file exists or a section key is absent.
FACTS_FILE = PROJECT_ROOT / "config" / "planner_facts.json"
DEFAULT_FILE_PATHS: dict[str, str] = {
    "test_tone": str(PROJECT_ROOT / "assets" / "test_tone.mp3"),
    "readme": str(PROJECT_ROOT / "README.md"),
}
DEFAULT_RECIPIENTS: dict[str, str] = {}
DEFAULT_FACTS: list[str] = [
    "firefox launches via window.open_app(\"firefox\").",
]


@dataclass(frozen=True)
class ProjectFacts:
    """Structured PROJECT FACTS for the planning prompt.

    `facts` renders as plain bullets (OTHER FACTS). Names in `file_paths`
    and `recipients` are referenceable in plan args as $facts.<name> and
    are resolved deterministically by plan() before validation, so goals
    and plans never need hardcoded paths or recipient ids.
    """

    facts: tuple[str, ...] = ()
    file_paths: dict[str, str] = field(default_factory=dict)
    recipients: dict[str, str] = field(default_factory=dict)


def _resolve_path(raw: str) -> str:
    """Resolve a configured path: ~ expands, relative paths anchor at
    PROJECT_ROOT, so the config file is machine-portable."""
    p = Path(raw).expanduser()
    if not p.is_absolute():
        p = PROJECT_ROOT / p
    return str(p)


def load_project_facts(facts_file: Path | None = None) -> ProjectFacts:
    """Load the structured PROJECT FACTS (file paths, recipients, bullets).

    Priority: an explicit facts_file argument > $FRIDAY_FACTS_FILE > the
    default config/planner_facts.json. If the chosen file exists it is
    authoritative; a section key that is absent falls back to that
    section's built-in default. If the file does not exist, every section
    uses its default. A malformed file - or a name that appears in both
    'file_paths' and 'recipients' (a $facts.<name> reference would be
    ambiguous) - raises FridayError loudly: a silently-wrong prompt is
    worse than none.
    """
    path = facts_file or Path(os.environ.get("FRIDAY_FACTS_FILE", str(FACTS_FILE)))
    if not path.exists():
        return ProjectFacts(
            facts=tuple(DEFAULT_FACTS),
            file_paths=dict(DEFAULT_FILE_PATHS),
            recipients=dict(DEFAULT_RECIPIENTS),
        )
    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as exc:
        raise FridayError(f"facts file {path} is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise FridayError(f"facts file {path} must contain a JSON object")

    facts = data.get("facts", list(DEFAULT_FACTS))
    if not isinstance(facts, list) or not all(isinstance(f, str) for f in facts):
        raise FridayError(f"facts file {path}: 'facts' must be a list of strings")

    file_paths = data.get("file_paths", dict(DEFAULT_FILE_PATHS))
    if not isinstance(file_paths, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in file_paths.items()
    ):
        raise FridayError(
            f"facts file {path}: 'file_paths' must be an object mapping names to path strings"
        )

    recipients = data.get("recipients", dict(DEFAULT_RECIPIENTS))
    if not isinstance(recipients, dict) or not all(
        isinstance(k, str) and isinstance(v, str) for k, v in recipients.items()
    ):
        raise FridayError(
            f"facts file {path}: 'recipients' must be an object mapping names to recipient strings"
        )

    collision = set(file_paths) & set(recipients)
    if collision:
        raise FridayError(
            f"facts file {path}: name(s) {sorted(collision)} appear in both "
            "'file_paths' and 'recipients'; a $facts.<name> reference would be ambiguous"
        )

    return ProjectFacts(
        facts=tuple(facts),
        file_paths={name: _resolve_path(value) for name, value in file_paths.items()},
        recipients=dict(recipients),
    )


def load_facts(facts_file: Path | None = None) -> list[str]:
    """Backward-compatible helper: just the free-form 'facts' bullets."""
    return list(load_project_facts(facts_file).facts)


def _resolve_project(
    facts: list[str] | None,
    file_paths: dict[str, str] | None,
    recipients: dict[str, str] | None,
) -> ProjectFacts:
    """Merge per-call section overrides over the loaded config: None means
    'use the configured section' (facts file, or built-in default if
    absent); a value means 'use exactly this' - and override paths are
    resolved exactly like file-sourced ones (~ expands, relative anchors
    at PROJECT_ROOT), so the two sources stay interchangeable."""
    loaded = load_project_facts()
    return ProjectFacts(
        facts=tuple(facts) if facts is not None else loaded.facts,
        file_paths=(
            {name: _resolve_path(value) for name, value in file_paths.items()}
            if file_paths is not None
            else loaded.file_paths
        ),
        recipients=recipients if recipients is not None else loaded.recipients,
    )


# $facts.<name> references let the LLM emit config by name ("file_path":
# "$facts.readme", "to": "$facts.whatsapp"); plan() substitutes the value
# deterministically before validation, so the emitted plan never needs to
# transcribe hardcoded paths or recipient ids. Names must start with a
# letter or underscore: literal prose like "$facts.50" is never a ref.
_FACTS_REF = re.compile(r"\$facts\.([A-Za-z_][A-Za-z0-9_.-]*)")


def _substitute_facts_refs(value: Any, project: ProjectFacts) -> Any:
    """Replace every $facts.<name> reference with its configured value,
    recursively through dicts/lists/strings. file_paths wins over
    recipients (a cross-section collision is a load-time error, so the
    lookup is unambiguous). An unknown name raises FridayError so plan()
    can feed the rejection reason back into the next attempt. Returns a
    new structure; the input is never mutated."""
    if isinstance(value, dict):
        return {k: _substitute_facts_refs(v, project) for k, v in value.items()}
    if isinstance(value, list):
        return [_substitute_facts_refs(v, project) for v in value]
    if not isinstance(value, str):
        return value

    def repl(m: re.Match[str]) -> str:
        name = m.group(1)
        if name in project.file_paths:
            return project.file_paths[name]
        if name in project.recipients:
            return project.recipients[name]
        known = sorted(set(project.file_paths) | set(project.recipients))
        raise FridayError(
            f"$facts.{name} is not a configured name "
            f"(known names: {', '.join(known) or 'none'})"
        )

    return _FACTS_REF.sub(repl, value)


_FACTS_REF_ANY = re.compile(r"\$facts\.")


def _has_unresolved_facts_ref(value: Any) -> bool:
    """True if any string in value still carries a $facts.<name>
    reference. validate_plan uses this to reject plans that reach it
    unresolved - the executor resolves only $steps.N.result, never
    $facts, so a leftover ref would flow through as a literal string."""
    if isinstance(value, dict):
        return any(_has_unresolved_facts_ref(v) for v in value.values())
    if isinstance(value, list):
        return any(_has_unresolved_facts_ref(v) for v in value)
    return isinstance(value, str) and bool(_FACTS_REF_ANY.search(value))


# Every L1 module, imported so the contract registry is fully populated.
# The tuple is the FALLBACK; _discover_l1_modules() prefers scanning the
# friday/l1/ directory so a primitive registered through the capability-gap
# gate becomes planable WITHOUT editing this list.
_L1_MODULES = ("window", "media", "browser", "dev", "digestcheck", "files", "git", "calendar", "clipboard", "screenshot", "whatsapp", "telegram", "discord", "gmail", "notify")

DEFAULT_ATTEMPTS = 3
DEFAULT_TIMEOUT_S = 300


# -------------------------------------------------------------- registry


def _discover_l1_modules() -> list[str]:
    """Every module name in friday/l1/ (FRIDAY_L1_DIR overrides the
    directory - the capability-gap gate's tests point it at a temp dir).
    Falls back to _L1_MODULES when the scan fails."""
    # parents[2] of friday/l4/planner.py is the PROJECT ROOT. REGRESSION
    # (2026-08-13, found live by cycle 2): parents[1] is the friday PACKAGE
    # dir itself, so the default base was <root>/friday/friday/l1
    # (nonexistent) - the glob silently returned nothing and discovery
    # ALWAYS fell back to the hardcoded tuple. New module files (e.g.
    # friday/l1/calendar.py, the loop's first new-module registration)
    # were never discovered and never became planable.
    base = Path(
        os.environ.get(
            "FRIDAY_L1_DIR",
            str(Path(__file__).resolve().parents[2] / "friday" / "l1"),
        )
    )
    try:
        names = sorted(p.stem for p in base.glob("*.py") if p.stem != "__init__")
    except OSError:
        names = []
    return names or list(_L1_MODULES)


def _ensure_registry() -> None:
    """Import every L1 module so REGISTRY is complete. Importing has no
    side effects beyond registering contracts - nothing sends or launches."""
    for name in _discover_l1_modules():
        importlib.import_module(f"friday.l1.{name}")


def _checks() -> dict[str, Any]:
    import friday.l2.checks as checks

    return {
        n: getattr(checks, n)
        for n in dir(checks)
        if not n.startswith("_")
        and callable(getattr(checks, n))
        and getattr(getattr(checks, n), "__module__", "") == checks.__name__
    }


# ---------------------------------------------------------------- catalog


def _sig(fn: Any) -> str:
    try:
        return str(inspect.signature(fn))
    except (TypeError, ValueError):
        return "(...?)"


def _signature(fn: Any) -> inspect.Signature | None:
    """Signature for kwarg checking, or None when it cannot be determined
    (then kwargs are not validated - a **kwargs parameter also yields None,
    since any kwarg is accepted there)."""
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return None
    if any(p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()):
        return None
    return sig


def build_catalog() -> str:
    """Compact text catalog of every contract-registered primitive and every
    L2 check, derived from the registry at call time so it can never drift
    from what the executor will actually resolve."""
    _ensure_registry()
    lines: list[str] = ["PRIMITIVES:"]
    for qualified in sorted(REGISTRY):
        if qualified in EXECUTOR_BLOCKED:
            continue  # never advertise a blocked primitive to the LLM
        c = REGISTRY[qualified]
        mod_name, _, fn_name = qualified.partition(".")
        fn = getattr(importlib.import_module(f"friday.l1.{mod_name}"), fn_name)
        doc = inspect.getdoc(fn) or ""
        summary = doc.split(".")[0].strip() if doc else ""
        lines.append(
            f"- {qualified}{_sig(fn)}  [idempotency={c.idempotency.value}]"
        )
        if summary:
            lines.append(f"    {summary}.")
        if c.returns:
            lines.append(f"    returns: {c.returns}")
    lines.append("")
    lines.append("READ-ONLY CHECKS (verification - never mutate state):")
    for name, fn in sorted(_checks().items()):
        doc = inspect.getdoc(fn) or ""
        summary = doc.split(".")[0].strip() if doc else ""
        lines.append(f"- checks.{name}{_sig(fn)} -> {summary or 'bool'}")
    return "\n".join(lines)


# --------------------------------------------------------------- prompt


def build_prompt(
    goal: str,
    last_error: str | None = None,
    facts: list[str] | None = None,
    file_paths: dict[str, str] | None = None,
    recipients: dict[str, str] | None = None,
) -> str:
    """Assemble the full planning prompt. `facts` / `file_paths` /
    `recipients` override the corresponding PROJECT FACTS section; None
    loads the configured section (config/planner_facts.json, or built-in
    defaults if absent)."""
    catalog = build_catalog()
    project = _resolve_project(facts, file_paths, recipients)
    paths_rendered = "\n".join(
        f"- {name}: {path}" for name, path in sorted(project.file_paths.items())
    ) or "  (none configured)"
    recipients_rendered = "\n".join(
        f"- {name}: {value}" for name, value in sorted(project.recipients.items())
    ) or "  (none configured - senders default to the credential recipient)"
    facts_rendered = "\n".join(f"- {f}" for f in project.facts) or "  (none configured)"
    # the bounded, human-approved KNOWN MISTAKES block for planning (""
    # when none approved) - approved lessons shape the next plan, they
    # never gate it
    lessons_block = render_known_mistakes("planner")
    retry_note = (
        f"\nYOUR PREVIOUS PLAN WAS REJECTED with this error:\n    {last_error}\n"
        "Fix the plan so it passes the schema and rules above.\n"
        if last_error
        else ""
    )
    return f"""You are the planning layer of 'Friday', a deterministic desktop
automation agent. Convert the GOAL into a machine-readable plan.

SCHEMA - the output must match EXACTLY; a deterministic executor consumes
it without modification. A plan is a JSON object:
{{
  "goal": "<the goal string, copied verbatim>",
  "steps": [
    {{
      "primitive": "module.function",
      "args": {{ ... }},
      "verify": {{
        "check": "checks.name",
        "args": {{ ... }},
        "expect": <exact JSON value the check must return>
      }}
    }}
  ]
}}

Optional per-step fields (rarely needed):
  "retries": <int>     - explicit override; omit to use the contract default
  "backoff_s": <float> - seconds between retries
  "verify_wait_s": <float> - how long to poll the check before giving up
These are TOP-LEVEL step fields - siblings of "primitive", "args" and
"verify" - never nested inside "verify".

RULES:
1. Use ONLY the primitives and checks listed below. Never invent names.
2. EVERY step MUST carry a "verify" that reads real state (through the
   listed read-only checks) confirming that step's effect - the executor
   refuses steps whose effect cannot be proven.
3. Primitives marked [at-most-once] have side effects that must never be
   duplicated: call each at most once in the whole plan. In particular,
   NEVER open the same app twice - one open is enough, a second open is
   redundant and creates ambiguity. Primitives marked [idempotent] or
   [commutative-safe] may be re-invoked harmlessly.
4. "expect" must be the exact JSON type the check returns: booleans
   true/false (not the strings "true"/"false"), numbers, or strings.
5. A step may reference the return value of an EARLIER step with
   "$steps.N.result.key" (N is the 1-based step number) in any args or
   verify value. ARGS resolve before the primitive runs (prior steps
   only); VERIFY values resolve after it runs, so a step's verify may also
   reference the CURRENT step's own result (e.g. a send step verifies its
   returned message id). Never reference a future step. To close or
   manipulate an app you just opened, pass the address from that open
   step's result, e.g. "selector": "$steps.1.result.address" - this is
   unambiguous even when several windows share a class. Integer path
   segments index into LIST results, e.g. "$steps.1.result.0.message_id"
   is the first element's message_id (primitive list results are ordered,
   most-relevant first).
6. Do not write verifies that assume the whole desktop is empty - other
   applications are running. Verify the specific thing the goal mentions
   (e.g. checks.window_has_class with cls "firefox"), never a global
   count like checks.window_client_count == 0.
7. Do not invent steps the goal does not need; keep the plan minimal.
8. Output ONLY the JSON plan object. No markdown fences, no commentary,
   no text before or after.
9. NAMED CONFIG REFERENCES: when the goal names a file or recipient that
   appears in the NAMED FILE PATHS / NAMED RECIPIENTS sections below,
   emit a $facts.<name> reference in the plan arg (e.g. "file_path":
   "$facts.readme", "to": "$facts.whatsapp") instead of transcribing a
   hardcoded value - the planner resolves it deterministically before
   execution. Never invent a $facts.<name> that is not listed; an unknown
   reference rejects the plan. A literal path or recipient id written in
   the GOAL that is not in those sections is NOT a $facts reference: use
   it exactly as written.

EXAMPLE (open an app, then close exactly that window by address):
{{
  "goal": "open firefox and close it",
  "steps": [
    {{"primitive": "window.open_app", "args": {{"command": "firefox"}},
      "verify": {{"check": "checks.window_has_class", "args": {{"cls": "firefox"}}, "expect": true}}}},
    {{"primitive": "window.close_window", "args": {{"selector": "$steps.1.result.address"}},
      "verify": {{"check": "checks.window_has_class", "args": {{"cls": "firefox"}}, "expect": false}}}}
  ]
}}

EXAMPLE (play audio for a fixed time and prove it stops BY ITSELF):
{{
  "goal": "play the test tone for 1 minute and verify it stops by itself",
  "steps": [
    {{"primitive": "media.play_for", "args": {{"minutes": 1, "source": "$facts.test_tone"}},
      "verify": {{"check": "checks.media_playing", "args": {{}}, "expect": true}}}},
    {{"primitive": "media.is_playing", "args": {{}},
      "verify": {{"check": "checks.media_playing", "args": {{}}, "expect": false}},
      "verify_wait_s": 70}}
  ]
}}

PROJECT FACTS (environment context; edit config/planner_facts.json or
point $FRIDAY_FACTS_FILE at another file). Goals may reference any NAMED
entry below in plan args as $facts.<name>; the planner resolves it
deterministically before execution:

NAMED FILE PATHS ($facts.<name>):
{paths_rendered}

NAMED RECIPIENTS ($facts.<name> - or omit a send's recipient arg to use
the credential default):
{recipients_rendered}

OTHER FACTS:
{facts_rendered}

FRAMEWORK NOTES (always on):
- window.close_window accepts an address from an earlier step's result
  (e.g. "$steps.1.result.address") OR a class name such as "firefox".
- Only window.open_app returns a client dict with an 'address' key.
  window.focus_window, window.move_to_workspace and window.close_window
  all RETURN None - their results have no .address. When a goal opens a
  window then focuses/moves/closes it, reference the OPEN step's result
  ("$steps.1.result.address") in every later step's selector, never a
  later step's result.
- To verify a window.close_all step (a 'close everything except X'
  goal), use checks.window_only_classes with the classes you EXCLUDED,
  e.g. "verify": {{"check": "checks.window_only_classes",
  "args": {{"classes": ["kitty"]}}, "expect": true}} - it asserts
  every remaining window's class is in that set, which is the SUFFICIENT
  proof that nothing outside the excluded set survived.
  checks.window_focused proves only where focus landed, not that
  everything else closed - never use it to verify a close_all step.
- All three messaging send primitives default the recipient from
  configured credentials: whatsapp.send_document/send_text (default
  phone), telegram.send_document/send_text (default chat),
  discord.send_file/send_text (default channel). Omit the recipient arg
  to use the default.
- A send step may instead name a configured recipient from NAMED
  RECIPIENTS in the recipient arg: "to": "$facts.whatsapp" (or
  "chat_id"/"channel_id" for telegram/discord). Omit the arg to use the
  credential default.
- For WEB tasks use the browser.* primitives (Playwright). browser.goto
  requires a full http(s):// URL ("https://example.com", never a bare
  hostname like "example.com") and returns {{"url", "title"}}; verify a
  navigation with checks.browser_has_text on a distinctive substring of
  the page. The visible page text rarely contains the bare hostname - if
  the goal names expected content ("Example Domain"), verify THAT. Do
  not verify a hostname that does not appear on the page.
  window.open_app launches a DESKTOP application window and is not
  needed for web navigation - do not open a browser app AND call
  browser.goto for the same goal.
- To interact with a page, type_text's `what` must be a REAL string the
  page shows - placeholder, aria-label or name text. For DuckDuckGo the
  search box placeholder is literally "search privately" - use THAT
  exact string, never a description like "search box" (a made-up handle
  cannot resolve and the step fails). Use the same `what` string in
  checks.browser_input_has_value. Never use a single-character handle
  like "q". Submit with press_key ("what": null, "key": "Enter") and
  verify the RESULT page with checks.browser_has_text on a distinctive
  phrase you expect to see in the results.
- To OPEN a link (e.g. a search result), use browser.click(what) with
  'what' being the link's real visible text (e.g. "Example Domain").
  When the goal expects a specific target page (e.g. "the first result
  should be example.com"), do NOT verify the click with text that also
  appears on the search results page (a result's own title/snippet does) -
  that  can pass before the navigation happens. Verify with text
  DISTINCTIVE to the target page, and end with a browser.read_page_text
  step whose output IS the report of the page that opened.
- Never pass a secret (password/token) as type_text's `text` argument -
  typed text is written to the L0 log. Credentials go through
  browser.login(service, ...), which fills them without logging them.
- To act on a file you can only DESCRIBE (e.g. "the receipt pdf in my
  downloads"), locate it first: files.find_file returns {{"path": ...}}.
  Step 1 finds it (verify with checks.file_exists on
  "$steps.1.result.path" expect true), step 2 sends it with
  "file_path": "$steps.1.result.path". Pass "directory":
  "$facts.downloads" (or any configured folder / absolute path); "name"
  is a case-insensitive substring of the filename; add "recursive":
  true only if the file may be nested in subfolders. If several files
  match, the first (sorted) is returned - name the goal precisely when
  it matters.
- To verify a send step, use checks.message_sent with the platform name
  and the send step's OWN returned message id:
    "verify": {{"check": "checks.message_sent",
               "args": {{"platform": "whatsapp", "message_id": "$steps.N.result.message_id"}},
               "expect": true}}
  where N is that send step's own 1-based number.
- Gmail is READ-ONLY. gmail.list_unread(sender) returns a LIST of
  {{message_id, sender, subject, date}}; take the first element with
  "$steps.N.result.0.message_id" (dot or bracket syntax both work) and
  verify the step with checks.gmail_unread_exists(sender).
  gmail.get_message(message_id) returns {{message_id, sender, subject,
  date, snippet, body}}; verify it with
  checks.gmail_message_matches(message_id=...,
  expected_sender_substring=<the sender from the goal>) - never invent an
  unrelated check. gmail.summarize(message_id) returns the summary TEXT;
  verify it the SAME way - checks.gmail_message_matches on the SOURCE
  message_id (chain of custody back to the verified message). There is no
  L2 check for summary quality; never use browser/media/window checks for
  gmail steps. A gmail goal needs ONLY gmail.* primitives - never
  browser.* (goto/login/read_page_text) or dev.* steps: the mailbox is
  read through the API, not by opening mail.google.com in a browser, and
  no login flow is ever part of a gmail task. Keep the plan minimal:
  list_unread -> get_message -> summarize is the whole shape.
- To play audio FOR A FIXED TIME use media.play_for(minutes, source): it
  stops AUTOMATICALLY after that many minutes (mpv --length plus a
  one-shot safety timer). Never use media.play for a timed goal - it plays
  until stopped. When the goal says "the test tone", that is the
  configured fixture: pass "source": "$facts.test_tone" DIRECTLY - do not
  files.find_file it (it is already a NAMED FILE PATH, and find_file
  without recursion cannot see it inside assets/). To PROVE the auto-stop
  is the goal's effect, add a SEPARATE later step that polls
  checks.media_playing expecting false with a "verify_wait_s" longer than
  minutes*60 (e.g. minutes=1 -> "verify_wait_s": 70);  the carrier step
  primitive can be the read-only media.is_playing. Do not expect false on
  the play_for step itself unless that step also carries a "verify_wait_s"
  long enough to reach the auto-stop (the check then only passes once
  playback has actually ended). Never
  use media.stop or media.pause to satisfy a goal about stopping by
  itself - that masks the timer and proves nothing. Never use dev.run or
  dev.run_shell to wait out a timer - they invoke the LLM CLI, cost a
  call, and are not a reliable clock; the step's "verify_wait_s" IS the
  wait mechanism.

{catalog}

{lessons_block}
GOAL: {goal}
{retry_note}
Output the plan JSON now."""


# -------------------------------------------------------------- parsing


def _extract_json(text: str) -> dict[str, Any] | None:
    """Parse the model's output as a single JSON object. Tolerates stray
    markdown fences even though the prompt forbids them."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    try:
        value = json.loads(text)
        return value if isinstance(value, dict) else None
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            value = json.loads(text[start : end + 1])
            return value if isinstance(value, dict) else None
        except json.JSONDecodeError:
            return None
    return None


# ------------------------------------------------------------ validation


def validate_plan(plan: dict[str, Any]) -> tuple[bool, str]:
    """Check the plan against the exact schema the executor accepts, plus
    the 'only registered primitives / real checks' rules. Returns
    (ok, error_message). Catches malformed plans BEFORE the executor ever
    sees them, so the planner can retry instead of aborting a whole goal."""
    _ensure_registry()
    if not isinstance(plan, dict):
        return False, "plan is not a JSON object"
    goal = plan.get("goal")
    if not isinstance(goal, str) or not goal.strip():
        return False, "missing non-empty 'goal' string"
    steps = plan.get("steps")
    if not isinstance(steps, list) or not steps:
        return False, "missing non-empty 'steps' list"
    checks = _checks()
    for i, raw in enumerate(steps, start=1):
        if not isinstance(raw, dict):
            return False, f"step {i}: not an object"
        primitive = raw.get("primitive")
        if not isinstance(primitive, str) or primitive not in REGISTRY:
            return False, f"step {i}: unknown or unregistered primitive {primitive!r}"
        if primitive in EXECUTOR_BLOCKED:
            return False, (
                f"step {i}: primitive {primitive!r} is blocked from execution "
                "(EXECUTOR_BLOCKED)"
            )
        args = raw.get("args")
        if args is not None and not isinstance(args, dict):
            return False, f"step {i}: 'args' must be an object"
        v = raw.get("verify")
        if not isinstance(v, dict):
            return False, f"step {i}: missing 'verify' object"
        check = v.get("check")
        bare = check.removeprefix("checks.") if isinstance(check, str) else check
        if not isinstance(bare, str) or bare not in checks:
            return False, f"step {i}: unknown check {check!r}"
        if "expect" not in v:
            return False, f"step {i}: verify needs an 'expect' value"
        # Signature-check the kwargs NOW: a wrong arg name would otherwise
        # crash the executor with a raw TypeError (its verify/primitives
        # path catches only FridayError). The planner can retry; the
        # executor cannot - catch it here.
        mod_name, _, fn_name = primitive.partition(".")
        fn = getattr(importlib.import_module(f"friday.l1.{mod_name}"), fn_name)
        if (psig := _signature(fn)) is not None:
            for key in (args or {}):
                if key not in psig.parameters:
                    return False, f"step {i}: primitive {primitive} does not accept arg {key!r}"
        check_fn = checks[bare]
        if (csig := _signature(check_fn)) is not None:
            for key in (v.get("args") or {}):
                if key not in csig.parameters:
                    return False, f"step {i}: check {check!r} does not accept arg {key!r}"
        if "retries" in raw:
            try:
                int(raw["retries"])
            except (TypeError, ValueError):
                return False, f"step {i}: 'retries' must be an integer"
        for field in ("backoff_s", "verify_wait_s"):
            # Accepted at the step level (canonical) or nested inside
            # 'verify' - the LLM has emitted both; they mean the same
            # thing and the executor reads both. bool is excluded even
            # though bool is an int subclass - a plan author writing
            # true/false for a timing value is a mistake. Deliberately
            # stricter than the executor (where float(True)==1.0 would
            # pass): bad plans are caught here, at planning time, where
            # they can be retried.
            if field in raw or field in v:
                val = raw.get(field, v.get(field))
                if not isinstance(val, (int, float)) or isinstance(val, bool) or val <= 0:
                    return False, f"step {i}: '{field}' must be a positive number"
        # Unresolved $facts.<name> references must never reach the
        # executor (it resolves only $steps.N.result, so a leftover ref
        # would be passed to the primitive as a literal string). plan()
        # substitutes them before calling this, so only hand-written or
        # mis-plumbed plans trip here - rejected loudly, like every other
        # bad plan, at planning time where they can be retried.
        if _has_unresolved_facts_ref(args) or _has_unresolved_facts_ref(v):
            return False, (
                f"step {i}: $facts.<name> references must be resolved before "
                "validation - run the plan through planner.plan()"
            )
    return True, ""


# ------------------------------------------------------------------ plan


def plan(
    goal: str,
    *,
    run_id: str | None = None,
    attempts: int = DEFAULT_ATTEMPTS,
    timeout_s: int = DEFAULT_TIMEOUT_S,
    facts: list[str] | None = None,
    file_paths: dict[str, str] | None = None,
    recipients: dict[str, str] | None = None,
) -> dict[str, Any]:
    """LLM call: goal string in, plan JSON out (L3 schema). Bounded retries
    on unparseable/invalid output. Logs every attempt through L0 at
    layer=L4. `facts` / `file_paths` / `recipients` override the
    corresponding PROJECT FACTS section (default: config/planner_facts.json,
    or built-in defaults if absent); $facts.<name> references in the
    model's output are resolved against them before validation."""
    from friday.l1.dev import run as dev_run

    if run_id:
        set_run_id(run_id)
    if not goal or not goal.strip():
        raise FridayError("plan() requires a non-empty goal")
    if attempts < 1:
        raise FridayError("plan() requires attempts >= 1")
    project = _resolve_project(facts, file_paths, recipients)

    emit_event(
        layer="L4", primitive="plan",
        args={"goal": goal, "attempts": attempts}, result="PENDING",
    )
    last_error: str | None = None
    for i in range(1, attempts + 1):
        emit_event(
            layer="L4", primitive="plan.attempt",
            args={"attempt": i, "max_attempts": attempts}, result="RUNNING",
        )
        try:
            env = dev_run(
                # Pass the already-resolved project so the prompt and the
                # later $facts substitution can never disagree (and the
                # config file is read once per attempt, not twice).
                build_prompt(
                    goal, last_error,
                    facts=list(project.facts),
                    file_paths=project.file_paths,
                    recipients=project.recipients,
                ),
                cwd=str(PROJECT_ROOT),
                timeout_s=timeout_s,
            )
        except FridayError as exc:
            last_error = f"LLM call failed: {exc}"
            # every failed attempt is a lesson event (best-effort) - the
            # lessons loop generalizes planner failure classes over time
            record_lesson_event(category="planner_llm_error", source="planner", detail=last_error, goal_id=goal[:80])
            emit_event(layer="L4", primitive="plan.attempt", args={"attempt": i}, result="FAILED", exception=last_error)
            continue
        if env.get("is_error"):
            last_error = f"LLM reported an error: {str(env.get('result'))[:200]}"
            record_lesson_event(category="planner_llm_error", source="planner", detail=last_error, goal_id=goal[:80])
            emit_event(layer="L4", primitive="plan.attempt", args={"attempt": i}, result="FAILED", exception=last_error)
            continue
        text = env.get("result") or ""
        parsed = _extract_json(text)
        if parsed is None:
            last_error = "LLM output was not parseable JSON"
            record_lesson_event(category="planner_unparseable", source="planner", detail=last_error, goal_id=goal[:80])
            emit_event(layer="L4", primitive="plan.attempt", args={"attempt": i}, result="FAILED", exception=last_error)
            continue
        try:
            parsed = _substitute_facts_refs(parsed, project)
        except FridayError as exc:
            last_error = f"plan references an unknown facts name: {exc}"
            record_lesson_event(category="planner_facts_ref", source="planner", detail=last_error, goal_id=goal[:80])
            emit_event(layer="L4", primitive="plan.attempt", args={"attempt": i}, result="FAILED", exception=last_error)
            continue
        ok, err = validate_plan(parsed)
        if not ok:
            last_error = f"plan failed schema validation: {err}"
            # classify the failure: an invented primitive is a different
            # lesson than a structural schema slip
            if "unknown or unregistered primitive" in err:
                lesson = "planner_unknown_primitive"
            elif "blocked from execution" in err:
                lesson = "planner_blocked_primitive"
            else:
                lesson = "planner_schema"
            record_lesson_event(category=lesson, source="planner", detail=last_error, goal_id=goal[:80])
            emit_event(layer="L4", primitive="plan.attempt", args={"attempt": i}, result="FAILED", exception=last_error)
            continue
        emit_event(
            layer="L4", primitive="plan",
            args={"goal": goal, "steps": len(parsed["steps"])}, result="ACCEPTED",
        )
        return parsed

    msg = f"no valid plan after {attempts} attempts: {last_error}"
    emit_event(layer="L4", primitive="plan", result="ABORT", exception=msg)
    raise FridayError(msg)
