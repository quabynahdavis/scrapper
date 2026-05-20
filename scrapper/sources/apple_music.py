"""
Apple Music / iTunes source adapter.

Uses the public iTunes Search API to find songs and fetch 30-second
M4A preview clips. No authentication required.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

import httpx

from ..models import AudioFormat, DownloadResult, Quality, SearchResult
from .base import SourceAdapter

logger = logging.getLogger(__name__)

ITUNES_SEARCH_URL = "https://itunes.apple.com/search"


class AppleMusicSource(SourceAdapter):
    """Search Apple Music (iTunes) and download 30-second M4A previews."""

    name = "apple_music"
    priority = 80

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list[SearchResult]:
        term = f"{song} {artist}".strip() if artist else song
        params = {
            "term": term,
            "media": "music",
            "limit": 10,
        }

        try:
            resp = httpx.get(
                ITUNES_SEARCH_URL,
                params=params,
                headers={"Accept": "application/json"},
                timeout=15,
            )
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Apple Music search failed for '%s': %s", term, exc)
            return []

        results: list[SearchResult] = []
        for item in data.get("results", []):
            preview_url = item.get("previewUrl")
            if not preview_url:
                continue

            results.append(
                SearchResult(
                    title=item.get("trackName", "Unknown"),
                    artist=item.get("artistName"),
                    duration=int(item.get("trackTimeMillis", 0) / 1000),
                    format=AudioFormat.M4A,
                    quality=Quality.MEDIUM,
                    source=self.name,
                    url=preview_url,
                    file_size=None,
                    score=self._compute_score(item),
                    metadata={
                        "itunes_id": item.get("trackId"),
                        "album": item.get("collectionName"),
                        "genre": item.get("primaryGenreName"),
                        "release_date": item.get("releaseDate"),
                        "track_number": item.get("trackNumber"),
                    },
                )
            )

        return results

    def download(
        self,
        result: SearchResult,
        dest_dir: str,
    ) -> DownloadResult:
        artist_dir = self._sanitize(result.artist or "Unknown")
        song_file = self._sanitize(result.title)
        filename = f"{song_file}--apple_music.m4a"
        dest_path = os.path.join(dest_dir, "m4a", artist_dir, filename)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        try:
            resp = httpx.get(result.url, timeout=30)
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(resp.content)
        except Exception as exc:
            logger.error(
                "Apple Music download failed for '%s': %s", result.url, exc
            )
            return DownloadResult(
                result=result,
                file_path="",
                success=False,
                error=str(exc),
            )

        return DownloadResult(result=result, file_path=dest_path, success=True)

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_score(item: dict) -> float:
        """Score based on track price and collection price (heuristic)."""
        # Tracks with higher prices or collection prices rank slightly better
        track_price = item.get("trackPrice") or 0
        collection_price = item.get("collectionPrice") or 0
        score = min(1.0, (track_price + collection_price) / 5.0)
        return round(score, 2)

    @staticmethod
    def _sanitize(name: str) -> str:
        """Remove characters problematic for filenames."""
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()
