"""Friday Adapters — each integration is a self-contained plugin.

Every adapter implements the Adapter ABC and registers its primitives
via the @contract decorator.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from friday_mcu.core.events import Event


class Adapter(ABC):
    """Base class for all Friday adapters.

    Each adapter wraps an external service or capability and exposes
    it through the standard primitive interface.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique adapter name (e.g. 'whatsapp', 'gmail')."""
        ...

    @property
    @abstractmethod
    def capabilities(self) -> list[str]:
        """List of capability strings this adapter provides."""
        ...

    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the adapter (connect, authenticate, etc.)."""
        ...

    @abstractmethod
    async def execute(self, action: str, **kwargs: Any) -> Any:
        """Execute an adapter-specific action."""
        ...

    @abstractmethod
    async def observe(self) -> list[Event]:
        """Poll for new events from this adapter (inbound messages, etc.)."""
        ...

    def health_check(self) -> bool:
        """Check if the adapter is healthy. Override if needed."""
        return True

    def shutdown(self) -> None:
        """Clean up resources. Override if needed."""
        pass


# Adapter registry
_ADAPTERS: dict[str, Adapter] = {}


def register_adapter(adapter: Adapter) -> None:
    """Register an adapter instance."""
    _ADAPTERS[adapter.name] = adapter


def get_adapter(name: str) -> Adapter | None:
    """Get a registered adapter by name."""
    return _ADAPTERS.get(name)


def list_adapters() -> dict[str, Adapter]:
    """List all registered adapters."""
    return dict(_ADAPTERS)
