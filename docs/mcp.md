# Friday MCP Server — client setup

Friday ships a Model Context Protocol (MCP) tool server
(`friday/mcp_server.py`, run via `python -m friday.mcp_server` or the
`friday-mcp` console script). It exposes every contract-registered,
executor-accessible primitive (currently **57 tools**) as MCP tools over
stdio, so any MCP client — Claude Desktop, Claude Code, Cursor — can
drive the desktop through the **same verified boundary the executor
uses**: each tool call is resolved through `_resolve_primitive`
(registered contract + not in `EXECUTOR_BLOCKED`), and L0 logging is
automatic via the existing `@contract -> @observe` wrap.

What a client sees (`tools/list`):

```
browser__click, browser__new_page, browser__read_page,
calendar__list_events, clipboard__read_text, dev__run,
files__find_file, files__read_text, gmail__list_unread,
media__get_playing_title, notify__notify_send, screenshot__capture,
telegram__send_text, whatsapp__send_text, window__list_clients,
window__open_app, ... (57 total)
```

The destructive `window.shutdown` is **never advertised and refused if
called** — the same `EXECUTOR_BLOCKED` gate as a plan step.

---

## 0. Prerequisites (all clients)

The MCP server is a child process of the client, so it needs:

1. **The repo installed** (`pip install -e .` — creates the `friday-mcp`
   console script) and **Playwright browsers** if you will call
   `browser.*` tools:
   ```bash
   python -m venv .venv
   .venv/Scripts/pip install -e .        # Windows
   .venv/bin/pip install -e .            # macOS / Linux
   .venv/Scripts/playwright install chromium   # only if using browser.*
   ```

2. **A known-good command line.** The most robust form is the venv
   Python directly (no PATH dependence — see the Windows note below):

   - Windows: `C:\Users\<you>\...\Friday V2\.venv\Scripts\python.exe -m friday.mcp_server`
   - macOS/Linux: `/path/to/Friday V2/.venv/bin/python -m friday.mcp_server`

   Verify it speaks MCP before wiring it into a client:

   ```bash
   printf '%s\n' \
     '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}' \
     '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' \
   | .venv/Scripts/python.exe -m friday.mcp_server
   ```

   You should see two JSON-RPC responses: an `initialize` result and a
   `tools/list` result with 57 tools.

3. **Credentials in the server's environment.** The server inherits the
   client's environment, not your shell's. Tools that need secrets
   (`telegram.*`, `whatsapp.*`, `gmail.*`, ...) read them from env vars
   (see `docs/user-guide.md` → Configuration). On Windows, GUI clients do
   not see shell-session exports — set them at the **user** level so the
   child process inherits them:

   ```powershell
   setx TELEGRAM_BOT_TOKEN "..."
   setx FRIDAY_LOG_FILE "C:\Users\<you>\...\Friday V2\var\logs\friday.jsonl"
   ```

   (`setx` applies to processes started *after* it runs — restart the
   client afterwards.)

---

## 1. Claude Desktop

Config file (JSON):

- Windows: `%APPDATA%\Claude\claude_desktop_config.json`
  (`C:\Users\<you>\AppData\Roaming\Claude\claude_desktop_config.json`)
- macOS: `~/Library/Application Support/Claude/claude_desktop_config.json`

Add a `mcpServers` entry:

```json
{
  "mcpServers": {
    "friday": {
      "command": "C:\\Users\\<you>\\Desktop\\Projects\\Friday V2\\.venv\\Scripts\\python.exe",
      "args": ["-m", "friday.mcp_server"]
    }
  }
}
```

**Windows note:** the JSON `command` must be the **absolute path** — GUI
apps don't inherit your shell PATH, so a bare `friday-mcp` or
`python` will not resolve. Backslashes in JSON must be doubled, or use
forward slashes (`"C:/Users/<you>/Desktop/Projects/Friday V2/.venv/Scripts/python.exe"`).

Then **fully quit and restart Claude Desktop**. A hammer icon appears in
the composer — click it to see the connected `friday` tools.

---

## 2. Claude Code (CLI)

Two scopes; the project scope is shareable via git:

- **Project scope** — `.mcp.json` at the repo root (commit it if you
  want the team to get it), or
- **User scope** — `~/.claude.json` under the top-level `mcpServers`
  key.

`.mcp.json`:

```json
{
  "mcpServers": {
    "friday": {
      "command": "/path/to/Friday V2/.venv/bin/python",
      "args": ["-m", "friday.mcp_server"]
    }
  }
}
```

Or add it with the CLI (writes the config for you):

```bash
claude mcp add --scope project friday -- \
  /path/to/Friday V2/.venv/bin/python -m friday.mcp_server
```

Check it connected: `claude mcp list` (shows `friday ... connected`).
The tools appear in `/mcp` inside Claude Code.

---

## 3. Cursor

Config file (JSON):

- **Project scope** — `.cursor/mcp.json` at the repo root, or
- **Global scope** — `~/.cursor/mcp.json` (Windows:
  `C:\Users\<you>\.cursor\mcp.json`)

```json
{
  "mcpServers": {
    "friday": {
      "command": "C:\\Users\\<you>\\Desktop\\Projects\\Friday V2\\.venv\\Scripts\\python.exe",
      "args": ["-m", "friday.mcp_server"]
    }
  }
}
```

Then enable it: Cursor Settings → **MCP** → **Add new MCP server** →
select the config (or **Refresh** if you edited an existing file), and
confirm `friday` shows **Enabled** / **Connected**. Tools are available
to the agent in chat and agents mode.

---

## 4. Verifying it works

Ask the client to run a harmless read-only tool, e.g.:

> List the open windows using the friday MCP server.

That calls `window__list_clients` (idempotent, read-only — safe). Every
call lands in the L0 structured log (`var/logs/friday.jsonl` by default)
with the primitive name, args, result status and duration — the same log
the watcher and planner write to, so MCP traffic is auditable alongside
everything else.

## 5. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| Client shows the server but **no tools** | The server failed at startup. Run the exact `command` + `args` from the config in a terminal by hand and check for a traceback. |
| `friday` shows **Disconnected** / **Error** | The child process died. Check the repo path in `command` (spaces are fine in JSON, but the whole path must exist) and that `pip install -e .` was run in that venv. |
| Tools connect but calls fail with `primitive module ... cannot be imported` | The server process is a different Python than the one with `friday` installed — use the venv's python explicitly (prerequisite 2). |
| `window__open_app` or `browser.*` fail | Missing desktop prerequisite (Playwright browsers not installed; or the tool is a no-op for this OS backend). See `gates/PORTABILITY.md` for what each backend supports. |
| Credential tools (`telegram.*`, `gmail.*`, ...) fail with auth errors | The env vars aren't visible to the child process — GUI clients don't inherit shell exports. Set them at user level (`setx` on Windows) and restart the client. |
| Logs not where you expect | Set `FRIDAY_LOG_FILE` in the client-visible environment (prerequisite 3). |

## 6. Security notes

- The MCP surface is exactly the **executor's** surface: only
  contract-registered primitives, with `window.shutdown` blocked
  outright. The L0 log records every call.
- The tools are still **real desktop automation** — `window.close_window`
  closes windows, `media.play_for` plays media. Granting an MCP client
  these tools grants it desktop control, so only connect clients you
  trust, and prefer read-only tools (`window__list_clients`,
  `files__read_text`, `gmail__list_unread`, `clipboard__read_text`) for
  anything unattended.
- `config/credentials.json` is gitignored and is **not** read by the
  server (runtime creds come from env vars / `pass`); never commit it.
