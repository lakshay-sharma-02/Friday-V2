# CAPABILITY_GAP_PROOF - gap -> draft (self-improvement loop, steps 1-2)

Status date: 2026-08-10T04:47:25+00:00.

The refusal, the gap record, the triage grouping and the LLM draft all run
through the REAL shipped stack; only the triggering plan is hand-written
(the same convention WATCHER_PROOF uses for deterministic plans), so the
proof is reproducible.

## 1. The refusal (real L3 executor)

```
plan aborted at step 1: "primitive 'files.do_thing' has no registered contract; refusing to call it"
```

`files.do_thing` is a real module with an unregistered function -
`_resolve_primitive` refuses it (`no registered contract`) and the plan
ABORTs exactly as it did before the gap loop existed; the gap record is
additive, never a behavior change.

## 2. The structured capability-gap record

```
{
  "gap_id": "18ca58326015f70b29",
  "timestamp": "2026-08-10T04:46:15.589496+00:00",
  "source": "executor",
  "attempted_primitive": "files.do_thing",
  "attempted_args_shape": {
    "name": "str:1",
    "recursive": "bool"
  },
  "goal_context": "locate the missing artifact and report it",
  "refusal_reason": "\"primitive 'files.do_thing' has no registered contract; refusing to call it\"",
  "goal_id": "locate the missing artifact and report it"
}
```

One record per refusal: source, goal_context, attempted_primitive,
attempted_args_shape (type tags only - no values, so secrets and mail
metadata never ride a gap record), and the refusal_reason.

## 3. Triage (group + LLM draft)

```
files.do_thing: drafting proposal from 3 gap record(s)...
  files.do_thing: draft written to gates/proposed_primitives/files.do_thing
```

Artifacts: `gates/proposed_primitives/files.do_thing/`

- `contract.json` - the draft Contract following friday/contracts.py
- `impl.py` - a draft @contract-decorated function
- `test.py` - a draft hermetic unittest
- `rationale.md` - which refused goal(s) drove this, in plain language

Draft status from rationale.md:

```
- impl compiles: no
- test compiles: yes
- APPROVAL: PENDING - this is a DRAFT; nothing is registered. The
```

## 4. Draft quality is a KNOWN LIMIT

The LLM draft is only syntax-checked (compile()) - it is NOT semantic-

or safety-validated, and there is no sandboxed build or approval gate

(that machinery is aspirational). A real run observed the model emitting

the contract as a Python decorator-source string instead of a JSON

object, and an impl that hardcoded a filename while ignoring its own

name argument. Such a draft compiles yet is wrong - it must be rejected

at HUMAN REVIEW, never registered: nothing in this loop self-registers,

and a rejected draft changes nothing about the running agent.


## 5. Approval + registration - PENDING BY DESIGN

The meta-engine gate (AST-validation + sandboxed build + dual human
approval) described in the plan DOES NOT EXIST in this repo yet - it is
aspirational (see gates/PLAN_STATUS.md section 8). Per the session
constraint, no parallel approval flow was invented: **nothing is
auto-registered**. A human must review these draft artifacts and, if
approved, wire the primitive through the REAL registration path:

1. create friday/l1/<module>.py with the reviewed contract + function,
2. add the module name to planner._L1_MODULES so the registry populates,
3. re-run the original goal that produced the gap - it should now plan
   and execute instead of refusing.

## Verdict

Gap -> draft loop proven end to end with real machinery. Approval +
registration await the approval-gate decision.

