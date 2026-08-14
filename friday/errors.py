"""Exception hierarchy for Friday.

Every layer raises from this tree so L0/L3 can classify failures without
string-matching on messages.
"""


class FridayError(Exception):
    """Base class for all Friday errors."""


class PrimitiveError(FridayError):
    """A primitive call failed at the backing-mechanism level (subprocess,
    IPC socket, browser, etc.).

    `state` documents what is known about the world left behind on partial
    failure, per the primitive's contract. This is the detail that hides
    silent corruption if skipped, so every raise site fills it in.
    """

    def __init__(self, message: str, *, state: str | None = None):
        super().__init__(message)
        self.state = state


class PreconditionError(FridayError):
    """The caller violated a primitive's documented precondition. This is a
    caller bug, not a system failure, and is never retried."""


class PrimitiveTimeout(FridayError):
    """A primitive exceeded its allowed time budget.

    `state` documents what is known about the world left behind on partial
    failure, per the primitive's contract - the same contract as
    PrimitiveError. REGRESSION (2026-08-13, found LIVE by the triage repair
    loop): this class inherited FridayError's bare Exception init, so every
    raise site passing `state=` (dev.py claude timeout, window.py hyprctl
    timeout) crashed with "PrimitiveTimeout() takes no keyword arguments"
    instead of raising the intended timeout - a timeout surfaced as a
    confusing TypeError that hid the real cause."""

    def __init__(self, message: str, *, state: str | None = None):
        super().__init__(message)
        self.state = state
