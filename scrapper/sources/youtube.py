"""
YouTube source adapter.

Uses yt-dlp to search YouTube and extract the best available audio.
Provides full-length songs with good quality.
"""

from __future__ import annotations

import logging
import os
import re
from typing import Optional

import yt_dlp

from ..models import AudioFormat, DownloadResult, Quality, SearchResult
from .base import SourceAdapter

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Map yt-dlp format notes / audio codec to our AudioFormat
_FORMAT_MAP: dict[str, AudioFormat] = {
    "mp3": AudioFormat.MP3,
    "m4a": AudioFormat.M4A,
    "webm": AudioFormat.WEBM,
    "opus": AudioFormat.OPUS,
    "vorbis": AudioFormat.OPUS,
    "aac": AudioFormat.M4A,
    "wav": AudioFormat.WAV,
    "flac": AudioFormat.FLAC,
}


def _infer_format(format_info: dict) -> AudioFormat:
    """Extract the audio format from yt-dlp's format info dict."""
    ext = (format_info.get("ext") or "").lower()
    acodec = (format_info.get("acodec") or "").lower()

    # Direct extension match
    if ext in _FORMAT_MAP:
        return _FORMAT_MAP[ext]

    # Fallback to codec
    if acodec in _FORMAT_MAP:
        return _FORMAT_MAP[acodec]

    return AudioFormat.MP3


def _infer_quality(format_info: dict) -> Quality:
    """Infer quality from bitrate."""
    abr = format_info.get("abr")  # audio bitrate in kbps
    if abr is None:
        return Quality.MEDIUM
    if abr < 96:
        return Quality.LOW
    if abr <= 192:
        return Quality.MEDIUM
    if abr <= 320:
        return Quality.HIGH
    return Quality.LOSSLESS


def _sanitize_filename(name: str) -> str:
    """Remove characters that are problematic in filenames."""
    return re.sub(r'[\\/*?:"<>|]', "", name).strip()


# ---------------------------------------------------------------------------
# Adapter
# ---------------------------------------------------------------------------


class YouTubeSource(SourceAdapter):
    """Search YouTube and download audio via yt-dlp."""

    name = "youtube"
    priority = 100

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list[SearchResult]:
        query = f"ytsearch10:{song} {artist}".strip() if artist else f"ytsearch10:{song}"

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "extract_flat": True,  # only metadata, no download
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl: # type: ignore
            try:
                info = ydl.extract_info(query, download=False)
            except Exception as exc:
                logger.warning(
                    "YouTube search failed for '%s': %s", query, exc)
                return []

        entries = info.get("entries") or []
        results: list[SearchResult] = []

        for entry in entries:
            if not entry:
                continue

            title = entry.get("title") or "Unknown"
            duration = entry.get("duration") or 0
            url = f"https://www.youtube.com/watch?v={entry.get('id', '')}"
            uploader = entry.get("uploader") or entry.get("channel") or ""

            # Build a quality estimate — yt-dlp doesn't give bitrate in flat mode
            results.append(
                SearchResult(
                    title=title,
                    artist=uploader,
                    duration=int(duration),
                    format=AudioFormat.MP3,  # will be refined on download
                    quality=Quality.MEDIUM,
                    source=self.name,
                    url=url,
                    score=self._compute_score(entry),
                    metadata={
                        "video_id": entry.get("id"),
                        "channel": uploader,
                        "view_count": entry.get("view_count"),
                        "source": "youtube",
                    },
                )
            )

        return results

    def download(
        self,
        result: SearchResult,
        dest_dir: str,
    ) -> DownloadResult:
        artist_dir = _sanitize_filename(result.artist or "Unknown")
        outtmpl = os.path.join(
            dest_dir,
            "mp3",
            artist_dir,
            "%(title)s--youtube.%(ext)s",
        )

        ydl_opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        try:
            with yt_dlp.YoutubeDL(ydl_opts) as ydl: # type: ignore
                ydl.download([result.url])
        except Exception as exc:
            logger.error("YouTube download failed for '%s': %s",
                         result.url, exc)
            return DownloadResult(
                result=result,
                file_path="",
                success=False,
                error=str(exc),
            )

        # Build expected file path
        safe_title = _sanitize_filename(result.title)
        expected_file = os.path.join(
            dest_dir, "mp3", artist_dir, f"{safe_title}--youtube.mp3"
        )

        if os.path.isfile(expected_file):
            return DownloadResult(
                result=result,
                file_path=expected_file,
                success=True,
            )

        # Fallback: search for any matching file
        parent = os.path.join(dest_dir, "mp3", artist_dir)
        if os.path.isdir(parent):
            for fname in os.listdir(parent):
                if safe_title in fname:
                    return DownloadResult(
                        result=result,
                        file_path=os.path.join(parent, fname),
                        success=True,
                    )

        return DownloadResult(
            result=result,
            file_path=expected_file,
            success=False,
            error="File not found after download",
        )

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _compute_score(entry: dict) -> float:
        """Heuristic relevance score based on view count and match quality."""
        views = entry.get("view_count") or 0
        # Normalise views: 10M+ → 1.0, 1M → 0.8, 100k → 0.5, 10k → 0.2
        score = min(1.0, views / 10_000_000) * 0.8 + 0.2
        return round(score, 2)
