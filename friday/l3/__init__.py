"""L3 - Execution.

A deterministic state machine per plan step:

    PENDING -> RUNNING -> {VERIFIED, FAILED}
    FAILED -> RETRY (bounded, with backoff) -> RUNNING
    FAILED -> RETRY_EXHAUSTED -> ABORT (plan-level, loud, logged)

The executor contains zero LLM calls - it is a dumb, deterministic walker
over a plan (a list of {primitive, args, verify} steps), checking through
L2 and logging through L0. It must be fully testable against a hardcoded
plan with no dependency on L4 existing.
"""
