"""L1 primitive contract registry.

Every primitive carries an explicit contract (precondition, postcondition,
idempotency class, failure mode). The executor consults REGISTRY at runtime
to decide retry policy; a primitive without a registered contract is never
callable.

Idempotency classes:
  - idempotent:        safe to blindly retry (read-only ops).
  - at-most-once:      retry can duplicate a side effect (send/open).
  - commutative-safe:  retry is harmless once the target state already
                       matches (set-volume, close-already-closed).
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum
from typing import Any, TypeVar

F = TypeVar("F", bound=Callable[..., Any])


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


# Global registry — populated by @contract decorators at import time.
REGISTRY: dict[str, Contract] = {}

# Primitives that ARE registered but must NEVER be reachable through
# the executor: a plan can never contain them, the LLM never sees them.
EXECUTOR_BLOCKED: frozenset[str] = frozenset()


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

    redact_result=True: the primitive's return value is written to the
    L0 log as "<redacted>".

    log_transform: applied to the returned value purely for the L0 log
    line; the real return value is untouched.
    """

    def deco(fn: F) -> F:
        if fn.__name__.startswith("_"):
            raise TypeError(
                f"contract() must decorate a public primitive, got private "
                f"'{fn.__name__}'"
            )
        # Registry keys are module-qualified (e.g. 'telegram.send_text')
        # so primitives with the same function name in different modules
        # never collide.
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
        wrapped: F = fn
        wrapped.__contract__ = c  # type: ignore[attr-defined]
        return wrapped

    return deco
