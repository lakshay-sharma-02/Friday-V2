# MCU Friday v1 — Architecture

> "I am Friday. I observe, I infer, I act, I learn, I communicate."

## Ideology

Current Friday executes goals you give it. MCU Friday **understands what you need before you ask**.

The shift:
- **V8**: "Pause music" → plan → execute → done
- **MCU**: Observes you play music every morning at 8am → preloads your playlist → notices you skipped a track yesterday → adjusts today's queue → proactively asks "want me to queue that podcast you mentioned?"

## Core Principles

1. **Headless-first**: API-only. No compositor dependency. Deploy on a VPS, control from your phone.
2. **Adapter model**: Every integration is a plugin. Register capabilities, not hardcoded paths.
3. **Event-driven**: Not polling loops. Real events from real sources.
4. **Learning is first-class**: Not a prompt injection. A real memory system that shapes behavior.
5. **Confidence over certainty**: Actions have confidence scores. Low-confidence actions ask for confirmation.

## Architecture

```
┌─────────────────────────────────────────────────────┐
│                    FRIDAY CORE                        │
│  contracts · registry · events · observability       │
├─────────────────────────────────────────────────────┤
│                    FRIDAY BRAIN                       │
│  planner · executor · reasoning · context            │
├─────────────────────────────────────────────────────┤
│                    FRIDAY MEMORY                      │
│  working · episodic · semantic · procedural           │
├─────────────────────────────────────────────────────┤
│                    FRIDAY OBSERVER                    │
│  patterns · predictions · user_model · anomalies     │
├─────────────────────────────────────────────────────┤
│                    FRIDAY COMMS                       │
│  channels · proactive · natural · adaptive           │
├─────────────────────────────────────────────────────┤
│                    FRIDAY ADAPTERS                    │
│  whatsapp · telegram · gmail · browser · calendar    │
│  files · media · clipboard · system · http · ...     │
└─────────────────────────────────────────────────────┘
```

## Layer 1: Core (friday.core)

The non-negotiable foundation. Cherry-picked from V8, cleaned up.

### contracts.py
- `@contract` decorator (from V8 — proven, elegant)
- `Idempotency` enum
- `Contract` dataclass
- `REGISTRY` dict
- `EXECUTOR_BLOCKED` frozenset

### registry.py
- Module auto-discovery (from V8 `_discover_l1_modules`, fixed path)
- `register(module)` / `get(name)` / `list_all()` / `list_blocked()`
- Capability catalog generation

### events.py
- Event bus (pub/sub, not log-file-only)
- `Event` dataclass with: timestamp, source, type, data, correlation_id
- `EventBus` with `emit()` / `subscribe()` / `drain()`
- Event types: `PRIMITIVE_CALL`, `STEP_COMPLETE`, `GOAL_START`, `GOAL_COMPLETE`, `ERROR`, `LEARNING`, `PATTERN_DETECTED`, `USER_ACTION`

### observability.py
- Structured JSON logging (from V8 — good as-is)
- L0 log rotation
- Per-primitive log projection
- Redaction support

### errors.py
- Exception hierarchy (from V8 — good as-is)

## Layer 2: Brain (friday.brain)

The intelligence. Not just "call LLM, parse JSON."

### planner.py
- Goal → plan conversion (adapted from V8 L4)
- Template matching (from V8, but deduplicated — one template = one pattern, not 50 copy-paste variants)
- **Context-aware planning**: uses memory + observer data to inform plans
- **Confidence scoring**: every plan has a confidence score
- **Multi-attempt with feedback**: when a plan fails, the failure context feeds back

### executor.py
- Deterministic state machine (from V8 L3 — proven, solid)
- **Streaming events**: emits step progress in real-time via the event bus
- **Adaptive retry**: uses memory of past failures to adjust retry strategy

### context.py
- **Working context**: what's happening RIGHT NOW
  - Active windows, playing media, open files, recent commands
  - Time of day, day of week, user's current activity
- **Goal context**: what the user is trying to achieve
  - Current goal + history of recent goals
  - Related memories and patterns
- **Environmental context**: system state
  - Running processes, network status, battery, etc.

### reasoning.py
- **Chain-of-thought**: break complex goals into sub-goals
- **Hypothesis testing**: try an approach, verify, adjust
- **Anomaly detection**: "this goal has failed 3 times in the same way — something is wrong"
- **Capability assessment**: "I can do X, Y, Z but not W — here's what I can try"

## Layer 3: Memory (friday.memory)

Not a JSONL file. A real memory system.

### architecture

```
┌─────────────────────────────────────┐
│          Working Memory              │
│  Current context, active goals,     │
│  recent interactions (last hour)    │
├─────────────────────────────────────┤
│          Episodic Memory             │
│  "Last Tuesday, user asked me to    │
│   send the report to WhatsApp"      │
│  Indexed by: time, goal, outcome    │
├─────────────────────────────────────┤
│          Semantic Memory             │
│  "User prefers formal tone in       │
│   work emails, casual in personal"  │
│  Indexed by: concept, relationship  │
├─────────────────────────────────────┤
│          Procedural Memory          │
│  "To send Gmail, first list_unread, │
│   then get_message, then summarize" │
│  Indexed by: goal_pattern, success  │
└─────────────────────────────────────┘
```

### store.py
- **Working memory**: in-memory dict, TTL-based expiry
- **Episodic memory**: JSONL-backed, indexed by timestamp + goal hash
- **Semantic memory**: key-value store with TF-IDF or embedding-based retrieval
- **Procedural memory**: successful plan patterns, indexed by normalized goal signature

### retrieval.py
- `recall(query, memory_type, limit)` — search across memory types
- `consolidate()` — merge working → episodic → semantic (like sleep consolidation)
- `forget(key)` — intentional memory deletion
- `reinforce(key)` — strengthen a memory (successful recall = stronger)

### learning.py
- **Pattern detection**: "user asks for email summary every morning at 9am"
- **Success prediction**: "this goal succeeded 80% of the time with this approach"
- **Failure analysis**: "goals fail when Gmail OAuth token is expired"
- **Behavior adaptation**: "user prefers Telegram over WhatsApp for long messages"

## Layer 4: Observer (friday.observer)

The proactive intelligence. This is what makes MCU Friday different from "a CLI that calls Claude."

### patterns.py
- **Temporal patterns**: time-of-day, day-of-week, seasonal
- **Goal patterns**: recurring goals, goal sequences, goal dependencies
- **Platform patterns**: which platform for which type of message
- **Failure patterns**: common failure modes, environmental factors

### predictions.py
- "User will likely ask for email summary in 10 minutes"
- "This goal has a 90% success rate on weekdays, 40% on weekends"
- "Battery is at 15% — user might need a charge reminder"

### user_model.py
- **Preferences**: tone, platform, time preferences, notification style
- **Habits**: daily routines, weekly patterns, seasonal behaviors
- **Context**: current project, recent focus areas, upcoming deadlines

### anomalies.py
- Detect unusual patterns: "email volume is 3x normal today"
- Detect failures: "3 goals failed in a row — something is wrong"
- Detect opportunities: "user hasn't checked email in 6 hours — might be busy"

## Layer 5: Communications (friday.comms)

Not just "notify_send." Intelligent, adaptive communication.

### channels.py
- Abstract `Channel` interface: `send(message)` / `receive()` / `status()`
- Concrete channels: WhatsApp, Telegram, Discord, Email, Desktop, SMS
- Channel selection: "for short updates, use Telegram; for files, use WhatsApp"

### proactive.py
- **Scheduled insights**: "Here's your daily briefing"
- **Event-driven alerts**: "New email from [important person]"
- **Pattern-based suggestions**: "You usually check email at 9am — want me to summarize now?"
- **Failure notifications**: "Goal X failed — here's what I think is wrong"

### natural.py
- **Adaptive tone**: formal for work, casual for personal
- **Context-aware messages**: include relevant history
- **Progressive disclosure**: summary first, details on request
- **Confirmation flows**: "I'm about to send this email — confirm?"

### adaptive.py
- **Channel learning**: "user responds faster on Telegram than WhatsApp"
- **Timing learning**: "don't send notifications after 10pm"
- **Volume learning**: "don't spam — batch updates hourly"

## Layer 6: Adapters (friday.adapters)

Each adapter is a self-contained plugin. Not a 200-line module mixed into a monolith.

### Adapter Interface

```python
class Adapter(ABC):
    """Every integration implements this."""
    
    @property
    def name(self) -> str: ...
    
    @property
    def capabilities(self) -> list[str]: ...
    
    async def initialize(self) -> None: ...
    
    async def execute(self, action: str, **kwargs) -> Any: ...
    
    async def observe(self) -> list[Event]: ...
    
    def health_check(self) -> bool: ...
```

### Built-in Adapters
- `whatsapp` — WhatsApp Cloud API
- `telegram` — Telegram Bot API
- `discord` — Discord Bot API
- `gmail` — Gmail REST API (OAuth2)
- `calendar` — Google Calendar API
- `browser` — Playwright-based web automation
- `media` — mpv IPC
- `files` — filesystem operations
- `clipboard` — clipboard access
- `system` — system info
- `http` — generic HTTP requests
- `vision` — screenshot + OCR + describe

### Adapter Registration

```python
# In friday/core/registry.py
friday.register_adapter(WhatsAppAdapter(token=os.environ["WHATSAPP_TOKEN"]))
friday.register_adapter(TelegramAdapter(token=os.environ["TELEGRAM_TOKEN"]))
```

## Layer 7: API (friday.api)

Proper HTTP API, not hand-rolled.

### Framework
- **FastAPI** — async, auto-docs, type-safe, production-ready
- **WebSocket** — real-time event streaming
- **JWT auth** — proper authentication
- **CORS** — proper cross-origin support

### Endpoints

```
POST   /v1/goals              Execute a goal
GET    /v1/goals/{id}         Get goal status
GET    /v1/goals              List recent goals
GET    /v1/status             System health
GET    /v1/memory             Query memory
POST   /v1/memory             Store a memory
GET    /v1/patterns           Detected patterns
GET    /v1/predictions        Current predictions
GET    /v1/adapter/{name}     Adapter status
POST   /v1/adapter/{name}/action  Direct adapter call
WS     /ws/events             Real-time event stream
```

### Dashboard
- Modern SPA (React/Vue/Svelte — pick one)
- Real-time goal execution visualization
- Memory browser
- Pattern/prediction viewer
- Adapter management
- Settings and configuration

## Event Flow

```
User: "Summarize my unread emails"
  │
  ▼
[API] receives POST /v1/goals
  │
  ▼
[Brain] planner.build_context(goal)
  │  ← [Memory] recalls: "user checks email at 9am, prefers Telegram"
  │  ← [Observer] notes: "it's 9:05am, user just opened terminal"
  │  ← [Context] sees: "3 unread emails, 1 from boss"
  │
  ▼
[Brain] planner.plan(goal, context)
  │  ← calls Claude CLI via dev.run
  │  ← validates plan schema
  │  ← scores confidence: 0.92
  │
  ▼
[Brain] executor.run_plan(plan)
  │  step 1: gmail.list_unread(max_results=5)
  │    → [Core] event: PRIMITIVE_CALL(gmail.list_unread)
  │    → [Core] observability: L0 log line
  │    → [Adapter] gmail.execute("list_unread", max_results=5)
  │    → result: [{message_id, sender, subject, ...}]
  │    → verify: checks.gmail_unread_exists ✓
  │    → [Core] event: STEP_COMPLETE(step=1, status=VERIFIED)
  │
  │  step 2: gmail.get_message(message_id=$steps.1.result.0.message_id)
  │    → ... same flow ...
  │
  │  step 3: gmail.summarize(message_id=...)
  │    → ... same flow ...
  │
  ▼
[Brain] executor.complete(result)
  │  → [Memory] store: episodic("summarized 3 emails at 9:05")
  │  → [Memory] store: procedural("email summary → gmail flow")
  │  → [Observer] detect: "user asked for email summary at 9:05 again"
  │
  ▼
[Comms] proactive.send(
    channel=telegram,  ← learned preference
    message="📧 3 unread emails:\n• Boss: Q3 report due Friday\n...",
    confidence=0.95
  )
  │
  ▼
[Core] event: GOAL_COMPLETE(goal, duration=4.2s, confidence=0.92)
```

## What We Keep From V8

| Module | Verdict | Reason |
|--------|---------|--------|
| contracts.py | **KEEP** | Elegant, proven |
| errors.py | **KEEP** | Good hierarchy |
| observability.py | **KEEP** | Structured logging works |
| L3 executor | **KEEP + adapt** | State machine is solid |
| L4 planner (validate_plan) | **KEEP + adapt** | Schema validation is good |
| L2 checks | **KEEP** | Read-only verification pattern |
| window.py | **KEEP** | Hyprland IPC works |
| media.py | **KEEP** | mpv IPC works |
| files.py | **KEEP** | Deterministic file ops |
| browser.py | **KEEP** | Playwright integration |
| gmail.py | **KEEP** | OAuth2 flow works |
| calendar.py | **KEEP** | OAuth2 flow works |
| clipboard.py | **KEEP** | Cross-platform clipboard |
| telegram.py | **KEEP** | Bot API works |
| discord.py | **KEEP** | Bot API works |
| whatsapp.py | **KEEP** | Cloud API works |
| screenshot.py | **KEEP** | grim/PIL works |
| vision.py | **KEEP** | OCR + LLM describe |
| notify.py | **KEEP** | Desktop notifications |
| system.py | **KEEP** | fastfetch integration |
| git.py | **KEEP** | Read-only git ops |
| dev.py | **KEEP + adapt** | Claude CLI substrate |
| secrets.py | **KEEP** | pass-based creds |
| templates.py | **REBUILD** | 50 copy-paste templates → deduplicated pattern system |
| watcher.py | **REBUILD** | Polling → event-driven |
| api_server.py | **REBUILD** | Hand-rolled → FastAPI |
| dashboard.html | **REBUILD** | Static → SPA |
| mcp_server.py | **REBUILD** | Hand-rolled → proper MCP SDK |
| capability_gaps.py | **REBUILD** | File-based → event-driven learning |
| gap_triage.py | **REBUILD** | Paperwork → real analysis |
| automated_gate.py | **KEEP concept** | AST checks are good |
| register_proposal.py | **KEEP concept** | Human approval gate is good |
| lessons.py | **REBUILD** | Prompt injection → vector memory |
| goal_proposals.py | **REBUILD** | Failure mining → pattern-based prediction |
| suggestions.py | **REBUILD** | Statistical → predictive |

## What We Cut

- 50+ copy-paste templates (one template = one pattern)
- 4 retired ambient-gap-probe triggers (dead code)
- Windows ctypes stubs (not functional, adds confusion)
- `gates/` directory of proof files (replace with proper CI/CD)
- `gates/proposed_primitives/` (replaced by adapter model)
- `gates/proposed_triggers/` (replaced by observer predictions)

## Development Phases

### Phase 1: Foundation (Week 1)
- [ ] Create `friday-core` package
- [ ] Port contracts, errors, observability
- [ ] Build event bus
- [ ] Build registry + adapter interface
- [ ] Write tests

### Phase 2: Brain (Week 2)
- [ ] Port executor (adapted from V8 L3)
- [ ] Port planner (adapted from V8 L4)
- [ ] Build context system
- [ ] Build reasoning layer
- [ ] Write tests

### Phase 3: Memory (Week 3)
- [ ] Build working memory
- [ ] Build episodic memory (JSONL)
- [ ] Build semantic memory (retrieval)
- [ ] Build procedural memory (plan patterns)
- [ ] Write tests

### Phase 4: Observer (Week 4)
- [ ] Build pattern detection
- [ ] Build prediction engine
- [ ] Build user model
- [ ] Build anomaly detection
- [ ] Write tests

### Phase 5: First Integrations (Week 5)
- [ ] WhatsApp adapter
- [ ] Telegram adapter
- [ ] Gmail adapter
- [ ] Media adapter
- [ ] Write integration tests

### Phase 6: API + UI (Week 6)
- [ ] FastAPI server
- [ ] WebSocket event streaming
- [ ] Dashboard SPA
- [ ] Authentication
- [ ] Write API tests

### Phase 7: Learning Loop (Week 7)
- [ ] Pattern → prediction → action → feedback loop
- [ ] Success/failure recording
- [ ] Behavioral adaptation
- [ ] Proactive communication

### Phase 8: Polish (Week 8)
- [ ] Documentation
- [ ] Deployment (Docker, systemd)
- [ ] Monitoring
- [ ] Onboarding flow

## Success Metrics

1. **Response time**: Goal → first action < 5s
2. **Reliability**: 95%+ goal completion rate
3. **Learning**: Measurable improvement in plan quality over time
4. **Proactivity**: At least 1 unsolicited useful action per day
5. **Memory**: Can recall and use information from previous sessions
6. **Adaptation**: Adjusts behavior based on user feedback
