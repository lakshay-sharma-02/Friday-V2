"""Friday V8 - layered desktop automation.

Layer map:
    L0  Observability  (structured logging)      -- Gate 2
    L1  Primitives     (window/media/browser/dev/files/whatsapp/telegram/discord)
                                                  -- Gate 1, every executor-
                                                  callable primitive proven
    L2  Verification   (read-only state checks)   -- Gate 3
    L3  Execution      (deterministic runner)     -- Gate 4
    L4  Planning       (LLM: goal -> plan JSON)   -- Gate 5

All gates G1-G6 proven with raw output; 13 composite tasks on record in
var/logs/tasks.jsonl. window.shutdown is blocked from the executor
(EXECUTOR_BLOCKED) and vision is deferred by design. The ambient watch
loop (friday/watcher.py) turns config/ triggers into background goals.
"""

__version__ = "0.8.0"
