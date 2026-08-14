# CAPABILITIES - what Friday can do (generated from the live registry)

Status date: 2026-08-14.

**This document is GENERATED from the running code, not hand-maintained** -
regenerate it after any primitive/check/trigger change:

```sh
./.venv/bin/python -u gates/generate_capabilities.py   # rewrites gates/CAPABILITIES.md
```

The pipeline: L4 LLM planner -> L3 deterministic executor (retry policy derived
from each primitive's contract) -> L2 read-only verification -> L1 contract-
registered primitives -> L0 structured logs. An ambient watcher daemon fires
triggers on schedule with per-trigger primitive allowlists, and a closed
capability-gap loop lets human-approved new primitives register themselves.

## L1 primitives (51 registered)

Retry semantics come from each contract's idempotency class: `idempotent` = safe
to blind-retry (read-only); `at-most-once` = never blindly retried (side effect);
`commutative-safe` = safe to re-run once the target state already matches.

### `window`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `window.close_all(exclude_classes: 'list[str] | None' = None) -> 'int'` | `commutative-safe` | int: number of clients closed. | PrimitiveError from any individual close; PreconditionError if closing would touch a… |
| `window.close_window(selector: 'str') -> 'None'` | `commutative-safe` | None | PrimitiveError if a resolved address survives 5s after its close dispatch; Precondit… |
| `window.focus_window(selector: 'str') -> 'None'` | `commutative-safe` | None | PrimitiveError if the selector never becomes active. |
| `window.get_active_window() -> 'dict[str, Any] | None'` | `idempotent` | dict | None: the focused client, or None if nothing is focused. | PrimitiveError if hyprctl fails. |
| `window.list_clients() -> 'list[dict[str, Any]]'` | `idempotent` | list[dict]: raw client objects from `hyprctl clients -j`. | PrimitiveError if hyprctl fails or returns invalid JSON; PrimitiveTimeout if hyprctl… |
| `window.move_to_workspace(workspace_id: 'int', selector: 'str') -> 'None'` | `commutative-safe` | None | PrimitiveError if hyprctl rejects the arguments or the move never lands. |
| `window.open_app(command: 'str') -> 'dict[str, Any]'` | `at-most-once` | dict: the client entry that appeared. | PrimitiveError if no matching client appears within 12s - the app may still have bee… |
| `window.shutdown() -> 'None'` | `at-most-once` | None | PrimitiveError if hyprctl rejects the exit command. |

### `media`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `media.is_playing() -> 'bool'` | `idempotent` | bool | Never raises: no player -> False. |
| `media.pause() -> 'None'` | `commutative-safe` | None | No-op when no player is running. |
| `media.play(source: 'str', volume: 'int' = 70) -> 'dict[str, Any]'` | `at-most-once` | dict: {pid, socket, source}. | PrimitiveError if mpv cannot start or its IPC socket never appears; any pre-existing… |
| `media.play_for(minutes: 'float', source: 'str', volume: 'int' = 70) -> 'dict[str, Any]'` | `at-most-once` | dict: {pid, socket, length_s, source}. | PrimitiveError if mpv cannot start or its IPC socket never appears; any pre-existing… |
| `media.resume() -> 'None'` | `commutative-safe` | None | No-op when no player is running. |
| `media.set_volume(percent: 'int') -> 'None'` | `commutative-safe` | None | PreconditionError on out-of-range volume; no-op (not an error) when no player is run… |
| `media.stop() -> 'None'` | `commutative-safe` | None | None expected; stubborn processes are SIGTERM'd by the orphan sweep. |

### `browser`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `browser.click(what: 'str', timeout_ms: 'int' = 10000) -> 'dict[str, str]'` | `at-most-once` | dict: {clicked, url}. | PrimitiveError if nothing resolves or the click times out; a timed-out click may hav… |
| `browser.close() -> 'None'` | `commutative-safe` | None | Swallows closure errors; nothing left running. |
| `browser.credentials(service: 'str') -> 'dict[str, str]'` | `idempotent` | dict: {username, password}. | PrimitiveError if pass is missing, the entry is missing, or the entry is not JSON or… |
| `browser.find_locator(what: 'str', wait_ms: 'int' = 2000) -> 'Locator'` | `idempotent` | Locator: the first matching element. | PrimitiveError if nothing resolves through the whole chain (exact selector -> attrib… |
| `browser.goto(url: 'str', timeout_ms: 'int' = 30000) -> 'dict[str, str]'` | `idempotent` | dict: {url, title}. | PrimitiveError on navigation failure (bad URL, offline, timeout); a failed navigatio… |
| `browser.login(service: 'str', username_sel: 'str', password_sel: 'str', submit_sel: 'str') -> 'dict[str, str]'` | `at-most-once` | dict: {service, url}. | PrimitiveError from any sub-step; partial fill is possible, so verify the resulting … |
| `browser.press_key(what: 'str | None', key: 'str') -> 'dict[str, str]'` | `at-most-once` | dict: {key}. | PrimitiveError if 'what' is given but does not resolve. |
| `browser.read_page_text() -> 'str'` | `idempotent` | str: the page's visible text. | PrimitiveError if no page exists (call goto() first) or the context died. |
| `browser.type_text(what: 'str', text: 'str', timeout_ms: 'int' = 10000) -> 'dict[str, object]'` | `at-most-once` | dict: {typed_into, length}. | PrimitiveError if the element can neither be filled nor typed into; the field may be… |
| `browser.upload_file(what: 'str | None', path: 'str', timeout_ms: 'int' = 10000) -> 'dict[str, object]'` | `at-most-once` | dict: {path, input_count}. | PrimitiveError if no file input is found, the path is missing, or set_input_files fa… |

### `dev`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `dev.digest(context: 'dict[str, Any]', instruction: 'str' = "You are Friday's cross-project digest. Below is recent activity from the user's projects, each under a label. Produce:\n(a) a plain 2-4 sentence summary of what happened in each project, and\n(b) at most 1-2 CONCRETE suggestions for how something in one project could apply to another - an actual specific pattern, piece of code, or approach that could transfer, not vague 'consider synergies' language. If the content is too thin for a specific suggestion, say so honestly rather than inventing one.\nReply with ONLY the digest text.") -> 'str'` | `idempotent` | str: the digest text (the task's human-verifiable deliverable). | PreconditionError for an empty context or instruction; PrimitiveError when the LLM r… |
| `dev.run(task: 'str', *, cwd: 'str | None' = None, timeout_s: 'int' = 300, model: 'str' = 'opus', allow_bypass_permissions: 'bool' = False) -> 'dict[str, Any]'` | `at-most-once` | dict: the `claude --output-format json` envelope (result, is_error, u… | PrimitiveError/PrimitiveTimeout from the subprocess; the task may have had side effe… |
| `dev.run_shell(cwd: 'str', command: 'str', *, timeout_s: 'int' = 120, model: 'str' = 'opus', allow_bypass_permissions: 'bool' = False) -> 'dict[str, Any]'` | `at-most-once` | dict: {exit_code, stdout, stderr, model, duration_ms}. | PrimitiveError if claude fails or the result is not the required JSON; the command m… |

### `files`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `files.find_file(name: 'str', directory: 'str | None' = None, recursive: 'bool' = False) -> 'dict[str, Any]'` | `idempotent` | dict: {path, name, matches} - path is the chosen file, matches lists … | PreconditionError naming the directory and search term when nothing matches or the d… |
| `files.find_file_exact(name: 'str', directory: 'str | None' = None) -> 'str'` | `idempotent` | str: absolute path of the exact match, or '' when none. | Returns '' when no exact match exists (an absent file is a result, never an exceptio… |
| `files.find_recent_doc(repo_path: 'str', patterns: 'list[str] | tuple[str, ...] | None' = None) -> 'str'` | `idempotent` | str: absolute path of the chosen doc, or '' when none exists. | PreconditionError when repo_path does not exist or is not a directory. An absent doc… |
| `files.read_text(path: 'str', max_chars: 'int' = 8000) -> 'dict[str, Any]'` | `idempotent` | dict: {path, chars, truncated, text}. | PreconditionError when the path does not exist, is not a file, or max_chars is not p… |
| `files.write_text(path: 'str', text: 'str', *, append: 'bool' = False) -> 'str'` | `commutative-safe` | str: the absolute path of the written file. | PreconditionError when path is empty, parent directory does not exist, or path is no… |

### `git`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `git.log(repo_path: 'str', count: 'int' = 10, days: 'int | None' = None) -> 'list[dict[str, str]]'` | `idempotent` | list[dict]: [{commit, author, date, subject}] newest first. | PreconditionError for a missing/non-directory repo_path or an invalid count/days; Pr… |

### `gmail`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `gmail.get_message(message_id: 'str') -> 'dict[str, str]'` | `idempotent` | dict: {message_id, sender, subject, date, snippet, body}. | PrimitiveError if the message no longer exists or the fetch fails (auth/API). Never … |
| `gmail.list_unread(sender: 'str', max_results: 'int' = 5) -> 'list[dict[str, str]]'` | `idempotent` | list[dict]: [{message_id, sender, subject, date}] most recent first. | PrimitiveError on auth failure (refresh rejected) or API error - DISTINCT from 'no m… |
| `gmail.send_document(file_path: 'str', to: 'str | None' = None, subject: 'str | None' = None, body: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, thread_id, to, filename}. | PreconditionError for a missing file or an empty recipient; PrimitiveError with the … |
| `gmail.summarize(message_id: 'str') -> 'str'` | `idempotent` | str: the summary text (the task's human-verifiable deliverable). | PrimitiveError from get_message (missing message/auth) or dev.run (LLM failure); not… |

### `whatsapp`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `whatsapp.get_me() -> 'str'` | `idempotent` | str: the display phone number, e.g. '15552014242'. | PrimitiveError with the Graph API error detail on non-2xx. |
| `whatsapp.send_document(file_path: 'str', to: 'str | None' = None, caption: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, to, filename, api}. | PrimitiveError with the Graph API error detail on non-2xx. If the response is lost, … |
| `whatsapp.send_text(text: 'str', to: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, to, api}. | PrimitiveError with the Graph API error detail on non-2xx. |
| `whatsapp.upload_document(file_path: 'str') -> 'str'` | `commutative-safe` | str: the media id. | PreconditionError for missing/unsupported files; PrimitiveError with the Graph API e… |

### `telegram`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `telegram.get_me() -> 'str'` | `idempotent` | str: the bot username, e.g. 'MyFridayBot'. | PrimitiveError with the API detail on non-2xx or ok=false. |
| `telegram.send_document(file_path: 'str', to: 'str | None' = None, caption: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, chat_id, filename, api}. | PreconditionError for a missing file or empty to; PrimitiveError with the API detail… |
| `telegram.send_text(text: 'str', to: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, chat_id, api}. | PreconditionError for empty text or to; PrimitiveError with the API detail on failur… |

### `discord`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `discord.get_me() -> 'str'` | `idempotent` | str: the bot username, e.g. 'FridayBot'. | PrimitiveError with the API detail on non-2xx. |
| `discord.send_file(file_path: 'str', channel_id: 'str | None' = None, caption: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, channel_id, filename, api}. | PreconditionError for a missing file or empty channel_id; PrimitiveError with the AP… |
| `discord.send_text(text: 'str', channel_id: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, channel_id, api}. | PreconditionError for empty text or channel_id; PrimitiveError with the API detail o… |

### `notify`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `notify.notify_send(title: 'str', body: 'str' = '', timeout_ms: 'int' = 5000) -> 'dict[str, Any]'` | `commutative-safe` | dict: {title, body, sent}. | PrimitiveError if notify-send is missing (install libnotify) or exits non-zero; Prec… |

### `digestcheck`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `digestcheck.verify_attribution(digest: 'str', context: 'dict[str, Any]') -> 'str'` | `idempotent` | str: the digest text followed by an '## Attribution check' appendix (… | PreconditionError for an empty digest or empty/malformed context. Never raises on an… |

### `calendar`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `calendar.list_upcoming(days: 'int' = 7) -> 'list[dict[str, str]]'` | `idempotent` | list[dict]: [{event_id, summary, start_time, end_time, location, atte… | PrimitiveError on API/auth failure - DISTINCT from 'no upcoming events', which retur… |

## L2 verification checks (17)

Every check is side-effect-free: it reads current real-world state and returns
True/False (or a scalar) against a specific claim. A step is VERIFIED only when
its check agrees with the world - absence of an exception is never enough.

| check | claim |
|---|---|
| `checks.active_window_class` | Claim: 'the focused window's class is X' |
| `checks.browser_has_text` | Claim: 'the open page's visible text contains X' |
| `checks.browser_input_has_value` | Claim: 'the field resolved by `what` currently contains exactly the text `value`' |
| `checks.file_exists` | Claim: 'a file exists at path' |
| `checks.gmail_message_matches` | Claim: 'the fetched message's From header contains the expected sender substring' |
| `checks.gmail_unread_exists` | Claim: 'there is at least one unread message from this sender' |
| `checks.list_nonempty` | Claim: 'a step result is a non-empty list' |
| `checks.media_playing` | Claim: 'media is currently playing' |
| `checks.message_sent` | Claim: 'the messaging platform acknowledged a message with this id' |
| `checks.text_nonempty` | Claim: 'a step result is a non-empty string' |
| `checks.whatsapp_identity_ok` | Claim: 'the whatsapp credentials resolve to a real account' |
| `checks.window_client_count` | Claim: 'there are N windows open right now' |
| `checks.window_focused` | Claim: 'the currently focused window is a X' |
| `checks.window_has_class` | Claim: 'at least one open window has class X' |
| `checks.window_has_title` | Claim: 'an open window's title contains X' |
| `checks.window_on_workspace` | Claim: 'at least one open window with class X sits on workspace N' |
| `checks.window_only_classes` | Claim: 'every open window's class is in the allowed set' |

## Executor-blocked primitives

Registered but NEVER reachable from a plan or the planner catalog - the LLM
never sees them and L3 refuses them:

```
  window.shutdown
```

## Ambient watcher triggers (config/watcher.json)

| id | enabled | schedule | notify | allow |
|---|---|---|---|---|
| `ambient-gap-probe-calendar` | false | time 11:00 [daily] | false | notify.notify_send |
| `ambient-gap-probe-clipboard` | true | time 11:00 [daily] | false | notify.notify_send |
| `ambient-gap-probe-email-send` | false | time 11:05 [daily] | false | notify.notify_send |
| `ambient-gap-probe-file-write` | false | time 00:05 [daily] | false | notify.notify_send |
| `morning-gmail-summary` | true | time 09:00 [mon,tue,wed,thu,fri] | true | gmail.list_unread, gmail.get_message, gmail.summarize |
| `new-download-alert` | false | file - [daily] | true | - |
| `sunday-digest-reminder` | true | time 10:05 [sun] | false | notify.notify_send |
| `weekly-cross-project-digest` | true | time 10:00 [sun] | true | dev.digest, digestcheck.verify_attribution, files.find_rece… |

## Capability-gap loop (self-improvement)

A refused/unknown primitive step becomes a structured `capability_gap` record;
triage LLM-drafts a proposal (contract + impl + test); the automated gate (AST
checks + sandboxed test run + build-verify where applicable) filters it before
a human signature; on approval the primitive registers into L1 and the planner
auto-discovers it - the originally-refused goal then re-runs and must pass.

Gate-registered primitives (4):

- `calendar.list_upcoming`
- `files.find_file_exact`
- `files.write_text`
- `gmail.send_document`

## Ambient learning (lessons + goal proposals)

- **Lessons loop**: approved 'known mistakes' are injected into future
  synthesis (e.g. the digest's attribution lesson) so past defects shape
  later output instead of recurring.
- **Goal proposals**: mines the failure history (var/logs/tasks.jsonl) into
  candidate NEW triggers - inert until a human grants scope and allowlist.

## The ambient digest (Phase C)

Weekly (Sundays 10:00): `git.log` across the configured repos, each repo's most
recently modified status/planning doc (`files.find_recent_doc`), `dev.digest`
synthesis, `digestcheck.verify_attribution` (the provenance guard - no repo may
be credited with a mechanism not in its own gathered content) and a desktop
`notify`. The suggestions are human-judged in `gates/DIGEST_TRACKING.md`.

