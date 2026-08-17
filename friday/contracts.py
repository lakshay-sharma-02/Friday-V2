"""L1 primitive contract registry.

Every primitive carries an explicit contract (precondition, postcondition,
idempotency class, failure mode). L3 consults REGISTRY at runtime to decide
retry policy; a primitive without a registered contract is never callable
by the executor.

Idempotency classes (from the V8 master plan):
  - idempotent:        safe to blindly retry (read-only ops).
  - at-most-once:      retry can duplicate a side effect (send/open).
  - commutative-safe:  retry is harmless once the target state already
                       matches (set-volume, close-already-closed).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

# Generic bound so a @contract-decorated primitive KEEPS its real signature
# for typecheckers - a bare-Callable decorator would make every primitive
# (and its return type) Any, which is how the first strict-mypy run failed
# (list_clients() was Any, so every caller of it was 'returning Any').
F = TypeVar("F", bound=Callable[..., Any])
from enum import Enum
from typing import Any

from friday.observability import observe


class Idempotency(Enum):
    IDEMPOTENT = "idempotent"
    AT_MOST_ONCE = "at-most-once"
    COMMUTATIVE_SAFE = "commutative-safe"


@dataclass(frozen=True)
class Contract:
    name: str
    precondition: str
    postcondition: str
    idempotency: Idempotency
    failure_mode: str
    returns: str = ""


REGISTRY: dict[str, Contract] = {}

# Primitives that ARE registered (their contracts, docs and direct calls
# stay intact) but must NEVER be reachable through the executor or the
# planner's catalog: a plan can never contain them, the LLM never sees
# them, and L3 refuses them. 'window.shutdown' ends the Hyprland session -
# destructive, with no legitimate plan path. Deferred-by-design becomes
# mechanically enforced here, not convention.
EXECUTOR_BLOCKED: frozenset[str] = frozenset({"window.shutdown"})


def contract(
    *,
    precondition: str = "",
    postcondition: str = "",
    idempotency: Idempotency = Idempotency.AT_MOST_ONCE,
    failure_mode: str = "",
    returns: str = "",
    redact_result: bool = False,
    log_transform: Callable[[Any], Any] | None = None,
) -> Callable[[F], F]:
    """Decorator that registers a Contract for the wrapped primitive.

    redact_result=True: the primitive's returned value is written to the
    L0 log as "<redacted>" (e.g. credentials() returns the credentials
    dict itself - the whole result is a secret, not just a nested key).

    log_transform: applied to the returned value purely for the L0 log
    line (redact selected fields / compact a large result); the real
    return value - the one the executor stores and plans reference - is
    untouched. See friday.observability.observe.
    """

    def deco(fn: F) -> F:
        if fn.__name__.startswith("_"):
            raise TypeError(
                f"contract() must decorate a public primitive, got private "
                f"'{fn.__name__}' - a misplaced decorator would silently "
                "mislabel the registry"
            )
        # Registry keys are module-qualified (e.g. 'telegram.send_text') so
        # that primitives with the same function name in different modules
        # (whatsapp/telegram/discord all have send_text) never collide - a
        # bare-name key would let one silently overwrite the other, and L3
        # would have no way to pick the right platform.
        module = fn.__module__.rsplit(".", 1)[-1]
        qualified = f"{module}.{fn.__name__}"
        c = Contract(
            name=qualified,
            precondition=precondition,
            postcondition=postcondition,
            idempotency=idempotency,
            failure_mode=failure_mode,
            returns=returns,
        )
        REGISTRY[qualified] = c
        # L0: wrap every contract-registered primitive with the observability
        # decorator. One choke point instruments all primitives - Gate 2's
        # explicit requirement (no per-call-site instrumentation).
        # observe is itself generic over F, so the wrapped function keeps
        # its declared signature for typecheckers
        wrapped: F = observe(redact_result=redact_result, log_transform=log_transform)(fn)
        # runtime attribute the executor checks before dispatch; type:
        # ignore because F is bound to Callable, which has no such attr
        wrapped.__contract__ = c  # type: ignore[attr-defined]
        return wrapped

    return deco
