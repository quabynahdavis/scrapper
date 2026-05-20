"""
Download Manager — concurrent downloads with retry, rate limiting, and progress tracking.

Manages the reliable transfer of files from source adapters to the local filesystem.
"""

from __future__ import annotations

import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Callable, Optional

from .models import DownloadResult, SearchResult
from .sources.base import SourceAdapter

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Callback types
# ---------------------------------------------------------------------------

ProgressCallback = Callable[[int, int, DownloadResult], None]
"""Signature: (completed_count, total_count, latest_result) -> None"""


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class DownloadConfig:
    """Configuration for the download manager."""

    max_concurrent: int = 3        # max simultaneous downloads
    max_retries: int = 3           # retries per file
    base_delay: float = 1.0        # initial backoff seconds
    timeout: int = 60              # per-file timeout (seconds)
    rate_limits: dict[str, float] = field(default_factory=dict)
    # per-source rate limits: {"youtube": 1.0, "spotify": 0.5, ...}


# ---------------------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------------------


class _RateLimiter:
    """Per-source rate limiter using a simple token bucket approach."""

    def __init__(self) -> None:
        self._locks: dict[str, threading.Lock] = {}
        self._last_calls: dict[str, float] = {}

    def wait(self, source: str, min_interval: float) -> None:
        """Block until the minimum interval for *source* has elapsed."""
        if source not in self._locks:
            self._locks[source] = threading.Lock()
            self._last_calls[source] = 0.0

        with self._locks[source]:
            elapsed = time.time() - self._last_calls[source]
            if elapsed < min_interval:
                sleep_for = min_interval - elapsed
                logger.debug(
                    "Rate limiting '%s': sleeping %.2fs", source, sleep_for
                )
                time.sleep(sleep_for)
            self._last_calls[source] = time.time()


# ---------------------------------------------------------------------------
# Core download manager
# ---------------------------------------------------------------------------


class DownloadManager:
    """Manages concurrent downloads with retries and rate limiting."""

    def __init__(self, config: Optional[DownloadConfig] = None) -> None:
        self.config = config or DownloadConfig()
        self._rate_limiter = _RateLimiter()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(
        self,
        result: SearchResult,
        source_adapter: SourceAdapter,
        dest_dir: str = "./data/raw",
        progress_callback: Optional[ProgressCallback] = None,
    ) -> DownloadResult:
        """Download a single search result with retries.

        Args:
            result: The search result to download.
            source_adapter: The adapter that produced this result.
            dest_dir: Root download directory.
            progress_callback: Optional progress callback.

        Returns:
            A DownloadResult with the outcome.
        """
        last_error: Optional[str] = None

        for attempt in range(1, self.config.max_retries + 1):
            # Rate limit
            min_interval = self.config.rate_limits.get(
                source_adapter.name, 0.0
            )
            self._rate_limiter.wait(source_adapter.name, min_interval)

            try:
                dl_result = source_adapter.download(result, dest_dir)
            except Exception as exc:
                dl_result = DownloadResult(
                    result=result,
                    file_path="",
                    success=False,
                    error=str(exc),
                )

            if dl_result.success:
                if progress_callback:
                    progress_callback(1, 1, dl_result)
                return dl_result

            last_error = dl_result.error

            if attempt < self.config.max_retries:
                delay = self.config.base_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Download attempt %d/%d failed for '%s': %s. "
                    "Retrying in %.1fs…",
                    attempt,
                    self.config.max_retries,
                    result.title,
                    last_error,
                    delay,
                )
                time.sleep(delay)

        # All retries exhausted
        failed = DownloadResult(
            result=result,
            file_path="",
            success=False,
            error=last_error or "Unknown error",
        )
        if progress_callback:
            progress_callback(1, 1, failed)
        return failed

    def download_many(
        self,
        items: list[tuple[SearchResult, SourceAdapter]],
        dest_dir: str = "./data/raw",
        progress_callback: Optional[ProgressCallback] = None,
    ) -> list[DownloadResult]:
        """Download multiple results concurrently.

        Args:
            items: List of (SearchResult, SourceAdapter) pairs.
            dest_dir: Root download directory.
            progress_callback: Optional callback invoked after each download.

        Returns:
            List of DownloadResults in the same order as *items*.
        """
        total = len(items)
        results: list[DownloadResult] = [None] * total  # type: ignore
        completed = 0
        lock = threading.Lock()

        def _work(index: int, result: SearchResult, adapter: SourceAdapter) -> int:
            nonlocal completed
            dl = self.download(result, adapter, dest_dir)
            with lock:
                results[index] = dl
                completed += 1
                if progress_callback:
                    progress_callback(completed, total, dl)
            return index

        with ThreadPoolExecutor(max_workers=self.config.max_concurrent) as pool:
            futures = {
                pool.submit(_work, i, res, adap): i
                for i, (res, adap) in enumerate(items)
            }
            for future in as_completed(futures):
                # Exceptions inside _work are caught and converted to DownloadResult
                try:
                    future.result()
                except Exception as exc:
                    idx = futures[future]
                    with lock:
                        results[idx] = DownloadResult(
                            result=items[idx][0],
                            file_path="",
                            success=False,
                            error=str(exc),
                        )
                        completed += 1

        return results  # type: ignore[return-value]
