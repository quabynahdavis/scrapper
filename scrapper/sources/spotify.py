"""
Spotify source adapter.

Uses the Spotify Web API to search for tracks and fetch 30-second
MP3 preview clips. Requires SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET
environment variables.
"""

from __future__ import annotations

import logging
import os
from typing import Optional

import httpx

from ..models import AudioFormat, DownloadResult, Quality, SearchResult
from .base import SourceAdapter

logger = logging.getLogger(__name__)

TOKEN_URL = "https://accounts.spotify.com/api/token"
SEARCH_URL = "https://api.spotify.com/v1/search"


class SpotifySource(SourceAdapter):
    """Search Spotify and download 30-second preview clips."""

    name = "spotify"
    priority = 90

    def __init__(self) -> None:
        self._access_token: Optional[str] = None
        self._client_id = os.environ.get("SPOTIFY_CLIENT_ID")
        self._client_secret = os.environ.get("SPOTIFY_CLIENT_SECRET")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list[SearchResult]:
        if not self._ensure_token():
            logger.warning("Spotify: no valid access token, skipping search")
            return []

        query = f"track:{song}"
        if artist:
            query += f" artist:{artist}"

        headers = {"Authorization": f"Bearer {self._access_token}"}
        params = {"q": query, "type": "track", "limit": 10}

        try:
            resp = httpx.get(SEARCH_URL, headers=headers,
                             params=params, timeout=15)
            resp.raise_for_status()
            data = resp.json()
        except Exception as exc:
            logger.warning("Spotify search failed for '%s': %s", query, exc)
            return []

        tracks = data.get("tracks", {}).get("items", [])
        results: list[SearchResult] = []

        for track in tracks:
            preview_url = track.get("preview_url")
            if not preview_url:
                continue

            artists = ", ".join(a["name"] for a in track.get("artists", []))
            duration_ms = track.get("duration_ms", 0)

            results.append(
                SearchResult(
                    title=track.get("name", "Unknown"),
                    artist=artists or None,
                    duration=int(duration_ms / 1000),
                    format=AudioFormat.MP3,
                    quality=Quality.MEDIUM,
                    source=self.name,
                    url=preview_url,
                    file_size=None,
                    score=self._compute_score(track),
                    metadata={
                        "spotify_id": track.get("id"),
                        "album": track.get("album", {}).get("name"),
                        "popularity": track.get("popularity"),
                        "track_number": track.get("track_number"),
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
        filename = f"{song_file}--spotify.mp3"
        dest_path = os.path.join(dest_dir, "mp3", artist_dir, filename)

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)

        try:
            resp = httpx.get(result.url, timeout=30)
            resp.raise_for_status()
            with open(dest_path, "wb") as f:
                f.write(resp.content)
        except Exception as exc:
            logger.error("Spotify download failed for '%s': %s",
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

    def _ensure_token(self) -> bool:
        """Obtain a Client Credentials OAuth token if we don't have one."""
        if self._access_token:
            return True
        if not self._client_id or not self._client_secret:
            logger.warning(
                "SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET must be set"
            )
            return False

        try:
            resp = httpx.post(
                TOKEN_URL,
                data={"grant_type": "client_credentials"},
                auth=(self._client_id, self._client_secret),
                timeout=15,
            )
            resp.raise_for_status()
            self._access_token = resp.json().get("access_token")
            return self._access_token is not None
        except Exception as exc:
            logger.warning("Failed to obtain Spotify token: %s", exc)
            return False

    @staticmethod
    def _compute_score(track: dict) -> float:
        """Compute a relevance score from Spotify's popularity metric."""
        popularity = track.get("popularity") or 0  # 0–100
        return round(popularity / 100, 2)

    @staticmethod
    def _sanitize(name: str) -> str:
        """Remove characters problematic for filenames."""
        import re
        return re.sub(r'[\\/*?:"<>|]', "", name).strip()
