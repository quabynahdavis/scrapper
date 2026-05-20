"""
Registry that manages available source adapters.

Sources are ordered by priority (highest first) so that the most
reliable sources are queried first.
"""

from __future__ import annotations

from typing import Optional

from .base import SourceAdapter


class SourceRegistry:
    """Manages registration, discovery and ordering of source adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, SourceAdapter] = {}

    # ------------------------------------------------------------------
    # Registration
    # ------------------------------------------------------------------

    def register(self, adapter: SourceAdapter) -> None:
        """Register a source adapter.

        Args:
            adapter: An instance of a SourceAdapter subclass.

        Raises:
            ValueError: If an adapter with the same name is already registered.
        """
        if adapter.name in self._adapters:
            raise ValueError(
                f"Source '{adapter.name}' is already registered."
            )
        self._adapters[adapter.name] = adapter

    def unregister(self, name: str) -> None:
        """Remove a previously registered source adapter.

        Args:
            name: The source name to remove.
        """
        self._adapters.pop(name, None)

    # ------------------------------------------------------------------
    # Querying
    # ------------------------------------------------------------------

    def get(self, name: str) -> Optional[SourceAdapter]:
        """Get a specific adapter by name.

        Returns:
            The adapter, or None if not registered.
        """
        return self._adapters.get(name)

    def get_all(self) -> list[SourceAdapter]:
        """Return all registered adapters (unordered)."""
        return list(self._adapters.values())

    def get_by_priority(self) -> list[SourceAdapter]:
        """Return all adapters sorted by priority (highest first)."""
        return sorted(
            self._adapters.values(),
            key=lambda a: a.priority,
            reverse=True,
        )

    def get_by_names(self, names: list[str]) -> list[SourceAdapter]:
        """Return adapters matching the given names, in priority order.

        Args:
            names: Source names to filter by.

        Returns:
            Matching adapters sorted by priority (highest first).
        """
        adapters = [
            self._adapters[n] for n in names if n in self._adapters
        ]
        return sorted(adapters, key=lambda a: a.priority, reverse=True)

    # ------------------------------------------------------------------
    # Introspection
    # ------------------------------------------------------------------

    @property
    def count(self) -> int:
        """Number of registered adapters."""
        return len(self._adapters)

    def __repr__(self) -> str:
        names = ", ".join(self._adapters)
        return f"SourceRegistry({names})"
