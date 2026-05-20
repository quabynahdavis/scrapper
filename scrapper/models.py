"""
Data models for song search results and download outcomes.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class AudioFormat(str, Enum):
    """Supported audio file formats."""

    MP3 = "mp3"
    MIDI = "midi"
    M4A = "m4a"
    WAV = "wav"
    FLAC = "flac"
    WEBM = "webm"
    OPUS = "opus"

    def __str__(self) -> str:
        return self.value


class Quality(str, Enum):
    """Audio quality tiers."""

    LOW = "low"           # < 96 kbps
    MEDIUM = "medium"     # 96–192 kbps
    HIGH = "high"         # 192–320 kbps
    LOSSLESS = "lossless"

    def __str__(self) -> str:
        return self.value


@dataclass
class SearchResult:
    """A single search result found by a source adapter."""

    title: str
    artist: Optional[str]
    duration: int                     # seconds
    format: AudioFormat
    quality: Quality
    source: str                       # e.g. "youtube", "spotify"
    url: str                          # download / stream URL
    file_size: Optional[int] = None   # bytes
    score: float = 0.0                # relevance 0.0–1.0
    metadata: dict = field(default_factory=dict)


@dataclass
class DownloadResult:
    """Outcome of a single file download attempt."""

    result: SearchResult
    file_path: str
    success: bool
    error: Optional[str] = None
