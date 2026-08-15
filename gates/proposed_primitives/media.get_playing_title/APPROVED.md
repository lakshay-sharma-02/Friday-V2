# Human approval

APPROVED

Reviewed 2026-08-14 after the automated gate passed. Read-only, idempotent,
reuses the module's own _socket_send/_reply_ok helpers, returns None on
absence (mirrors is_playing). Contract matches impl exactly. Register.
