"""
scrapper — Song audio scraper.

Fetches MP3, MIDI, and other audio formats from multiple sources
given a song name and optional artist.

Usage:
    from scrapper import SongScraper

    scraper = SongScraper()
    results = scraper.search("Bohemian Rhapsody", artist="Queen")
    downloaded = scraper.download_best(results)
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import yaml

from .downloader import DownloadConfig, DownloadManager
from .exceptions import ConfigurationError
from .models import AudioFormat, DownloadResult, SearchResult
from .organizer import FileOrganizer
from .sources import (
    AppleMusicSource,
    AudiomackSource,
    MIDISource,
    SourceAdapter,
    SourceRegistry,
    SpotifySource,
    YouTubeSource,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Default sources — registered in priority order
# ---------------------------------------------------------------------------

_DEFAULT_SOURCES: list[type[SourceAdapter]] = [
    YouTubeSource,
    SpotifySource,
    AudiomackSource,
    AppleMusicSource,
    MIDISource,
]


class SongScraper:
    """High-level orchestrator that ties together sources, downloads, and file organisation.

    Args:
        config_path: Path to a YAML configuration file. If not provided,
                     defaults are used.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config = self._load_config(config_path)
        self.registry = SourceRegistry()
        self._register_sources()
        self.download_manager = DownloadManager(
            config=DownloadConfig(
                max_concurrent=self.config.get(
                    "download", {}).get("max_concurrent", 3),
                max_retries=self.config.get(
                    "download", {}).get("max_retries", 3),
                timeout=self.config.get("download", {}).get("timeout", 60),
                rate_limits=self._build_rate_limits(),
            )
        )
        self.organizer = FileOrganizer(
            base_dir=self.config.get("download", {}).get(
                "directory", "./data/raw")
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
        sources: Optional[list[str]] = None,
        formats: Optional[list[AudioFormat]] = None,
    ) -> list[SearchResult]:
        """Search for a song across all enabled sources.

        Args:
            song: Song name to search for (required).
            artist: Optional artist name to narrow results.
            sources: Optional list of source names to restrict search to.
            formats: Optional list of audio formats to filter by.

        Returns:
            A list of SearchResult objects, sorted by relevance score (descending).

        Raises:
            ValueError: If *song* is empty.
        """
        if not song or not song.strip():
            raise ValueError("Song name must not be empty")

        adapters = (
            self.registry.get_by_names(sources)
            if sources
            else self.registry.get_by_priority()
        )

        # Filter enabled sources from config
        enabled_names = self._enabled_source_names()
        adapters = [a for a in adapters if a.name in enabled_names]

        all_results: list[SearchResult] = []
        for adapter in adapters:
            try:
                results = adapter.search(song, artist=artist)
                all_results.extend(results)
            except Exception as exc:
                logger.warning(
                    "Source '%s' search failed: %s", adapter.name, exc
                )

        # Deduplicate by URL (keep highest score)
        seen_urls: set[str] = set()
        unique: list[SearchResult] = []
        for r in sorted(all_results, key=lambda x: x.score, reverse=True):
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                unique.append(r)

        # Filter by format if specified
        if formats:
            unique = [r for r in unique if r.format in formats]

        # Sort by score descending
        unique.sort(key=lambda x: x.score, reverse=True)

        return unique

    def download_best(
        self,
        results: list[SearchResult],
        dest_dir: Optional[str] = None,
    ) -> DownloadResult:
        """Download the highest-scored result.

        Args:
            results: List of search results (e.g. from :meth:`search`).
            dest_dir: Override the default download directory.

        Returns:
            A DownloadResult for the attempted download.
        """
        if not results:
            return DownloadResult(
                result=SearchResult(
                    title="",
                    artist=None,
                    duration=0,
                    format=AudioFormat.MP3,
                    quality="medium",  # type: ignore
                    source="",
                    url="",
                ),
                file_path="",
                success=False,
                error="No results to download",
            )

        best = results[0]
        adapter = self.registry.get(best.source)
        if not adapter:
            return DownloadResult(
                result=best,
                file_path="",
                success=False,
                error=f"No adapter registered for source '{best.source}'",
            )

        dest = dest_dir or self.organizer.base_dir
        dl_result = self.download_manager.download(
            best, adapter, dest_dir=dest)
        return self.organizer.organise(dl_result)

    def download_all(
        self,
        results: list[SearchResult],
        dest_dir: Optional[str] = None,
        max_concurrent: Optional[int] = None,
    ) -> list[DownloadResult]:
        """Download all results concurrently.

        Args:
            results: List of search results.
            dest_dir: Override the default download directory.
            max_concurrent: Override max concurrent downloads.

        Returns:
            List of DownloadResults, one per input result.
        """
        if not results:
            return []

        if max_concurrent is not None:
            self.download_manager.config.max_concurrent = max_concurrent

        items: list[tuple[SearchResult, SourceAdapter]] = []
        for result in results:
            adapter = self.registry.get(result.source)
            if adapter:
                items.append((result, adapter))
            else:
                logger.warning(
                    "No adapter for source '%s', skipping", result.source)

        dest = dest_dir or self.organizer.base_dir
        dl_results = self.download_manager.download_many(items, dest_dir=dest)

        # Organise each successful download
        organised: list[DownloadResult] = []
        for dl in dl_results:
            organised.append(self.organizer.organise(dl))

        return organised

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    @staticmethod
    def _load_config(config_path: Optional[str] = None) -> dict:
        """Load YAML configuration file."""
        if config_path is None:
            # Try default locations
            candidates = [
                "config/scraper.yaml",
                "config/scraper.yml",
                os.path.expanduser("~/.config/scrapper/config.yaml"),
                os.path.expanduser("~/.config/scrapper/config.yml"),
            ]
            for path in candidates:
                if os.path.isfile(path):
                    config_path = path
                    break

        if config_path and os.path.isfile(config_path):
            try:
                with open(config_path, "r") as f:
                    return yaml.safe_load(f) or {}
            except Exception as exc:
                logger.warning("Failed to load config '%s': %s",
                               config_path, exc)

        return {}

    def _register_sources(self) -> None:
        """Register all source adapters."""
        for source_cls in _DEFAULT_SOURCES:
            try:
                adapter = source_cls()
                self.registry.register(adapter)
            except Exception as exc:
                logger.warning(
                    "Failed to register source '%s': %s",
                    source_cls.__name__,
                    exc,
                )

    def _enabled_source_names(self) -> set[str]:
        """Return the set of source names that are enabled in config."""
        sources_cfg = self.config.get("sources", {})
        enabled = set()
        for name, cfg in sources_cfg.items():
            if cfg.get("enabled", True):
                enabled.add(name)
        # If config is empty / has no source entries, enable all
        if not enabled:
            enabled = {a.name for a in self.registry.get_all()}
        return enabled

    def _build_rate_limits(self) -> dict[str, float]:
        """Build per-source rate limits from config."""
        sources_cfg = self.config.get("sources", {})
        limits: dict[str, float] = {}
        for name, cfg in sources_cfg.items():
            if "rate_limit" in cfg:
                limits[name] = float(cfg["rate_limit"])
        return limits


__all__ = [
    "SongScraper",
    "SearchResult",
    "DownloadResult",
    "AudioFormat",
    "Quality",
    "SourceRegistry",
    "SourceAdapter",
]
