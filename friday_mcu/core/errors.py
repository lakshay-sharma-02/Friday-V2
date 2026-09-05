"""Exception hierarchy for MCU Friday.

Every layer raises from this tree so the event bus and executor can
classify failures without string-matching on messages.
"""


class FridayError(Exception):
    """Base class for all Friday errors."""


class PrimitiveError(FridayError):
    """A primitive call failed at the backing-mechanism level.

    `state` documents what is known about the world left behind on partial
    failure, per the primitive's contract.
    """

    def __init__(self, message: str, *, state: str | None = None):
        super().__init__(message)
        self.state = state


class PreconditionError(FridayError):
    """The caller violated a primitive's documented precondition.

    This is a caller bug, not a system failure, and is never retried.
    """


class PrimitiveTimeout(FridayError):
    """A primitive exceeded its allowed time budget."""

    def __init__(self, message: str, *, state: str | None = None):
        super().__init__(message)
        self.state = state


class PlanError(FridayError):
    """The planner produced an invalid or unexecutable plan."""


class ValidationError(FridayError):
    """Schema validation failed (plan, config, or event)."""


class AdapterError(FridayError):
    """An adapter failed to communicate with its backing service."""


class MemoryError(FridayError):
    """A memory operation failed."""


class LearningError(FridayError):
    """A learning/pattern-detection operation failed."""


class ConfidenceError(FridayError):
    """Action rejected due to insufficient confidence."""
