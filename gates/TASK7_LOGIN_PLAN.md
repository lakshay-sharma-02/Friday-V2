# Task 7 — First browser login (secrets from `pass`) — PLAN

Status: **scheduled** (runs after Task 6). Not started.
Target: a real account — default example **GitHub** (swappable, see
"Change the target" below).

## Why this is next

`browser.credentials` + `browser.login` are the last major unproven L1
area: no gate or task has ever exercised them. Per the master plan, a
primitive that can't be proven standalone never gets called by the
executor — so this task is the scheduled proof of the secrets path.

The mechanism is already built and log-safe:

- `login(service, username_sel, password_sel, submit_sel)` fetches
  credentials from `pass` **internally** (`friday/secrets.get_credentials`).
  Its L0-logged args are the service name and selector strings **only** —
  the secret never enters the log.
- `friday/secrets.py` is genuinely called (no dead import).
- Both primitives are contract-registered and already in the planner catalog.

## Prerequisites (all must be true before the task runs)

1. **User creates the pass entry** (manual — only you know the creds):

   ```sh
   pass insert -m friday/github
   ```

   storing JSON `{"username": "...", "password": "..."}` (the parser also
   accepts the older two-line user/pass form).
2. **No 2FA / passkey-only auth** on the account — the primitive cannot do
   OTP. (GitHub: Settings -> Password and authentication.)
3. **Session control**: the Playwright persistent profile
   (`var/browser_profile/`) retains sessions across runs — the phase-1
   bring-up logged in, so a GitHub session exists there now. Both the
   bring-up and the composite task script therefore log out FIRST
   (`goto https://github.com/logout` then click "Sign out" — github.com/logout
   now shows a confirmation page) so `login()` must do real work. Never
   assume a clean profile.
4. **No browser left running** when the task starts (`browser.close()`
   hygiene at the end of each run).

## Phases

### 1. Standalone bring-up (before any executor call)

Hand-invoked, raw output captured (mini proof like `bringup_gate1.py`):

- `credentials("github")` returns `{username, password}` — and the printed
  result must **not** contain the password (redaction proof at the
  primitive level).
- `goto(<login url>)` + `read_page_text()` shows the login form.
- Hand-invoked `login(...)` with the real handles lands on the
  logged-in state.
- `browser.close()` hygiene.

Defects get fixed in this phase, per the plan's discipline.

### 2. Prompt teaching (in-gate; expect 1–2 iterations)

- Generic FRAMEWORK NOTE for `browser.login`: the three `*_sel` args are
  REAL page strings resolved through the fallback chain (never invented —
  the DuckDuckGo lesson); `service` must match a pass entry name; verify
  the logged-in state with `checks.browser_has_text` on a post-login
  marker.
- Site-specific field handles (if the model cannot derive them) go in
  `config/planner_facts.json` facts — user-editable config, **never code**
  (the anti-pattern line in the master plan is about handler code).

### 3. Composite task (Gate-6-grade proof)

New file `gates/task7_browser_login.py`, modeled on `task4_ddg_search.py` /
`task5_media_timer.py`, with the honest DoD read from the raw L0 trace.

- GOAL (example):
  `log in to GitHub using the stored credentials for 'github' and report whether the login succeeded`
- Expected LLM plan shape (L4 produces it; we do not hand-write it):

  1. `browser.goto("https://github.com/login")`
     → verify `checks.browser_has_text` on a login-form marker
  2. `browser.login(service="github", username_sel="<real handle>",
     password_sel="<real handle>", submit_sel="<real handle>")`
     → verify `checks.browser_has_text` on a **post-login** marker
     (one that only exists when logged in, e.g. "New repository")
  3. `browser.read_page_text()` as the report step

- **No new L2 check**: the post-login marker via the existing generic
  `checks.browser_has_text` — composition, not per-site code.
- The task script does the logout-first prep (Prerequisites 3) before
  running the plan, mirroring `bringup_login.py`.
- Redaction is now STRUCTURAL, not just a DoD assertion: `credentials()`
  logs `<redacted>` (`redact_result`), and `login()` fills credentials
  through the un-logged `_fill_field` (the phase-1 bring-up found and
  fixed a plaintext leak via type_text's `text` arg). The DoD assertion
  stays as belt-and-suspenders.

### 4. DoD (all from raw L0 trace)

- every step VERIFIED, plan COMPLETED;
- the post-login marker check is `True` only AFTER `login()` ran (order
  visible in the trace);
- **redaction assertion**: the actual password (fetched via
  `credentials(service)`) appears NOWHERE in the run's log lines — the
  task script asserts this, like task5's DoD asserts its own claims;
- raw output captured to `gates/TASK7_BROWSER_LOGIN_PROOF.md`.

## Risks / mitigations (all in-gate)

| Risk | Mitigation |
|---|---|
| LLM invents field handles | prompt note + facts bullets (config), never code |
| 2FA / passkey on the account | hard prerequisite — skip/swap target if enabled |
| Profile already logged in | logout-first prep in the task script (see Prerequisites 3); post-login marker must require genuine login |
| GitHub DOM drift | marker + handles chosen in-gate from real page text |
| Secret in logs | `login()` args are selectors only; DoD enforces redaction |

## Change the target (any real site)

- `pass insert -m friday/<site>` with the JSON credentials;
- update the GOAL and (if needed) facts with that site's real field
  handles + post-login marker;
- everything else — phases, executor, DoD — is site-agnostic.

## Sequencing

1. Task 6 (window or browser-click task, per the user's choice).
2. User: create the `pass` entry (`pass insert -m friday/github`).
3. Standalone bring-up (phase 1) → prompt teaching (phase 2) →
   composite (phase 3) → DoD proof (phase 4).
