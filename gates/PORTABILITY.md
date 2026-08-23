# PORTABILITY - would Friday work the same on Windows?

Status date: 2026-08-18.

**Status: PORTED (2026-08-18).** The Windows port planned in this document
is now implemented and verified: the full hermetic suite, ruff lint, and
strict mypy all pass on Windows (see gates/TESTS_PROOF.md for the current
count). This document now records *how* the port was done so the Linux
box can be migrated or the Windows shape maintained.

## The one-line verdict

**The brain and the network arms port cleanly; the desktop arms needed a
backend swap.** The layers (L4 planner, L3 executor, L2 checks, L1
primitives, the watcher, the self-improvement loop) are pure Python and
shipped unchanged. Five OS-tied places were swapped behind the same
contracts; the design never changed - only the backend did.

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
| The watcher loop logic | Pure Python; only its deployment differs (below). |
| Dependencies | `requests` + `playwright` are both cross-platform; requires Python >= 3.11. |

## Ported 2026-08-18 (backend swap behind the same contract)

| Piece | Linux backend | Windows backend now shipped | Notes |
|---|---|---|---|
| `secrets.get_credentials` | `pass show` (GPG) | env-var pair `FRIDAY_<SERVICE>_USER`/`FRIDAY_<SERVICE>_PASS` (both-or-none enforced); `pass` still tried first on POSIX | Choke point all messaging + `browser.login` read through. |
| `notify.notify_send` | `notify-send` (libnotify) | PowerShell toast (`[Windows.UI.Notifications]`) - no BurntToast dependency | Fire-and-forget like notify-send. |
| `browser.*` orphan sweep | `pgrep`/`SIGTERM` | `tasklist` + `taskkill` (no psutil) | Playwright itself is cross-platform. |
| `automated_gate` sandbox env | temp `HOME` + POSIX PATH filtering | Windows-shaped: `USERPROFILE`/`HOMEDRIVE`/`HOMEPATH` isolation + `;`-separated PATH filter | The "draft cannot find credentials" guarantee is preserved. |
| Deployment | systemd user service (`deploy/friday-watcher.service`) | Task Scheduler (`deploy/install-windows.ps1`) | RUNBOOK has the 1:1 day-2 ops table. |
| `window.*` (8 primitives) | `hyprctl` / Hyprland IPC | win32 API via stdlib `ctypes` (EnumWindows/GetWindowTextW/SetForegroundWindow/ShowWindow) - live-verified against the real desktop | No pywin32 dependency; the CONTRACT surface, idempotency classes, protected-window refusal, and all 7 window L2 checks survive untouched. One semantic mismatch: workspaces map to Windows virtual desktops rather than 1:1; `move_to_workspace`/`shutdown` refuse cleanly on Windows. |

## Config + tests

- `config/watcher.json` and `config/planner_facts.json` hardcode
  `/home/lakshay/Projects/*` (digest repo paths, facts file paths) - data,
  not code; edit per machine.
- The hermetic unit suite runs green on Windows (see gates/TESTS_PROOF.md
  for the current count). Porting the suite surfaced two real latent
  bugs that only Windows exposed: `signal.SIGKILL`/`socket.AF_UNIX`
  (now `getattr`-guarded in `media.py`) and the
  `time.time_ns()`-based ids in `record_gap`/`record_lesson_event`
  (collide on coarse Windows timers; now uuid-suffixed).

## What would still differ on Linux after this port

Nothing structural - the Linux backends (Hyprland, notify-send, pass,
systemd) are still the code path when running on POSIX; the port added
`sys.platform` dispatch branches, it did not replace the Linux code.
