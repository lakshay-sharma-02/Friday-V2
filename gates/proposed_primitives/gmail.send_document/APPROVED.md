APPROVED

Reviewed and approved by the human gate on 2026-08-11 (session with the
capability-gap loop; the user selected "Reviewed, signed, consented").

The two prior LLM drafts for this gap were REJECTED on record (see
rationale.md): a confabulated wrapper around a nonexistent
`gmail.send_document`, and an invalid contract qualified name. The
approved proposal is HAND-BUILT, not LLM-drafted.

Approved proposal:
- primitive: gmail.send_document(file_path, to=None, subject=None, body=None)
- Gmail REST API `messages.send` with a base64url MIME multipart message
  (attachment via stdlib `email`), authenticated by the module's existing
  `_access_token()` refresh machinery.
- contract: at-most-once (retry can duplicate a send; the executor never
  blind-retries); log_transform=_log_redact_send_meta keeps the recipient
  out of the L0 result line while message_id stays visible.
- automated gate verdict on record: AST checks passed; sandbox test run
  6/6 PASS; build-verify honestly NOT APPLICABLE for the gmail class
  (no safe real target) - human review IS the semantic gate for this one.
- impl: appends to the existing friday/l1/gmail.py, carrying only the
  `email` MIME imports the module lacks.

Signed decision: this is the loop's first SIDE-EFFECTING primitive. The
human gate reviewed the impl and accepts the expansion of Friday's gmail
surface from read-only to send-capable.

NOTE (2026-08-11): the live proof additionally requires the OAuth
re-consent with the gmail.send scope ADDED (tokeninfo confirmed the
current token is still readonly-only at approval time) - the browser step
is the user's, documented in gates/GMAIL_SETUP.md section 6.5.
