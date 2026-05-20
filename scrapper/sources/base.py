"""
Abstract base class for all source adapters.

Each source adapter must implement:
- name        : unique identifier for the source
- priority    : search order (higher = checked first)
- search()    : find matching songs
- download()  : download a specific search result
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from ..models import SearchResult, DownloadResult


class SourceAdapter(ABC):
    """Base class for all audio source adapters.

    Subclasses MUST set:
      name     – unique source identifier (e.g. 'youtube', 'spotify')
      priority – search order (higher = checked first)
    """

    name: str = ""
    priority: int = 0

    @abstractmethod
    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list[SearchResult]:
        """Search the source for matching songs.

        Args:
            song: Song title to search for.
            artist: Optional artist name to narrow results.

        Returns:
            A list of SearchResult objects, ordered by relevance.
        """
        ...

    @abstractmethod
    def download(
        self,
        result: SearchResult,
        dest_dir: str,
    ) -> DownloadResult:
        """Download the file for a given search result.

        Args:
            result: The search result to download.
            dest_dir: Directory where the file should be saved.

        Returns:
            A DownloadResult describing the outcome.
        """
        ...
