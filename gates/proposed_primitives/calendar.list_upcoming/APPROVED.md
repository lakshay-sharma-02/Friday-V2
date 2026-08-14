# Approval: calendar.list_upcoming

APPROVED

## Review record (2026-08-13) — cycle 2, ZERO hand-correction

This is the loop's SECOND complete cycle and its first with NO human
correction: the LLM draft (laguna-xs via FRIDAY_TRIAGE_MODEL) passed the
triage self-check repair loop and every automated gate stage unchanged.

Automated gate (all passed before this signature):
- contract schema: PASS (name `calendar.list_upcoming`, exactly
  `<module>.<fn>`)
- AST: PASS (allowed imports incl. requests; no dangerous calls; no
  sandbox-escaping writes; `list_upcoming()` defined; no dead arguments)
- sandbox: PASS — the draft's own 8-test hermetic suite (API mocked)
- build-verify: **NOT APPLICABLE for module class 'calendar'** — no safe
  real target for this class; human review required (the documented limit:
  build-verify is real for files.* only). For this primitive, this
  signature IS the semantic check, as the architecture intends.

Human review findings (accepted for a READ-ONLY primitive):
1. The impl is a real Google Calendar API call (`/calendars/primary/events`
   with timeMin/timeMax/singleEvents/orderBy) following gmail.py's
   credentials pattern (`friday.secrets.get_credentials("calendar")` /
   `GOOGLE_CALENDAR_TOKEN`).
2. L0 redaction: `_log_redact_calendar_meta` hides the `summary` field
   (event content) while keeping event_id/timestamps visible — the gmail
   privacy discipline applied to calendar.
3. **Credentials are NOT yet configured**: `pass show friday/calendar`
   does not exist and GOOGLE_CALENDAR_TOKEN is unset. The impl degrades
   gracefully (returns an empty list), so a goal planned against it will
   FAIL its `checks.list_nonempty` verification honestly — it cannot
   silently fake events. The primitive is registered but inert until
   calendar OAuth credentials are configured (the same state gmail was in
   before its token setup).
4. Error semantics: non-200 API responses raise PrimitiveError; no events
   returns []. Distinct, per the contract.

## Why this primitive exists

Driven by the real gap record from `ambient-gap-probe-calendar`:
goal_context "show me my upcoming calendar events for the week",
attempted_primitive `calendar.list_upcoming` (args shape {days: 7}),
refused because the calendar module does not exist. The probe is retired
with this registration (lifecycle precedent: email-send, file-write).
