# Friday V8 - Architecture

## The Five Layers

Friday implements a strictly layered architecture where each layer builds upon the one below. The design ensures that:

1. **Each layer ships raw proof** before the next starts
2. **Dependencies are unidirectional** (higher layers call lower layers only)
3. **Safety is enforced at the core** (L0-L2) and inherited by higher layers

### Layer 0 - Observability (L0)

**Purpose**: Structured logging with redaction and rotation

**Key Components**:
- `friday.observability` - Single choke point for all logging
- `observe()` decorator - Instruments primitives with L0 logging
- Log rotation: 10 MB default, 3 backups

**Log Format**:
```
{"timestamp": "...", "layer": "L1", "primitive": "window.open_app", 
 "args": {"command": "firefox"}, "result": {...}, "run_id": "..."}
```

**Security Features**:
- `redact_result=True` - Entire result hidden
- `log_transform` - Selective field redaction/compaction
- Secrets (credentials) never appear in logs

### Layer 1 - Primitives (L1)

**Purpose**: Domain-specific actions with explicit contracts

Every primitive is decorated with `@contract`:
```python
@contract(
    precondition="Hyprland session is live.",
    postcondition="Returns current client list; makes no state changes.",
    idempotency=Idempotency.IDEMPOTENT,
    failure_mode="PrimitiveError if hyprctl fails",
    returns="list[dict]: raw client objects",
)
def list_clients() -> list[dict[str, Any]]: ...
```

**Idempotency Classes**:
| Class | Meaning | Retry Behavior |
|-------|---------|----------------|
| `idempotent` | Read-only, safe to retry | Unlimited retries |
| `at-most-once` | Side effects on success | No retries by default |
| `commutative-safe` | State converges on retry | Unlimited retries |

**Platform Abstraction**:
- Linux: Hyprctl IPC for window/media, grim for screenshots
- Windows: win32 ctypes, PowerShell, PIL.ImageGrab
- Same API, different backends

### Layer 2 - Verification (L2)

**Purpose**: Read-only state checks for plan verification

**Rules**:
- Only idempotent (read-only) primitives can be imported
- Never mutates state to make a check pass
- Must exist BEFORE L3 calls it

**Verification Flow**:
1. Primitive executes
2. Check runs against real state
3. Check returns True/False (or scalar)
4. L3 verifies: `check_result == expect`

**Key Checks**:
```python
# Window verification
checks.window_has_class(cls: str) -> bool
checks.window_client_count() -> int
checks.window_only_classes(classes: list) -> bool  # sufficient for close_all

# Media verification
checks.media_playing() -> bool

# Browser verification
checks.browser_has_text(substring: str) -> bool
checks.browser_input_has_value(what: str, value: str) -> bool

# File verification
checks.file_exists(path: str) -> bool

# Messaging verification
checks.message_sent(platform: str, message_id: str) -> bool
```

### Layer 3 - Execution (L3)

**Purpose**: Deterministic state machine over plans

**State Transitions**:
```
PENDING → RUNNING → VERIFIED    (success)
               ↓
           RETRY → RUNNING       (bounded, by contract)
               ↓
        RETRY_EXHAUSTED → ABORT  (plan-level, loud, logged)
```

**Key Features**:
- Zero LLM calls
- Validates plan schema before execution
- Resolves `$steps.N.result.key` references
- Verifies every step through L2 checks
- Records capability gaps for unregistered primitives

**Step Resolution**:
```python
# Reference prior steps
"selector": "$steps.1.result.address"  # open step's return value
"message_id": "$steps.2.result.0.message_id"  # first element of list

# Rejects future references
"$steps.5.result.x"  # error if step 5 hasn't run yet
```

### Layer 4 - Planning (L4)

**Purpose**: Convert natural language goals to structured plans

**Flow**:
1. Goal string → LLM prompt (build_prompt)
2. LLM outputs JSON plan
3. Extract JSON, resolve `$facts.<name>` references
4. Validate against schema
5. Return plan for L3

**Prompt Structure**:
```
SCHEMA - exact JSON format L3 expects
PRIMITIVES - catalog of registered functions with signatures
CHECKS - read-only verification functions
PROJECT FACTS - file paths, recipients, general facts
KNOWN MISTAKES - bound rejection lessons
EXAMPLES - worked plan examples
GOAL - user's goal
```

**Bounded Retries**:
- 3 attempts by default
- Feed rejection reason back to LLM
- Record failures as lessons

---

## The Self-Improvement Loop

```
Capability Gap → Record → Triage → Draft → Gate → Register → Verify
       ↑                                                              ↓
       └────────────── Rejected Proposals ─────────────────────────────┘
```

### Gap Detection

When L3 encounters an unregistered primitive, it records a structured gap:
```json
{
  "source": "executor",
  "attempted_primitive": "files.find_file_exact",
  "goal_context": "find the receipt",
  "refusal_reason": "primitive not in REGISTRY"
}
```

### Triage

`gap_triage.py` groups gaps by primitive name and drafts proposals via LLM.

### Automated Gate

`automated_gate.py` applies strict checks:
- AST checks (imports, danger patterns)
- Contract schema validation
- Sandbox test run
- Build verification on real targets

### Human Approval

`register_proposal.py`:
1. Review draft artifacts
2. Sign `APPROVED.md`
3. Gate registers to actual L1 module

### Lessons Loop

```
Rejection → Record (lessons.jsonl) → Generalize → Candidate (gates/proposed_*)
    ↓
Human approval (config/lessons.json) → Inject into prompts
```

Approved lessons prevent the same failure class from recurring.

---

## Data Flow

```
User Goal
    ↓
┌─────────────────┐
│ L4: Planner     │ → LLM → Plan JSON
└─────────────────┘
    ↓
┌─────────────────┐
│ L3: Executor    │ → Step 1: primitive(args) → verify(check, expect)
└─────────────────┘     Step 2: ...
    ↓           ↘
Result          Verify: check() == expect
    ↓               ↓
                 PASS/FAIL → RETRY/ABORT
    ↓
┌─────────────────┐
│ L0: Logs        │ → Log line per call
└─────────────────┘
    ↓
Result
```

---

## Safety Invariants

1. **Read-only verification only**: L2 checks never mutate state
2. **Protected windows**: Terminal classes never closed
3. **Blocked primitives**: Destructive ops mechanically unreachable
4. **Dangerous gate**: Shell/LLM bypass requires explicit env var
5. **Allowlists**: Triggers limited to safe primitives
6. **Capability gap recording**: Unresolved primitives become proposals, never fail silently
7. **Result redaction**: Secrets and sensitive data never in logs