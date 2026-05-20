"""
sgpt-identifier — Song audio scraper.

Fetches MP3, MIDI, and other audio formats from multiple sources
given a song name and optional artist.
"""

from .models import SearchResult, DownloadResult, AudioFormat, Quality
from .sources import SourceRegistry
from .sources.base import SourceAdapter

__all__ = [
    "SearchResult",
    "DownloadResult",
    "AudioFormat",
    "Quality",
    "SourceRegistry",
    "SourceAdapter",
]
