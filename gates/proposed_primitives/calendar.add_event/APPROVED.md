# Human approval

APPROVED

Reviewed 2026-08-14 after the automated gate passed (AST + registration +
sandbox). The LLM draft was corrected at human review: end<=start was a
STRING comparison (wrong across mixed timezone offsets, no format
validation despite the contract promising RFC 3339) - now parsed with
datetime.fromisoformat, with tests for the mixed-offset and invalid-input
cases. The refresh token in pass friday/calendar carries both
calendar.readonly + calendar.events scopes (consent re-run 2026-08-14).
Register into friday/l1/calendar.py, then verify LIVE: create a real
event and read it back.
