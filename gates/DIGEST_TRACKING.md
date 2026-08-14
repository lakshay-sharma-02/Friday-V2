# Digest tracking — the only signal that matters for Phase C

Every Sunday the `weekly-cross-project-digest` trigger runs and delivers a
digest to the desktop (recorded in `var/logs/tasks.jsonl` as
`watch:weekly-cross-project-digest`; full text in the regenerated
`gates/PHASE_C_V2_PROOF.md`). This file is the HUMAN verdict log for the
one question the mechanical checks cannot answer: **"would I act on this?"**

The mechanical gates (specific-vs-generic, targets-owned, attribution)
prove a suggestion names real things in the right repos — they cannot
prove the transfer makes sense. Only this table can. Add ONE line per
suggestion after each weekly run:

| verdict | meaning |
|---------|---------|
| `acted` | you did something because of it |
| `ignored` | you read it and consciously did nothing |
| `wrong repo` | v1 failure mode — target isn't yours |
| `wrong mechanism` | mechanism exists in the source repo, but the transfer doesn't fit the target (v2 S2 `sync.sh`; v2.2 S1) |
| `wrong layer` | proposed mechanism can't exist at the target's layer (v2.2 S2 — a host systemd service "monitoring" a kernel that hasn't booted yet) |

| week | run date | suggestion | verdict | one-line note |
|------|----------|-----------|---------|---------------|
| 0 | 2026-08-11 | Friday per-trigger allowlist → Vivaha admin dashboard | wrong mechanism | grounded (roadmap Q4 names service-role key + custom RBAC) but wrong shape — the mechanism exists in Friday, the transfer doesn't fit Vivaha; the roadmap already specifies the better mechanism |
| 0 | 2026-08-11 | Friday systemd heartbeat → Aether kernel service | wrong layer | layer mismatch — Aether's own DEVLOG: kernel not booting in QEMU yet; no service exists to monitor, so a host systemd pattern can't exist at that layer |

Week-0 verdicts logged 2026-08-13 (both `pending human` rows resolved from the
v2.2 analysis; the tracker legend itself assigns v2.2 S1 = wrong mechanism and
v2.2 S2 = wrong layer). No `acted` yet — Phase C scaling stays deferred.

Scaling, the cost split, and Friday-V3 mining stay deferred until this
table shows at least one `acted` or a clear pattern across runs.
