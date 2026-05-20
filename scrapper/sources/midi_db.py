"""
MIDI source adapter.

Scrapes multiple public MIDI databases to find and download .mid files.
Supports: midiworld.com, bitmidi.com, freemidi.org
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

# ---------------------------------------------------------------------------
# Site definitions
# ---------------------------------------------------------------------------

MIDI_SITES: list[dict] = [
    {
        "name": "midiworld",
        "search_url": "https://www.midiworld.com/search/",
        "search_params": {"q": None},  # q={term}
        "result_selector": "a[href*='.mid'], a[href*='/midi/']",
    },
    {
        "name": "bitmidi",
        "search_url": "https://bitmidi.com/",
        "search_params": {"s": None},  # s={term}
        "result_selector": "a[href$='.mid'], a.download-link, a[href*='/midi/']",
    },
    {
        "name": "freemidi",
        "search_url": "https://freemidi.org/",
        "search_params": {"search": None},  # search={term}
        "result_selector": "a[href*='.mid'], a[href*='/download-']",
    },
]

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


class MIDISource(SourceAdapter):
    """Search public MIDI databases and download .mid files."""

    name = "midi_db"
    priority = 70

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list[SearchResult]:
        term = f"{song} {artist}".strip() if artist else song
        all_results: list[SearchResult] = []

        for site in MIDI_SITES:
            try:
                site_results = self._search_site(site, term)
                all_results.extend(site_results)
            except Exception as exc:
                logger.warning(
                    "MIDI site '%s' search failed: %s", site["name"], exc
                )

        return all_results

    def download(
        self,
        result: SearchResult,
        dest_dir: str,
    ) -> DownloadResult:
        artist_dir = self._sanitize(result.artist or "Unknown")
        song_file = self._sanitize(result.title)
        filename = f"{song_file}--{result.metadata.get('site', 'midi')}.mid"
        dest_path = os.path.join(dest_dir, "midi", artist_dir, filename)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        # Resolve download URL — some sites require scraping the song page first
        download_url = result.url
        if not download_url.endswith(".mid"):
            download_url = self._resolve_download_url(
                result.url,
                result.metadata.get("site", ""),
            )
            if not download_url:
                return DownloadResult(
                    result=result,
                    file_path="",
                    success=False,
                    error="Could not resolve MIDI download URL",
                )

        headers = {"User-Agent": USER_AGENT}
        try:
            resp = httpx.get(download_url, headers=headers, timeout=30)
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(resp.content)
        except Exception as exc:
            logger.error("MIDI download failed for '%s': %s", result.url, exc)
            return DownloadResult(
                result=result,
                file_path="",
                success=False,
                error=str(exc),
            )

        return DownloadResult(result=result, file_path=dest_path, success=True)

    # ------------------------------------------------------------------
    # Internal — per-site search
    # ------------------------------------------------------------------

    def _search_site(
        self,
        site: dict,
        term: str,
    ) -> list[SearchResult]:
        """Search a single MIDI database and return results."""
        params = {
            k: term if v is None else v
            for k, v in site["search_params"].items()
        }
        headers = {"User-Agent": USER_AGENT}

        resp = httpx.get(
            site["search_url"],
            params=params,
            headers=headers,
            timeout=20,
        )
        resp.raise_for_status()

        soup = BeautifulSoup(resp.text, "html.parser")
        results: list[SearchResult] = []

        for link in soup.select(site["result_selector"]):
            href = link.get("href", "")
            if not href:
                continue

            # Make absolute
            if href.startswith("//"):
                href = f"https:{href}"
            elif href.startswith("/"):
                href = f"{site['search_url'].rstrip('/')}{href}"
            elif not href.startswith("http"):
                href = f"{site['search_url'].rstrip('/')}/{href}"

            title = link.get("title") or link.get_text(strip=True) or "Unknown"

            results.append(
                SearchResult(
                    title=title,
                    artist=None,  # MIDI sites rarely provide artist metadata
                    duration=0,
                    format=AudioFormat.MIDI,
                    quality=Quality.MEDIUM,
                    source=self.name,
                    url=href,
                    score=self._compute_score(len(results)),
                    metadata={"site": site["name"]},
                )
            )

        return results

    def _resolve_download_url(
        self,
        page_url: str,
        site_name: str,
    ) -> Optional[str]:
        """Visit a song page and find the actual .mid download link."""
        headers = {"User-Agent": USER_AGENT}
        try:
            resp = httpx.get(page_url, headers=headers, timeout=20)
            resp.raise_for_status()
        except Exception:
            return None

        soup = BeautifulSoup(resp.text, "html.parser")

        # Common patterns for .mid download links
        for link in soup.select(
            "a[href$='.mid'], a[href$='.midi'], a.download, a[download]"
        ):
            href = link.get("href", "")
            if href.startswith("//"):
                href = f"https:{href}"
            elif href.startswith("/"):
                base = f"https://{httpx.URL(page_url).host}"
                href = f"{base}{href}"
            if ".mid" in href:
                return href

        return None

    @staticmethod
    def _compute_score(index: int) -> float:
        """Score based on position within a single site's results."""
        return round(max(0.0, 1.0 - index * 0.1), 2)

    @staticmethod
    def _sanitize(name: str) -> str:
        """Remove characters problematic for filenames."""
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()
