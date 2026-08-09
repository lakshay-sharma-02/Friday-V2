# GMAIL BRING-UP — list_unread / get_message / summarize (Phase 2 Task #10)

Status date: 2026-08-08.

## 0. The one-time OAuth setup (documented here so it is reproducible)

The Gmail integration uses the official **Gmail REST API** via OAuth2
(installed-app flow), scope **`gmail.readonly` only** — this is a
read-only integration by design (the task's explicit non-goal: no write
or send scopes). The decision: Gmail API over IMAP, consistent with the
Cloud-API-over-browser-automation pattern established for WhatsApp;
IMAP rejected as the "brittle generic path" the task prompt warns about.

The complete from-scratch guide (project creation → production publish
→ consent) lives at **`gates/GMAIL_SETUP.md`**. Summary of what was done
once by the user:

1. Google Cloud project created; **Gmail API enabled**; OAuth client
   (Desktop app) created — client ID `355325899244-…` (project
   `friday-gmail-504910`).
2. Consent screen status flipped to **In production** (external user
   type) — this matters: in **Testing** status Google expires refresh
   tokens after **7 days**; in production they are permanent (revoked
   only by user action, 6 months unused, or password change).
3. Consent flow run once via `gates/_gmail_oauth_setup.py`; the
   `{client_id, client_secret, refresh_token}` triple stored in **pass at
   `friday/gmail`** (env vars `GMAIL_CLIENT_ID` / `GMAIL_CLIENT_SECRET` /
   `GMAIL_REFRESH_TOKEN` override it).

`friday/l1/gmail.py` then refreshes access tokens automatically from the
refresh token — no further manual steps, ever.

## 1. What the bring-up proves

- `gmail.list_unread(sender)` returns structural metadata of real unread
  mail (message_id, From, Subject, Date) — no body, no token, and an
  auth failure is an exception while an empty inbox is an empty list
  (the two can never be conflated).
- `gmail.get_message(message_id)` returns headers + readable content;
  the body is REDACTED from this proof (only its length is shown).
- `gmail.summarize(message_id)` produces a non-trivial summary via a
  documented internal LLM call (`dev.run`) — the deliverable.
- Read-only throughout: `gmail.readonly` scope, nothing marked read.

## 2. Raw run output

================================================================
========================================================================
GMAIL BRING-UP - list_unread / get_message / summarize (read-only)
SENDER: 'accounts.google.com'
========================================================================

=== SECTION A - gmail.list_unread (structural shape, real inbox) ===
{
  "message_id": "19fe106a7af2070b",
  "sender": "Google <no-reply@accounts.google.com>",
  "subject": "Security alert",
  "date": "Sat, 08 Aug 2026 10:58:56 GMT"
}
{
  "message_id": "19fe0f7334590800",
  "sender": "Google <no-reply@accounts.google.com>",
  "subject": "Security alert for sharmalakshay1253@gmail.com",
  "date": "Sat, 08 Aug 2026 10:42:02 GMT"
}
{
  "message_id": "19fe0d1fb2b0d6ba",
  "sender": "Google <no-reply@accounts.google.com>",
  "subject": "Security alert for sharmalakshay1701@gmail.com",
  "date": "Sat, 08 Aug 2026 10:01:24 GMT"
}
{
  "message_id": "19fe0d1d6e83b52f",
  "sender": "Google <no-reply@accounts.google.com>",
  "subject": "Security alert for sharmalakshay1701@gmail.com",
  "date": "Sat, 08 Aug 2026 10:01:15 GMT"
}
{
  "message_id": "19fe0d131cfc6c0a",
  "sender": "Google <no-reply@accounts.google.com>",
  "subject": "Security alert for sharmalakshay0216@gmail.com",
  "date": "Sat, 08 Aug 2026 10:00:31 GMT"
}
OK: list_unread returned 5 unread message(s); structural shape above (id, From, Subject, Date - no body, no token)

=== SECTION B - gmail.get_message (headers + body presence, body REDACTED) ===
message_id : 19fe106a7af2070b
from       : Google <no-reply@accounts.google.com>
subject    : Security alert
date       : Sat, 08 Aug 2026 10:58:56 GMT
snippet    : 'You allowed friday-gmail access to some of your Google Account data sharmalakshay0208@gmail.com If you didn&#39;t allow friday-gmail access to some of your Goog'
body       : <1230 chars - REDACTED from output>
OK: get_message returned structural metadata + readable content (body length above, content redacted)

=== SECTION C - gmail.summarize (the deliverable; internal LLM call) ===
SUMMARY (for 19fe106a7af2070b):
From Google, a security alert email sent to sharmalakshay0208@gmail.com warns that friday-gmail may have been granted access to the user's Google Account data. It states that if the user did not grant this access, someone else might be trying to access the data. The email urges the user to check their account activity and secure the account immediately. It provides links to view recent activity and manage app permissions. No specific deadline is given, but prompt action is requested.
OK: summarize returned a non-trivial summary (deliverable above)

=== BRING-UP DoD ===
  OK: list_unread -> structural shape (real unread mail)
  OK: get_message -> headers + readable body (redacted from output)
  OK: summarize -> non-trivial summary text produced
  OK: read-only throughout (no labels modified, no mail marked read)
BRING-UP: DONE
