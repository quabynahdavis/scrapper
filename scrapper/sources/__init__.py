"""Source adapters for fetching song audio from various platforms."""

from .apple_music import AppleMusicSource
from .audiomack import AudiomackSource
from .base import SourceAdapter
from .midi_db import MIDISource
from .registry import SourceRegistry
from .spotify import SpotifySource
from .youtube import YouTubeSource

__all__ = [
    "SourceAdapter",
    "SourceRegistry",
    "YouTubeSource",
    "SpotifySource",
    "AudiomackSource",
    "AppleMusicSource",
    "MIDISource",
]
