# Friday V8 - User Guide

## Quick Start

### Installation

```bash
# Clone and setup
git clone https://github.com/lakshay/Friday-V2.git
cd Friday-V2

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux
# or
.\.venv\Scripts\activate   # Windows

# Install dependencies
pip install -e ".[dev,test]"

# Install Playwright browsers
playwright install chromium
```

### Configuration

#### Credentials

Friday needs credentials for various services. Each service has its own setup:

**Gmail / Calendar:**
See `gates/GMAIL_SETUP.md` for the Gmail OAuth setup. The one-time consent
scripts take the downloaded Google OAuth client file as input
(`config/credentials.json` - gitignored, never commit it); the refresh
tokens they mint are stored in `pass` at `friday/gmail` / `friday/calendar`
(or `GMAIL_*` / `CALENDAR_*` env vars), which is what the primitives read
at runtime. A missing credential path is a PrimitiveError, never a silent
empty result.

**Messaging (WhatsApp, Telegram, Discord):**
Set environment variables:
- `WHATSAPP_ACCESS_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_DEFAULT_PHONE`
- `TELEGRAM_BOT_TOKEN`
- `DISCORD_BOT_TOKEN`, `DISCORD_CHANNEL_ID`

### Running a Goal

```python
from friday.l4.planner import plan
from friday.l3.executor import run_plan

goal = "pause whatever's playing, then close every window except my terminal"
result = run_plan(plan(goal, run_id="demo"))
print(result.status)  # COMPLETED or ABORTED
```

### MCP Server (other agents / AI clients)

Friday's primitives are exposed as Model Context Protocol tools (57 of
them) over stdio, so Claude Desktop, Claude Code, or Cursor can drive
the desktop through the same verified executor boundary. Run it with:

```bash
python -m friday.mcp_server          # or the friday-mcp console script
```

See `docs/mcp.md` for per-client config snippets (Claude Desktop,
Claude Code, Cursor), verification steps, troubleshooting, and security
notes. A copy-paste sample config lives at `config/mcp.example.json`.

### The Watch Loop

The watch loop runs in the background, automating scheduled tasks.

**Start the daemon:**
```bash
# Linux (systemd user service)
./.venv/bin/python -m friday.watcher --poll 30  # daemon mode

# Or as a cron job (every 2 minutes)
crontab -e
# */2 * * * * /path/to/.venv/bin/python -m friday.watcher --once
```

**Configuration:** Goals are defined in `config/watcher.json`. Each trigger specifies:
- `goal`: What to execute
- `schedule`: When to fire (time/file triggers)
- `allow`: Which primitives are permitted
- `enabled`: Whether to run

---

## Architecture Overview

Friday's five layers work together:

```
L4 Planning   →  L3 Execution  →  L2 Verification  →  L1 Primitives  →  L0 Observability
(LLM: goal→plan)   (deterministic run)   (read-only checks)   (actions)   (structured logs)
```

### Layer 4 - Planning

Converts natural language goals into structured JSON plans that L3 can execute.

```json
{
  "goal": "open firefox",
  "steps": [
    {
      "primitive": "window.open_app",
      "args": {"command": "firefox"},
      "verify": {
        "check": "checks.window_has_class",
        "args": {"cls": "firefox"},
        "expect": true
      }
    }
  ]
}
```

### Layer 3 - Execution

Runs plans deterministically:
1. PENDING → RUNNING
2. RUNNING → VERIFIED (success) or FAILED
3. FAILED → RETRY (bounded, by contract) → RUNNING
4. RETRY_EXHAUSTED → ABORT

### Layer 2 - Verification

Read-only checks prove each step succeeded:
- Window: `window_has_class`, `window_client_count`, `window_focused`
- Media: `media_playing`
- Browser: `browser_has_text`, `browser_input_has_value`
- Files: `file_exists`
- Messaging: `message_sent`, `whatsapp_identity_ok`

### Layer 1 - Primitives

Domain-specific actions:
- `window.*` - Window management (open, close, focus, move to workspace)
- `media.*` - Audio control (play, pause, stop, volume)
- `browser.*` - DOM automation via Playwright
- `files.*` - File discovery and reading
- `git.*` - Repository history queries
- `gmail.*` - Email operations
- `calendar.*` - Calendar events
- `clipboard.*` - System clipboard
- `screenshot.*` - Capture screenshots

### Layer 0 - Observability

Every operation emits a structured JSON log line for auditing and debugging.

---

## Safety Features

- **Protected Windows**: Terminal windows are never closed automatically
- **Blocked Primitives**: Destructive operations (`window.shutdown`) are mechanically blocked
- **Dangerous Gate**: Shell/dangerous LLM operations require `FRIDAY_ALLOW_DANGEROUS=1`
- **Result Redaction**: Secrets and sensitive data never in logs
- **Allowlists**: Triggers limited to safe primitives

---

## Common Goals

### Browser Tasks
```
"open example.com and search for python"
"login to github and open the latest issue"
```

### Window Management
```
"close every window except my terminals"
"move firefox to workspace 2"
```

### Media Control
```
"pause media playback"
"set volume to 50%"
```

### File Operations
```
"find the receipt pdf and send it to my phone"
"read the last todo item from my notes"
```

### Messaging
```
"send 'meeting at 3pm' to my whatsapp contacts"
"report the current date to my team on telegram"
```

---

## Development

### Running Tests

```bash
# Run all tests
python -m pytest -v

# Run with coverage
python -m pytest --cov=friday --cov-report=html
```

---

## Troubleshooting

### Authentication Errors

If you get credential errors, ensure:
1. The runtime credentials exist: `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` /
   `GMAIL_REFRESH_TOKEN` env vars, or `pass` entries at `friday/gmail` and
   `friday/calendar` (minted by the OAuth setup scripts)
2. API services are enabled in your developer console
3. OAuth consent screens are properly configured

### Window Operations Fail

- Ensure you're on a Wayland (Linux) or Windows 11 24H2+ (Windows) session
- Check that `FRIDAY_PROTECTED_CLASSES` doesn't block your target

### LLM Planning Fails

- Check that you have access to the configured `MODEL_ALIAS`
- Review `var/logs/friday.jsonl` for detailed error messages
- Approved lessons in `config/lessons.json` can help prevent recurring failures