# PORTABILITY - would Friday work the same on Windows?

Status date: 2026-08-13.

**Status: REFERENCE / ASPIRATIONAL.** This document analyzes what a Windows
port would take. It is not a commitment to port, and no porting work is
scheduled. It exists so the question "should I rebuild this on a different
OS?" is answered with evidence whenever it comes up again - and so the
answer does not have to be re-derived from scratch each time.

## The one-line verdict

**The brain and the network arms port cleanly; the desktop arms mostly do
not.** Roughly 60-70% of the code ships to Windows unchanged. Five places
are OS-tied, and only ONE needs a real rewrite (`window`). The layers
under analysis: L4 planner, L3 executor, L2 checks, L1 primitives, the
watcher, the self-improvement loop (capability-gap), the lessons loop,
goal proposals, and the Phase C digest.

## Portable as-is (zero code changes)

| Piece | Why |
|---|---|
| L4 planner, L3 executor, L2 checks (pure + HTTP ones), contracts, errors, observability | Pure Python - the plan -> execute -> verify -> log pipeline has no OS calls. |
| `files.*` (find_file, find_file_exact, find_recent_doc, read_text) | Pure `pathlib`/stdlib. |
| `git.log` | Subprocess `git` - Git for Windows exists. |
| `digestcheck.verify_attribution` | Pure string logic. |
| `whatsapp` / `telegram` / `discord` / `gmail` (14 primitives) | Pure HTTP via `requests`. |
| `dev.*` (run, run_shell, digest) | Subprocess `claude -p`; the Claude Code CLI is officially supported on Windows (npm). |
| The entire self-improvement loop (capability_gaps, gap_triage, automated_gate AST checks, register_proposal, goal_proposals, lessons) | Pure Python + the claude CLI. |
| The watcher loop logic | Pure Python; only its deployment is Linux (below). |
| Dependencies | `requests` + `playwright` are both cross-platform; requires Python >= 3.11. |

## Port-ready with a small backend swap (one function/module each)

| Piece | Linux today | Windows shape | Effort |
|---|---|---|---|
| `secrets.get_credentials` | `pass show` (GPG) | env-var / Windows Credential Manager backend. Gmail already documents env overrides (`GMAIL_CLIENT_ID`/`SECRET`/`REFRESH_TOKEN`); extend that pattern to every service. This is the choke point all messaging + `browser.login` read through. | S |
| `notify.notify_send` | `notify-send` (libnotify) | PowerShell toast (BurntToast) or `plyer`. One function. | S |
| `browser.*` | Playwright (cross-platform) + a `pgrep`/`SIGTERM` orphan sweep | Keep Playwright (`playwright install chromium` on the new machine); replace the sweep with `tasklist`/psutil or drop it. `--ozone-platform-hint=auto` is harmless. | S |
| `media.*` | mpv over a Unix socket at `/tmp/friday_mpv.sock`, `AF_UNIX`, `pgrep`, `fuser`, `SIGTERM/SIGKILL`, `start_new_session` | mpv named-pipe IPC; `tasklist`-based process sweep; no `start_new_session` (Windows has no session semantics). | M |
| Deployment | systemd user service (`deploy/`) | Windows Task Scheduler or NSSM. The watcher code is untouched. | S |
| `automated_gate` sandbox env isolation | temp `HOME` + POSIX PATH filtering | Windows subprocesses read `USERPROFILE`, PATH separator is `;` - the "draft cannot find credentials" guarantee needs a Windows-shaped equivalent. The AST checks are pure and portable. | M |

## Needs a real rewrite (exactly one)

| Piece | Linux today | Windows shape |
|---|---|---|
| `window.*` (8 primitives: list_clients, get_active_window, open_app, close_window, close_all, focus_window, move_to_workspace, shutdown) | `hyprctl` / Hyprland IPC (`HYPRLAND_INSTANCE_SIGNATURE`) | win32 API (pywin32) or pywinauto. The CONTRACT surface, idempotency classes, protected-window refusal, and all 7 window L2 checks survive untouched - the backend is reimplemented, not the design. One semantic mismatch: "workspaces" map to Windows virtual desktops (`IVirtualDesktopManager`) rather than 1:1. |

## Config + tests

- `config/watcher.json` and `config/planner_facts.json` hardcode
  `/home/lakshay/Projects/*` (digest repo paths, facts file paths) - data,
  not code; edit per machine.
- The hermetic unit suite (see gates/TESTS_PROOF.md for the current count)
  would mostly pass on Windows; a handful of tests assert Linux error text
  (e.g. "`sudo pacman -S libnotify`") - cosmetic, not structural.

## Ordered port checklist (if ever pursued)

1. **`secrets` backend** (env / credential-manager) - unblocks gmail,
   whatsapp, telegram, discord, browser.login.
2. **`notify` backend** (toast) - restores the watcher's feedback channel.
3. **`browser` sweep cleanup** - keep Playwright, port the orphan sweep.
4. **`media` IPC + process sweep** - mpv named pipe + tasklist.
5. **`automated_gate` sandbox env** - Windows-shaped HOME/PATH isolation.
6. **Deployment** - Task Scheduler / NSSM in place of systemd.
7. **`window` backend** - the big one, last: win32 implementation behind
   the existing contracts, then re-run the window L2 checks + gates.

After 1-6, everything except desktop window control works identically.
After 7, the full surface is back. Nothing on this list is scheduled.
