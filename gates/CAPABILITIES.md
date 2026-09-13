# CAPABILITIES - what Friday can do (generated from the live registry)

Status date: 2026-09-12.

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

## L1 primitives (128 registered)

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
| `media.get_playing_title() -> 'str | None'` | `idempotent` | str | None - the current media title (mpv 'media-title' property), or… | Never raises: a missing or unreachable mpv player is reported as None, not an error.… |
| `media.get_volume() -> 'int | None'` | `idempotent` | int | None - the current volume in the 0-100 range, or None when no p… | Never raises: a missing or unreachable mpv player is reported as None, not an error.… |
| `media.is_playing() -> 'bool'` | `idempotent` | bool | Never raises: no player -> False. |
| `media.list_playlists() -> 'list[dict[str, Any]]'` | `idempotent` | list[dict]: list of {index, title, duration_s, played_count, duration… | No-op when no player running; returns empty list gracefully. |
| `media.pause() -> 'None'` | `commutative-safe` | None | No-op when no player is running. |
| `media.play(source: 'str', volume: 'int' = 70) -> 'dict[str, Any]'` | `at-most-once` | dict: {pid, socket, source}. | PrimitiveError if mpv cannot start or its IPC socket never appears; any pre-existing… |
| `media.play_for(minutes: 'float', source: 'str', volume: 'int' = 70) -> 'dict[str, Any]'` | `at-most-once` | dict: {pid, socket, length_s, source}. | PrimitiveError if mpv cannot start or its IPC socket never appears; any pre-existing… |
| `media.play_media(source: 'str', volume: 'int' = 70) -> 'dict[str, Any]'` | `at-most-once` | dict: {pid, socket, source, volume}. | PrimitiveError if mpv cannot start or its IPC socket never appears. |
| `media.resume() -> 'None'` | `commutative-safe` | None | No-op when no player is running. |
| `media.seek(position_s: 'float') -> 'dict[str, Any]'` | `commutative-safe` | dict: {success: bool, position_s: float}. | No-op when no player is running; PrimitiveError on invalid position. |
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
| `browser.screenshot(output_path: 'str | None' = None) -> 'str'` | `idempotent` | str: absolute path to the saved screenshot. | PrimitiveError if no page is open or screenshot fails. |
| `browser.type_text(what: 'str', text: 'str', timeout_ms: 'int' = 10000) -> 'dict[str, object]'` | `at-most-once` | dict: {typed_into, length}. | PrimitiveError if the element can neither be filled nor typed into; the field may be… |
| `browser.upload_file(what: 'str | None', path: 'str', timeout_ms: 'int' = 10000) -> 'dict[str, object]'` | `at-most-once` | dict: {path, input_count}. | PrimitiveError if no file input is found, the path is missing, or set_input_files fa… |

### `dev`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `dev.digest(context: 'dict[str, Any]', instruction: 'str' = "You are Friday's cross-project digest. Below is recent activity from the user's projects, each under a label. Produce:\n(a) a plain 2-4 sentence summary of what happened in each project, and\n(b) at most 1-2 CONCRETE suggestions for how something in one project could apply to another - an actual specific pattern, piece of code, or approach that could transfer, not vague 'consider synergies' language. If the content is too thin for a specific suggestion, say so honestly rather than inventing one.\n(c) Identify 1-2 semantic themes/categories evident across the repos (e.g., 'email processing', 'security hardening', 'UI retheme', 'kernel setup') and note if any patterns could transfer between repos.\n(d) Focus suggestions on semantic patterns that actually exist in each repo's own content - do not invent mechanisms or attribute patterns to repos that don't have them.\nReply with ONLY the digest text.") -> 'str'` | `idempotent` | str: the digest text (the task's human-verifiable deliverable). | PreconditionError for an empty context or instruction; PrimitiveError when the LLM r… |
| `dev.run(task: 'str', *, cwd: 'str | None' = None, timeout_s: 'int' = 300, model: 'str' = 'opus', allow_bypass_permissions: 'bool' = False) -> 'dict[str, Any]'` | `at-most-once` | dict: the `claude --output-format json` envelope (result, is_error, u… | PrimitiveError/PrimitiveTimeout from the subprocess; the task may have had side effe… |
| `dev.run_shell(cwd: 'str', command: 'str', *, timeout_s: 'int' = 120, model: 'str' = 'opus', allow_bypass_permissions: 'bool' = False) -> 'dict[str, Any]'` | `at-most-once` | dict: {exit_code, stdout, stderr, model, duration_ms}. | PrimitiveError if claude fails or the result is not the required JSON; the command m… |

### `files`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `files.copy(source: 'str', dest_dir: 'str') -> 'str'` | `commutative-safe` | str: absolute path of the copied file. | PreconditionError for missing source/dest; PrimitiveError on copy failure. |
| `files.delete(path: 'str') -> 'str'` | `at-most-once` | str: the path that was deleted. | PreconditionError for missing file; PrimitiveError on delete failure. |
| `files.file_size(path: 'str') -> 'dict[str, Any]'` | `idempotent` | dict: {path, size_bytes, size_human}. | PreconditionError for missing file. |
| `files.find_file(name: 'str', directory: 'str | None' = None, recursive: 'bool' = False) -> 'dict[str, Any]'` | `idempotent` | dict: {path, name, matches} - path is the chosen file, matches lists … | PreconditionError naming the directory and search term when nothing matches or the d… |
| `files.find_file_exact(name: 'str', directory: 'str | None' = None) -> 'str'` | `idempotent` | str: absolute path of the exact match, or '' when none. | Returns '' when no exact match exists (an absent file is a result, never an exceptio… |
| `files.find_newest(name: 'str', directory: 'str') -> 'str'` | `idempotent` | str: absolute path of the newest matching file, or '' when none exist… | PreconditionError when name or directory is empty or the directory does not exist; r… |
| `files.find_recent_doc(repo_path: 'str', patterns: 'list[str] | tuple[str, ...] | None' = None) -> 'str'` | `idempotent` | str: absolute path of the chosen doc, or '' when none exists. | PreconditionError when repo_path does not exist or is not a directory. An absent doc… |
| `files.list_dir(path: 'str' = '.') -> 'dict[str, Any]'` | `idempotent` | dict: {path, files: list[str], dirs: list[str], count: int}. | PreconditionError for missing directory. |
| `files.move(source: 'str', dest_dir: 'str') -> 'str'` | `at-most-once` | str: absolute path of the moved file. | PreconditionError for missing source/dest; PrimitiveError on move failure. |
| `files.read_text(path: 'str', max_chars: 'int' = 8000) -> 'dict[str, Any]'` | `idempotent` | dict: {path, chars, truncated, text}. | PreconditionError when the path does not exist, is not a file, or max_chars is not p… |
| `files.write_text(path: 'str', text: 'str', *, append: 'bool' = False) -> 'str'` | `commutative-safe` | str: the absolute path of the written file. | PreconditionError when path is empty, parent directory does not exist, or path is no… |

### `git`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `git.branch(repo_path: 'str') -> 'dict[str, Any]'` | `idempotent` | dict: {current: str, branches: list[str]}. | PreconditionError for missing repo; PrimitiveError if git fails. |
| `git.commit(repo_path: 'str', message: 'str', files: 'list[str] | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {commit_hash: str, message: str}. | PreconditionError for empty message or missing repo; PrimitiveError if git commit fa… |
| `git.diff(repo_path: 'str') -> 'dict[str, Any]'` | `idempotent` | dict: {staged: str, unstaged: str, is_clean: bool}. | PreconditionError for missing repo; PrimitiveError if git fails. |
| `git.log(repo_path: 'str', count: 'int' = 10, days: 'int | None' = None) -> 'list[dict[str, str]]'` | `idempotent` | list[dict]: [{commit, author, date, subject}] newest first. | PreconditionError for a missing/non-directory repo_path or an invalid count/days; Pr… |
| `git.status(repo_path: 'str') -> 'dict'` | `idempotent` | dict: {branch: str, staged: list[str], conflicts: list[str], uncommit… | PreconditionError for a missing/non-directory repo_path; PrimitiveError if git itsel… |

### `gmail`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `gmail.get_message(message_id: 'str') -> 'dict[str, str]'` | `idempotent` | dict: {message_id, sender, subject, date, snippet, body}. | PrimitiveError if the message no longer exists or the fetch fails (auth/API). Never … |
| `gmail.list_unread(sender: 'str', max_results: 'int' = 5) -> 'list[dict[str, str]]'` | `idempotent` | list[dict]: [{message_id, sender, subject, date}] most recent first. | PrimitiveError on auth failure (refresh rejected) or API error - DISTINCT from 'no m… |
| `gmail.mark_read(message_id: 'str') -> 'dict[str, str]'` | `commutative-safe` | dict: {message_id, status}. | PrimitiveError on API failure. |
| `gmail.search(query: 'str', max_results: 'int' = 10) -> 'list[dict[str, str]]'` | `idempotent` | list[dict]: [{message_id, sender, subject, date, snippet}]. | PrimitiveError on auth/API failure. |
| `gmail.send_document(file_path: 'str', to: 'str | None' = None, subject: 'str | None' = None, body: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, thread_id, to, filename}. | PreconditionError for a missing file or an empty recipient; PrimitiveError with the … |
| `gmail.send_text(text: 'str', to: 'str | None' = None, subject: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, thread_id, to}. | PreconditionError for empty text/to; PrimitiveError on API failure. |
| `gmail.summarize(message_id: 'str') -> 'str'` | `idempotent` | str: the summary text (the task's human-verifiable deliverable). | PrimitiveError from get_message (missing message/auth) or dev.run (LLM failure); not… |

### `whatsapp`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `whatsapp.download_media(media_id: 'str', dest_dir: 'str | None' = None, filename: 'str | None' = None) -> 'dict[str, Any]'` | `idempotent` | dict: {path, filename, mime_type, file_size}. | PreconditionError for empty media_id; PrimitiveError on network/download failure. |
| `whatsapp.get_me() -> 'str'` | `idempotent` | str: the display phone number, e.g. '15552014242'. | PrimitiveError with the Graph API error detail on non-2xx. |
| `whatsapp.get_media_url(media_id: 'str') -> 'dict[str, Any]'` | `idempotent` | dict: {url, mime_type, file_size, media_id}. | PrimitiveError with the Graph API error detail on non-2xx. |
| `whatsapp.send_document(file_path: 'str', to: 'str | None' = None, caption: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, to, filename, api}. | PrimitiveError with the Graph API error detail on non-2xx. If the response is lost, … |
| `whatsapp.send_text(text: 'str', to: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, to, api}. | PrimitiveError with the Graph API error detail on non-2xx. |
| `whatsapp.upload_document(file_path: 'str') -> 'str'` | `commutative-safe` | str: the media id. | PreconditionError for missing/unsupported files; PrimitiveError with the Graph API e… |

### `telegram`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `telegram.download_file(file_id: 'str', dest_dir: 'str | None' = None, filename: 'str | None' = None) -> 'dict[str, Any]'` | `idempotent` | dict: {path, filename, file_size, file_id}. | PreconditionError for empty file_id; PrimitiveError on network/download failure. |
| `telegram.get_me() -> 'str'` | `idempotent` | str: the bot username, e.g. 'MyFridayBot'. | PrimitiveError with the API detail on non-2xx or ok=false. |
| `telegram.poll_text_messages(limit: 'int' = 10) -> 'list[dict[str, Any]]'` | `idempotent` | list[dict]: messages with update_id, message_id, chat_id, date, from,… | PrimitiveError on API failure. |
| `telegram.poll_updates(limit: 'int' = 10) -> 'list[dict[str, Any]]'` | `idempotent` | list[dict]: messages with update_id, message_id, chat_id, date, text/… | PrimitiveError on API failure. |
| `telegram.send_document(file_path: 'str', to: 'str | None' = None, caption: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, chat_id, filename, api}. | PreconditionError for a missing file or empty to; PrimitiveError with the API detail… |
| `telegram.send_text(text: 'str', to: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, chat_id, api}. | PreconditionError for empty text or to; PrimitiveError with the API detail on failur… |

### `discord`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `discord.download_attachment(file_url: 'str', dest_dir: 'str | None' = None, filename: 'str | None' = None) -> 'dict[str, Any]'` | `idempotent` | dict: {path, filename, file_size}. | PreconditionError for empty URL; PrimitiveError on download failure. |
| `discord.get_me() -> 'str'` | `idempotent` | str: the bot username, e.g. 'FridayBot'. | PrimitiveError with the API detail on non-2xx. |
| `discord.poll_messages(limit: 'int' = 50) -> 'list[dict[str, Any]]'` | `idempotent` | list[dict]: messages with id, author, content, timestamp, attachments. | PrimitiveError on API failure. |
| `discord.send_file(file_path: 'str', channel_id: 'str | None' = None, caption: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, channel_id, filename, api}. | PreconditionError for a missing file or empty channel_id; PrimitiveError with the AP… |
| `discord.send_text(text: 'str', channel_id: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {message_id, channel_id, api}. | PreconditionError for empty text or channel_id; PrimitiveError with the API detail o… |

### `notify`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `notify.notify_send(title: 'str', body: 'str' = '', timeout_ms: 'int' = 5000) -> 'dict[str, Any]'` | `commutative-safe` | dict: {title, body, sent}. | PrimitiveError if the notifier is missing (install libnotify on POSIX) or exits non-… |

### `digestcheck`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `digestcheck.verify_attribution(digest: 'str', context: 'dict[str, Any]') -> 'str'` | `idempotent` | str: the digest text followed by an '## Attribution check' appendix (… | PreconditionError for an empty digest or empty/malformed context. Never raises on an… |

### `audio`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `audio.get_default_device(device_type: 'str' = 'sink') -> 'str'` | `idempotent` | str: the default device name ('' if none). | PrimitiveError if pactl fails; returns '' when no default is set. |
| `audio.get_output_volume() -> 'int | None'` | `idempotent` | int | None: 0-100 volume, or None. | PrimitiveError if pactl fails; returns None when no sink is found. |
| `audio.list_devices() -> 'list[dict[str, Any]]'` | `idempotent` | list[dict]: [{name, index, type}] - type is 'sink' or 'source'. | PrimitiveError if pactl fails or is absent. |
| `audio.speak(text: 'str', *, voice: 'str | None' = None) -> 'dict[str, Any]'` | `at-most-once` | dict: {engine, voice, duration_s, source, sink} | PrimitiveError on edge-tts rendering failure, empty text, or mpv launch failure. Do … |

### `calendar`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `calendar.add_event(summary: 'str', start: 'str', end: 'str') -> 'dict[str, str]'` | `at-most-once` | dict: {event_id, summary, start_time, end_time, status}. | PreconditionError for invalid parameters; PrimitiveError on auth/API failure. If the… |
| `calendar.delete_event(event_id: 'str') -> 'dict[str, str]'` | `commutative-safe` | dict: {event_id, status}. | PreconditionError for empty event_id; PrimitiveError on API failure. |
| `calendar.detect_conflicts(start: 'str', end: 'str') -> 'list[dict[str, str]]'` | `idempotent` | list[dict]: [{event_id, summary, start_time, end_time}] of conflictin… | PrimitiveError on auth/API failure. |
| `calendar.list_upcoming(days: 'int' = 7) -> 'list[dict[str, str]]'` | `idempotent` | list[dict]: [{event_id, summary, start_time, end_time, location, atte… | PrimitiveError on auth/API failure - DISTINCT from 'no upcoming events', which retur… |
| `calendar.update_event(event_id: 'str', summary: 'str | None' = None, start: 'str | None' = None, end: 'str | None' = None) -> 'dict[str, str]'` | `commutative-safe` | dict: {event_id, summary, start_time, end_time, status}. | PreconditionError for empty event_id; PrimitiveError on API failure. |

### `clipboard`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `clipboard.clear() -> 'None'` | `commutative-safe` | None | No-op on failure (best effort). |
| `clipboard.read_image() -> 'bytes | None'` | `idempotent` | bytes | None - image data if available, None if empty or not an image. | PrimitiveError when clipboard tool fails or returns error. |
| `clipboard.read_text() -> 'str'` | `idempotent` | str: the clipboard contents ('' when empty). | PrimitiveError when the clipboard tool is missing or fails to read - DISTINCT from a… |
| `clipboard.write_image(data: 'bytes') -> 'bytes'` | `commutative-safe` | bytes: the image data that was written. | PrimitiveError when clipboard tool fails. |
| `clipboard.write_text(text: 'str') -> 'str'` | `idempotent` | str: the text that was written to the clipboard (echoed back to the c… | PrimitiveError when the clipboard tool is missing or fails to write - DISTINCT from … |

### `http`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `http.delete(url: 'str', headers: 'dict[str, str] | None' = None, body: 'Any' = None, timeout_s: 'int' = 30) -> 'dict[str, Any]'` | `at-most-once` | dict: {status_code, headers, body, url, method}. | PreconditionError for empty url; PrimitiveError on network/timeout failure. |
| `http.get(url: 'str', headers: 'dict[str, str] | None' = None, timeout_s: 'int' = 30) -> 'dict[str, Any]'` | `idempotent` | dict: {status_code, headers, body, url, method}. | PreconditionError for empty url; PrimitiveError on network/timeout failure. |
| `http.patch(url: 'str', headers: 'dict[str, str] | None' = None, body: 'Any' = None, timeout_s: 'int' = 30) -> 'dict[str, Any]'` | `at-most-once` | dict: {status_code, headers, body, url, method}. | PreconditionError for empty url; PrimitiveError on network/timeout failure. |
| `http.post(url: 'str', headers: 'dict[str, str] | None' = None, body: 'Any' = None, timeout_s: 'int' = 30) -> 'dict[str, Any]'` | `at-most-once` | dict: {status_code, headers, body, url, method}. | PreconditionError for empty url; PrimitiveError on network/timeout failure. |
| `http.put(url: 'str', headers: 'dict[str, str] | None' = None, body: 'Any' = None, timeout_s: 'int' = 30) -> 'dict[str, Any]'` | `at-most-once` | dict: {status_code, headers, body, url, method}. | PreconditionError for empty url; PrimitiveError on network/timeout failure. |
| `http.request(url: 'str', method: 'str' = 'GET', headers: 'dict[str, str] | None' = None, body: 'Any' = None, timeout_s: 'int' = 30) -> 'dict[str, Any]'` | `idempotent` | dict: {status_code, headers, body, url, method}. | PreconditionError for empty url or invalid method; PrimitiveError on network/timeout… |

### `memory`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `memory.export_memories() -> 'dict[str, Any]'` | `idempotent` | dict: {data: str (JSON), count: int, exported_at: str}. | PrimitiveError on storage read failure. |
| `memory.forget(key: 'str', category: 'str | None' = None) -> 'dict[str, Any]'` | `commutative-safe` | dict: {key, found: bool}. | PreconditionError for empty key; PrimitiveError on storage failure. |
| `memory.import_memories(data: 'str') -> 'dict[str, Any]'` | `commutative-safe` | dict: {imported: int, updated: int, skipped: int}. | PreconditionError for empty/malformed data; PrimitiveError on storage failure. |
| `memory.list_categories() -> 'dict[str, Any]'` | `idempotent` | dict: {categories: {name: count}, total: int}. | PrimitiveError on storage read failure. |
| `memory.list_memories(category: 'str | None' = None, tags: 'list[str] | None' = None, offset: 'int' = 0, limit: 'int' = 20) -> 'dict[str, Any]'` | `idempotent` | dict: {entries: list[dict], total: int, offset: int, limit: int}. | PrimitiveError on storage read failure. |
| `memory.maintenance(ttl_days: 'int' = 90, min_access: 'int' = 5) -> 'dict[str, Any]'` | `idempotent` | dict: {archived: int, remaining: int, archived_keys: list[str]}. | PrimitiveError on storage failure. |
| `memory.reinforce(key: 'str', category: 'str | None' = None) -> 'dict[str, Any]'` | `commutative-safe` | dict: {key, found: bool, access_count: int}. | PreconditionError for empty key; PrimitiveError on storage failure. |
| `memory.retrieve(query: 'str', category: 'str | None' = None, tags: 'list[str] | None' = None, limit: 'int' = 5) -> 'list[dict[str, Any]]'` | `idempotent` | list[dict]: [{id, key, value, category, relevance, access_count}] ran… | PreconditionError for empty query; PrimitiveError on storage read failure. |
| `memory.store(key: 'str', value: 'str', category: 'str' = 'facts', tags: 'list[str] | None' = None) -> 'dict[str, str]'` | `commutative-safe` | dict: {id, key, category, status}. | PreconditionError for empty key/value or invalid category; PrimitiveError on storage… |
| `memory.summary() -> 'dict[str, Any]'` | `idempotent` | dict: {total, categories, oldest, newest, recent_keys: list[str]}. | PrimitiveError on storage read failure. |

### `screenshot`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `screenshot.capture(target: 'str' = 'full', output_path: 'str' = 'C:\\Users\\LAKSHA~1\\AppData\\Local\\Temp\\friday_screenshot.png') -> 'str'` | `idempotent` | str: the absolute path of the saved PNG. | PrimitiveError/PrimitiveTimeout when grim fails or times out; PreconditionError when… |

### `stark`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `stark.autonomous_plan(goal: 'str') -> 'dict[str, Any]'` | `idempotent` | dict: {goal, steps: list, estimated_cost: dict, confidence: float} | PreconditionError for invalid goals; PrimitiveError if planning fails. |
| `stark.health_check() -> 'dict[str, Any]'` | `idempotent` | dict: {status: str, layers: dict, resources: dict, recommendations: l… | PrimitiveError on unexpected failures; best-effort degrades gracefully. |
| `stark.predict_failures(log_path: 'str | None' = None, days: 'int' = 7) -> 'dict[str, Any]'` | `idempotent` | dict: {failure_likelihood: float, pattern: str, next_check: str} | PreconditionError for invalid arguments; returns 'unknown' on failure. |
| `stark.recognize_patterns(repos: 'list[str] | None' = None) -> 'dict[str, Any]'` | `idempotent` | dict: {patterns: list, suggestions: list, confidence: float} | PrimitiveError on unexpected failures; degrades gracefully if repos missing. |
| `stark.remediate(goal: 'str') -> 'dict[str, Any]'` | `idempotent` | dict: {steps: list, priority: str, estimated_time_s: int} | PreconditionError for invalid goals. |
| `stark.resource_governor(resources: 'dict[str, Any]') -> 'dict[str, Any]'` | `idempotent` | dict: {allocation: str, model: str, wait_for: str} | PreconditionError for invalid resources dict. |
| `stark.workflow_status(name: 'str') -> 'dict[str, Any]'` | `idempotent` | dict: {workflow_id, status, recommendations, next_step} | PrimitiveError if the orchestrator is unavailable. |

### `system`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `system.battery_info() -> 'dict[str, Any] | None'` | `idempotent` | dict or None: {percent, charging, time_remaining_s} or None if no bat… | PrimitiveError if fastfetch is missing or fails. |
| `system.cpu_info() -> 'dict[str, Any]'` | `idempotent` | dict: {model, cores_physical, cores_logical, frequency_mhz, temperatu… | PrimitiveError if fastfetch is missing or fails. |
| `system.disk_info() -> 'list[dict[str, Any]]'` | `idempotent` | list[dict]: [{mountpoint, filesystem, total_bytes, used_bytes, free_b… | PrimitiveError if fastfetch is missing or fails. |
| `system.memory_info() -> 'dict[str, Any]'` | `idempotent` | dict: {total_bytes, used_bytes, available_bytes, usage_percent, total… | PrimitiveError if fastfetch is missing or fails. |
| `system.system_summary() -> 'dict[str, Any]'` | `idempotent` | dict: {os, cpu, memory, disks, battery, uptime}. | PrimitiveError if fastfetch is missing or fails. |
| `system.uptime_info() -> 'dict[str, Any]'` | `idempotent` | dict: {uptime_seconds, uptime_human, boot_time}. | PrimitiveError if fastfetch is missing or fails. |

### `vision`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `vision.describe(image_path: 'str', instruction: 'str' = 'Describe what you see in this image in detail.', model: 'str | None' = None) -> 'str'` | `idempotent` | str: the LLM's description/analysis of the image. | PreconditionError for missing/empty files or empty instruction; PrimitiveError if th… |
| `vision.extract_text(image_path: 'str', language: 'str' = 'eng') -> 'dict[str, Any]'` | `idempotent` | dict: {text: str, confidence: float|None, language: str, word_count: … | PreconditionError for missing/empty/oversized files or missing tesseract; PrimitiveE… |

### `workflow`

| primitive | idempotency | returns | failure mode |
|---|---|---|---|
| `workflow.cancel_workflow(name: 'str') -> 'dict[str, Any]'` | `idempotent` | dict: {cancelled, workflow_id, status, error} | PrimitiveError if the workflow doesn't exist. |
| `workflow.compose_plans(plan1: 'dict[str, Any]', plan2: 'dict[str, Any]') -> 'dict[str, Any]'` | `idempotent` | dict: A valid plan dict representing the composition. | PrimitiveError if plans are invalid. |
| `workflow.get_workflow_status(name: 'str') -> 'dict[str, Any]'` | `idempotent` | dict: workflow state including status, duration, and results. | PrimitiveError if the workflow doesn't exist. |
| `workflow.list_workflows() -> 'list[dict[str, Any]]'` | `idempotent` | list[dict]: List of workflow states. | None (returns empty list on error). |
| `workflow.parallel_run(plans: 'list[dict[str, Any]]') -> 'dict[str, Any]'` | `idempotent` | dict: A plan dict that orchestrates parallel execution. | PrimitiveError if any plan is invalid. |
| `workflow.run_workflow(goals: 'list[str]', *, name: 'str | None' = None, timeout_s: 'float' = 3600.0) -> 'dict[str, Any]'` | `at-most-once` | dict: {success, duration_s, step_results, error} | PrimitiveError when planning or execution fails entirely. |

## L2 verification checks (39)

Every check is side-effect-free: it reads current real-world state and returns
True/False (or a scalar) against a specific claim. A step is VERIFIED only when
its check agrees with the world - absence of an exception is never enough.

| check | claim |
|---|---|
| `checks.active_window_class` | Claim: 'the focused window's class is X' |
| `checks.audio_output_ready` | Claim: 'the default audio sink is configured and the master volume is a sane level to hear a Friday utterance' |
| `checks.audio_utterance_playing` | Claim: 'media is currently playing and its title references the utterance a speak() step just produced' |
| `checks.browser_has_text` | Claim: 'the open page's visible text contains X' |
| `checks.browser_input_has_value` | Claim: 'the field resolved by `what` currently contains exactly the text `value`' |
| `checks.diff_is_clean` | Claim: 'the repository diff is clean (no staged or unstaged changes)' |
| `checks.file_exists` | Claim: 'a file exists at path' |
| `checks.file_exists_and_contents` | Claim: 'file exists and has expected contents' |
| `checks.file_is_copied_to` | Claim: 'file was successfully copied to dest_dir' |
| `checks.file_is_deleted` | Claim: 'file was successfully deleted (no longer exists at path)' |
| `checks.file_is_moved_from` | Claim: 'file was successfully moved from path to dest_dir' |
| `checks.file_size_equals` | Claim: 'a file exists at path and has exactly expected_bytes' |
| `checks.gmail_message_matches` | Claim: 'the fetched message's From header contains the expected sender substring' |
| `checks.gmail_unread_exists` | Claim: 'there is at least one unread message from this sender' |
| `checks.http_status_code` | Claim: 'the HTTP response status is N' |
| `checks.http_status_ok` | Claim: 'the HTTP response status is 2xx' |
| `checks.list_nonempty` | Claim: 'a step result is a non-empty list' |
| `checks.media_playing` | Claim: 'media is currently playing' |
| `checks.memory_age_days` | Claim: 'the memory with this key is at most N days old' |
| `checks.memory_has_key` | Claim: 'a memory exists with this key (optionally in this category)' |
| `checks.memory_retrieval_ok` | Claim: 'a memory retrieval for this query returns results' |
| `checks.memory_store_status` | Claim: 'the last memory store operation had this status' |
| `checks.message_sent` | Claim: 'the messaging platform acknowledged a message with this id' |
| `checks.repo_branch` | Claim: 'the repository is on the expected branch' |
| `checks.repo_has_staged` | Claim: 'the repository has staged changes' |
| `checks.repo_has_uncommitted` | Claim: 'the git repository has uncommitted changes' |
| `checks.repo_is_clean` | Claim: 'the git repository has no uncommitted changes' |
| `checks.text_nonempty` | Claim: 'a step result is a non-empty string' |
| `checks.vision_text_contains` | Claim: 'the image contains the specified text' |
| `checks.vision_text_nonempty` | Claim: 'extracting text from this image produces non-empty output' |
| `checks.vision_word_count_above` | Claim: 'the image contains at least N words' |
| `checks.whatsapp_identity_ok` | Claim: 'the whatsapp credentials resolve to a real account' |
| `checks.whatsapp_media_downloaded` | Claim: 'a file was downloaded to path and is non-empty' |
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
| `ambient-gap-probe-clipboard` | false | time 11:00 [daily] | false | notify.notify_send |
| `ambient-gap-probe-email-send` | false | time 11:05 [daily] | false | notify.notify_send |
| `ambient-gap-probe-file-write` | false | time 00:05 [daily] | false | notify.notify_send |
| `discord-inbound` | false | time 12:05 [mon,tue,wed,thu,fri,sat,sun] | false | discord.poll_messages, discord.download_attachment |
| `discord-inbound-text` | true | discord-text - [daily] | true | - |
| `memory-maintenance` | true | time 03:00 [sun] | false | memory.maintenance |
| `morning-calendar-summary` | true | time 08:00 [daily] | true | calendar.list_upcoming |
| `morning-clipboard-digest` | true | time 08:05 [daily] | true | calendar.list_upcoming, dev.digest, clipboard.write_text |
| `morning-email-digest` | false | time 09:15 [mon,tue,wed,thu,fri] | true | gmail.list_unread, gmail.get_message, gmail.summarize, gmai… |
| `morning-gmail-summary` | true | time 09:00 [mon,tue,wed,thu,fri] | true | gmail.list_unread, gmail.get_message, gmail.summarize |
| `new-download-alert` | true | file - [daily] | true | files.find_newest, whatsapp.send_document |
| `screenshot-digest` | true | time 12:00 [mon,tue,wed,thu,fri] | true | screenshot.capture, vision.describe, notify.notify_send |
| `sunday-digest-reminder` | true | time 10:05 [sun] | false | notify.notify_send |
| `telegram-inbound` | true | telegram-media - [daily] | true | telegram.poll_updates, telegram.download_file |
| `telegram-inbound-text` | true | telegram-text - [daily] | true | - |
| `telegram-media-download` | true | telegram-media - [daily] | true | - |
| `weekly-cross-project-digest` | true | time 10:00 [sun] | true | dev.digest, digestcheck.verify_attribution, files.find_rece… |
| `weekly-email-digest` | false | time 10:30 [sun] | true | git.log, files.find_recent_doc, files.read_text, dev.digest… |
| `whatsapp-media-download` | true | whatsapp-media - [daily] | true | - |

## Capability-gap loop (self-improvement)

A refused/unknown primitive step becomes a structured `capability_gap` record;
triage LLM-drafts a proposal (contract + impl + test); the automated gate (AST
checks + sandboxed test run + build-verify where applicable) filters it before
a human signature; on approval the primitive registers into L1 and the planner
auto-discovers it - the originally-refused goal then re-runs and must pass.

Gate-registered primitives (13):

- `calendar.add_event`
- `calendar.list_upcoming`
- `clipboard.read_text`
- `clipboard.write_text`
- `files.find_file_exact`
- `files.find_newest`
- `files.write_text`
- `git.status`
- `gmail.send_document`
- `media.get_playing_title`
- `media.get_volume`
- `media.seek`
- `screenshot.capture`

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

