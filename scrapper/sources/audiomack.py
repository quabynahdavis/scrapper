"""
Audiomack source adapter.

Scrapes audiomack.com for full-length MP3 downloads.
Uses HTTP requests + BeautifulSoup for HTML parsing.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

import httpx
from bs4 import BeautifulSoup

from ..models import AudioFormat, DownloadResult, Quality, SearchResult
from .base import SourceAdapter

logger = logging.getLogger(__name__)

SEARCH_URL = "https://audiomack.com/search"
USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class AudiomackSource(SourceAdapter):
    """Search Audiomack and download MP3 files."""

    name = "audiomack"
    priority = 85

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list[SearchResult]:
        query = f"{song} {artist}".strip() if artist else song

        headers = {"User-Agent": USER_AGENT}
        params = {"q": query}

        try:
            resp = httpx.get(SEARCH_URL, headers=headers,
                             params=params, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning("Audiomack search failed for '%s': %s", query, exc)
            return []

        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[SearchResult] = []

        # Audiomack search results are typically in anchor tags with song cards
        for card in soup.select("a.song-card, a[href*='/song/']"):
            href = card.get("href", "")
            if not href.startswith("http"):
                href = f"https://audiomack.com{href}"

            title_el = card.select_one(".song-card__title, .title")
            artist_el = card.select_one(".song-card__artist, .artist")

            title = title_el.get_text(strip=True) if title_el else "Unknown"
            artist_name = artist_el.get_text(strip=True) if artist_el else None

            results.append(
                SearchResult(
                    title=title,
                    artist=artist_name,
                    duration=0,  # unknown until we visit the page
                    format=AudioFormat.MP3,
                    quality=Quality.HIGH,
                    source=self.name,
                    url=href,
                    score=self._compute_score(len(results)),
                    metadata={"page_url": href},
                )
            )

        return results

    def download(
        self,
        result: SearchResult,
        dest_dir: str,
    ) -> DownloadResult:
        # Resolve the actual download URL from the song page
        download_url = self._extract_download_url(result.url)
        if not download_url:
            return DownloadResult(
                result=result,
                file_path="",
                success=False,
                error="Could not extract download URL from Audiomack page",
            )

        artist_dir = self._sanitize(result.artist or "Unknown")
        song_file = self._sanitize(result.title)
        filename = f"{song_file}--audiomack.mp3"
        dest_path = os.path.join(dest_dir, "mp3", artist_dir, filename)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        headers = {"User-Agent": USER_AGENT}
        try:
            resp = httpx.get(download_url, headers=headers, timeout=60)
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(resp.content)
        except Exception as exc:
            logger.error("Audiomack download failed for '%s': %s",
                         result.url, exc)
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

    def _extract_download_url(self, page_url: str) -> Optional[str]:
        """Visit the song page and extract the direct MP3 download link."""
        headers = {"User-Agent": USER_AGENT}
        try:
            resp = httpx.get(page_url, headers=headers, timeout=20)
            resp.raise_for_status()
        except Exception as exc:
            logger.warning(
                "Failed to fetch Audiomack page '%s': %s", page_url, exc)
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Look for download button/link — common patterns
        for link in soup.select("a[download], a[href$='.mp3']"):
            href = link.get("href", "")
            if href.startswith("//"):
                href = f"https:{href}"
            elif href.startswith("/"):
                href = f"https://audiomack.com{href}"
            if ".mp3" in href:
                return href

        # Fallback: look for audio source tags
        for source in soup.select("audio source[src], source[src$='.mp3']"):
            src = source.get("src", "")
            if src.startswith("//"):
                src = f"https:{src}"
            return src

        logger.debug("No download URL found on Audiomack page: %s", page_url)
        return None

    @staticmethod
    def _compute_score(index: int) -> float:
        """Simple score based on position in results list."""
        return round(max(0.0, 1.0 - index * 0.1), 2)

    @staticmethod
    def _sanitize(name: str) -> str:
        """Remove characters problematic for filenames."""
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()
