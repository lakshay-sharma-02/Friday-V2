# Friday Playbook — Phone + PC as Stark Industries

> "Friday, what's my day look like?" — from your phone, while the PC does the work.

Friday's brain and hands live on your PC (always-on daemon, files, browser,
calendar, git, media). Your phone is the remote control, the face, and the
missing sensor. This playbook maps the Jarvis moments to concrete commands,
and documents the bridge that lets the phone feed state back.

## The mental model

| Role | Where it runs | What it does |
|---|---|---|
| Brain + hands | PC daemon | plans, executes, verifies, remembers, learns |
| Remote control | phone chat (Telegram/Discord/WhatsApp) | you talk, Friday acts on the PC |
| Sensor | phone companion | presence, battery, activity, DND → planner context |
| Delivery | phone notifications | proactive pings land where you actually are |

## Talking to Friday from chat

Every inbound text message is routed before any goal is planned:

| You type | What happens |
|---|---|
| `/friday help` | the command list, zero LLM cost |
| `/friday status` | adapter/channel/memory health + current phone telemetry |
| `/friday adapters` | per-platform capability list (live registry) |
| `/friday memory` | memory store summary + recent episodic entries |
| `/friday phone` | last reported phone state |
| `/goal <anything>` | full pipeline: planner → executor → verified → natural reply |
| plain chatter | consumed silently, no reply, never re-queued |

The goal prefix is `/goal` by default; set `FRIDAY_COMMAND_PREFIX` (e.g.
`/do`) to change it. Set it to empty to make **every** message a goal.

Telegram and Discord text watcher triggers both route through this layer
(see `config/watcher_mcu.json` — flip `enabled: true`). Replies go back to
the chat you wrote from. Non-goal messages are consumed so they never
re-trigger.

## Jarvis moments → what actually works today

| Stark moment | How it's done |
|---|---|
| "What's my day look like?" | watcher time triggers: morning gmail + calendar summaries pushed to you |
| "Send this to my phone" | file triggers → send to Telegram/Discord/WhatsApp |
| "When that download finishes, ship it" | file-trigger watcher with persisted seen-state (survives restarts) |
| "What's on my screen?" | screenshot + vision describe → answer back over chat |
| "What changed across my projects?" | `dev.digest` cross-project digest |
| "Did you actually do it?" | every step verified against real state or the run fails loudly |
| "Do it and get better" | every outcome recorded → lessons + goal patterns |
| "Check on me later" | proactive engine: patterns → suggestions → channel delivery |

## Phone telemetry bridge (what's new)

The PC cannot see the phone half of your world. A small companion (Termux,
Tasker, HTTP Shortcuts, or any HTTP client) POSTs snapshots to the API.
Ready-made scripts + step-by-step pairing live in `tools/phone_bridge/`.
Friday stores only allowlisted presence fields — no secrets:

```json
{
  "device": "Pixel 8",
  "battery": 84,
  "charging": true,
  "activity": "walking",
  "location": "office",
  "do_not_disturb": false,
  "wifi": "home-5g",
  "note": "in a meeting until 3",
  "sms_unread": 2,
  "sms_latest": "Boss : did you send the report?",
  "missed_calls": 1,
  "notifications": 5,
  "notifications_top": "com.whatsapp"
}
```

The **SMS/call/notification sensors** (`sms_unread`, `sms_latest`,
`missed_calls`, `notifications`, `notifications_top`) come from the phone
bridge: `tools/phone_bridge/termux_report.sh` reads SMS + notifications via
Termux:API and POSTs them on a schedule; Tasker can additionally report
missed calls from its Call Log source.

- `POST /v1/phone` — ingest a snapshot (merged, `last_seen` refreshed)
- `GET /v1/phone` — current state + whether a phone has ever reported
- Auth: same `FRIDAY_API_TOKEN` bearer gate as every `/v1/*` endpoint

Reported state shows up in:
- `/friday phone` and `/friday status` chat replies
- the planner's context block (`PHONE: ...` section), so goals can react to
  *you* — "you're away from your desk", "2 unread SMS from boss", or
  "quiet hours" instead of just the PC

Example bridge call:

```bash
curl -X POST http://127.0.0.1:8080/v1/phone \
  -H "Authorization: Bearer $FRIDAY_API_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"device":"Pixel 8","battery":84,"activity":"walking","sms_unread":2,"notifications":5}'
```

## Running it

```bash
# daemon with time/file/inbound triggers (edit config/watcher_mcu.json)
python -m friday_mcu watcher

# one-shot API + WebSocket server (loopback default; token for remote)
FRIDAY_API_TOKEN=$(openssl rand -hex 24) python -m friday_mcu api

# interactive goal REPL
python -m friday_mcu
```

For phone-over-internet control, run the API on Tailscale (`FRIDAY_API_HOST`
= your Tailscale IP + `FRIDAY_API_TOKEN` set) and point the companion at it.

## Next phases on the roadmap

1. **Android companion app** — a tiny app that reports battery/activity/DND
   and shows proactive cards; until then, `tools/phone_bridge/` (Termux /
   Tasker / HTTP Shortcuts) is the pairing path.
2. **Two-way voice** — voice note → transcription → `/goal`; or Assistant
   shortcut → goal API.
3. **Reminders with context** — "when I'm back at my desk, tell me X" needs
   phone presence + location to gate the trigger.
4. **Recipient learning** — proactive suggestions that learn which channel
   and time you actually act on.
5. **Proactive gating on phone state** — don't buzz during DND or a meeting
   (already reported via `do_not_disturb`/`activity`).
