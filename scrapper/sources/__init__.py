"""Source adapters for fetching song audio from various platforms."""

from .base import SourceAdapter
from .registry import SourceRegistry

__all__ = [
    "SourceAdapter",
    "SourceRegistry",
]
