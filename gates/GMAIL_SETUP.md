# Gmail API setup — complete guide (from scratch to permanent token)

Status date: 2026-08-08. Applies to Task #10 (Gmail unread summary) and
every future Gmail task. The integration itself (`friday/l1/gmail.py`) is
already built and validated; this document is only about the Google-side
credentials — the one part that cannot be automated.

## The problem this guide solves (the 7-day expiry)

Google's OAuth docs are explicit: a project whose OAuth consent screen has
**publishing status "Testing"** (external user type) is issued a **refresh
token that expires in 7 days**, unless the only scopes are
openid/profile/email. `gmail.readonly` is not in that exempt subset, so a
testing-mode token dies after 7 days and every future Gmail task would
need the consent flow re-run.

With publishing status **"In production"**, the 7-day rule does not apply.
Production refresh tokens stop working only when:

1. the user revokes the app's access;
2. the token goes unused for **6 months**;
3. the user **changes their Google password** (this invalidates tokens
   with Gmail scopes — a real gotcha);
4. the account exceeds 100 live refresh tokens per client;
5. time-based access / admin policy / app deletion.

So the one-time setup is: **publish the app to Production, then run the
consent flow once** — that single token is permanent (until one of the
above happens, at which point you re-run the 5-minute flow in Part 6).

Note: an **unverified** Production app that requests sensitive scopes
(`gmail.readonly` is sensitive) shows a "Google hasn't verified this app"
warning on the consent screen and can be used by up to 100 users. For
personal use that warning is cosmetic — you click through it once. Full
verification (with the brand + privacy-policy + security questionnaire
burden) is NOT required for this.

---

## Part 1 — Create the Google Cloud project

> Skip if you already have the project that owns client ID
> `355325899244-…` (project `friday-gmail-504910`).

1. Go to https://console.cloud.google.com and sign in with the Google
   account whose Gmail you want Friday to read (use the SAME account
   throughout — the one you'll approve the consent screen with).
2. Top-left project picker → **New Project**.
3. Name it (e.g. `friday-gmail`) → **Create**.
4. Wait for it to appear in the picker; select it so every later step
   lands in the right project.

## Part 2 — Enable the Gmail API

1. **APIs & Services → Library** (left sidebar).
2. Search `Gmail API` → open it → **Enable**.
3. Confirm the breadcrumb shows your project name.

## Part 3 — Configure the OAuth consent screen

1. **APIs & Services → OAuth consent screen** (in some consoles:
   Google Auth Platform → Branding/Audience).
2. User type: **External** → **Create**.
3. **App information:**
   - App name: `Friday` (anything).
   - User support email: your Google email (from the dropdown).
4. **Developer contact information:** your email.
5. Save (you don't need to add scopes here — they're requested at runtime
   by the integration; scopes added here are just the ones Google
   pre-shows).

## Part 4 — Create the Desktop OAuth client

1. **APIs & Services → Credentials → Create credentials → OAuth client
   ID.**
2. Application type: **Desktop app** → name it (e.g. `friday-desktop`) →
   **Create**.
3. A dialog shows the **client ID** and **client secret**. Download the
   JSON (**Download JSON** button) → save as
   `/home/lakshay/Downloads/credentials.json` (or anywhere).
4. You do NOT need to add any Authorized redirect URIs — Desktop app
   clients accept `http://localhost:<port>/` loopback redirects natively.

If you ever lose the JSON: Credentials → your client → copy both values.
The integration reads them from `pass` at `friday/gmail` (or the env vars
`GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` / `GMAIL_REFRESH_TOKEN`).

## Part 5 — Publish to Production (the permanent fix)

> This is the step that kills the 7-day expiry. Do this BEFORE the
> consent flow so the token you obtain is permanent from birth.

1. **APIs & Services → OAuth consent screen** (or **Google Auth Platform
   → Audience**).
2. If the console shows a **Test users** section: optionally add your
   email there for testing, but it is NOT required once you publish.
3. Click **PUBLISH APP** (in newer consoles: **Publish app** under
   Publishing status).
4. Confirm the dialog. Status becomes **In production**.
5. You may see warnings about a privacy policy / homepage. For personal
   unverified use you can proceed; if the console hard-blocks publishing
   without a privacy policy URL, paste any real URL you control (a GitHub
   page/gist works) and add its domain under **Authorized domains** on
   the consent screen. The "unverified app" warning will still appear on
   the consent screen — that is expected and harmless for ≤100 users.

## Part 6 — One-time consent flow (get the refresh token)

Run from the project root (this is the part I execute with you — the
browser approval is yours):

```sh
cd '/home/lakshay/Projects/Friday V2'
./.venv/bin/python -u gates/_gmail_oauth_setup.py /path/to/credentials.json
```

1. The script opens the consent page in your browser and waits up to 5
   minutes on `http://localhost:8765/` for the redirect.
2. In the browser, on the **"Google hasn't verified this app"** screen:
   **Advanced → Go to Friday (unsafe)**.
3. Confirm the account shown is the target Gmail, tick the
   `gmail.readonly` checkbox → **Continue**.
4. You land on a local page saying **"Friday received the code"** — close
   the tab.
5. The script exchanges the code and stores
   `{"client_id", "client_secret", "refresh_token"}` in **pass** at
   `friday/gmail`.

Verify it landed:

```sh
pass show friday/gmail        # shows the JSON with the refresh token
```

The script never prints the client secret; it prints the refresh token
prefix once for your records. If the network dies mid-flow (a local
server on port 8765 must receive the redirect), just re-run the same
command — it picks a free port if 8765 is busy.

## Part 7 — What keeps this working (and what breaks it)

- Access tokens are refreshed automatically from the refresh token by
  `friday/l1/gmail.py` — nothing to do.
- Production refresh token stays valid until: you revoke the app
  (myaccount.google.com → Security → Third-party access), it sits unused
  for 6 months, **you change your Google password**, or the account hits
  100 live tokens for this client.
- If any of those happen: re-run Part 6 once (5 minutes) and you're back.
  Do NOT create new OAuth clients repeatedly — the 100-token limit is per
  client, and a fresh client means a fresh consent + storage.

## Part 8 — Next steps in the repo (already built)

1. `./.venv/bin/python -u gates/_gmail_inbox_snapshot.py` — shows which
   senders have genuinely unread mail (pick one).
2. `./.venv/bin/python -u gates/bringup_gmail.py '<sender>'` — standalone
   primitive proof (structural shape, body redacted).
3. `./.venv/bin/python -u gates/task_gmail_summary.py '<sender>'` — the
   full goal-string pipeline; registers in `var/logs/tasks.jsonl`.

Proof artifacts: `gates/BRINGUP_GMAIL_PROOF.md` and
`gates/TASK_GMAIL_SUMMARY_PROOF.md`.
