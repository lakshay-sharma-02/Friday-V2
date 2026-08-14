# Proposed trigger: verify-mpv-lifecycle-holds-under-repeate

STATUS: PROPOSED - NOT approved, and INERT. This trigger is proposed by
Friday from its own failure history; nothing runs until YOU approve it.

## The goal (verbatim quoted evidence - never rewritten)

> verify mpv lifecycle holds under repeated invocation

## WARNING: this goal has FAILED 2 time(s)

It is proposed precisely BECAUSE it kept failing - review WHY before you
ever enable it. It is not silently scheduled; the human gate is the whole
point of this stage.

## Evidence

- failed 2 time(s): retry-stress, retry-stress
- last failure: 2026-08-08T07:46:08.365871+00:00
- failure timestamps:
  - 2026-08-08T07:45:29.743331+00:00
  - 2026-08-08T07:46:08.365871+00:00

WATCH-layer L0 failures for this exact goal:
  (no matching WATCH-layer L0 failures)

## The draft trigger (watcher-validated, enabled: false)

```json
{
  "id": "verify-mpv-lifecycle-holds-under-repeate",
  "goal": "verify mpv lifecycle holds under repeated invocation",
  "schedule": {
    "type": "time",
    "at": "09:00",
    "days": [
      "mon",
      "tue",
      "wed",
      "thu",
      "fri"
    ]
  },
  "allow": [],
  "notify": true,
  "enabled": false
}
```

Note: "allow" is empty by design - with no allowlist the trigger would
refuse every step, so it cannot act until you grant each primitive scope.
The draft goal is quoted evidence; if you approve it, review the goal
text and the schedule too.

## To approve (the human gate - same philosophy as APPROVED.md)

1. Copy trigger.json into config/watcher.json (inside "triggers").
2. Expand "allow" to the primitives this goal legitimately needs
   (e.g. ["gmail.*"]); an empty allowlist is a refusal-only trigger.
3. Review the goal text and schedule.
4. Flip "enabled" to true. Until then this proposal changes nothing.
To reject, delete this directory - the cluster then re-candidates when
new failures arrive.
