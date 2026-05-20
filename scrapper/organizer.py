"""
File Organizer — naming, directory structure creation, metadata, and deduplication.

Manages the on-disk layout of downloaded audio files and their metadata.
"""

from __future__ import annotations

import json
import logging
import os
import re
from typing import Optional

from .models import AudioFormat, DownloadResult, SearchResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Mapping from AudioFormat to subdirectory name
_FORMAT_DIR_MAP: dict[AudioFormat, str] = {
    AudioFormat.MP3: "mp3",
    AudioFormat.M4A: "m4a",
    AudioFormat.WAV: "wav",
    AudioFormat.FLAC: "flac",
    AudioFormat.WEBM: "webm",
    AudioFormat.OPUS: "opus",
    AudioFormat.MIDI: "midi",
}


def _sanitize(text: str) -> str:
    """Remove characters that are problematic in filenames."""
    text = re.sub(r'[\\/*?:"<>|]', "", text)
    text = text.strip().rstrip(". ")
    return text or "Unknown"


def _format_dir(fmt: AudioFormat) -> str:
    """Get the subdirectory name for a format (fallback to 'other')."""
    return _FORMAT_DIR_MAP.get(fmt, "other")


# ---------------------------------------------------------------------------
# File Organizer
# ---------------------------------------------------------------------------


class FileOrganizer:
    """Handles file naming, directory structure, and metadata for downloads."""

    def __init__(self, base_dir: str = "./data/raw") -> None:
        self.base_dir = base_dir

    # ------------------------------------------------------------------
    # Path building
    # ------------------------------------------------------------------

    def build_path(self, result: SearchResult) -> str:
        """Build the full destination path for a search result.

        Directory structure:
            {base_dir}/{format_dir}/{artist}/{title}--{source}.{ext}
        """
        fmt_dir = _format_dir(result.format)
        artist_dir = _sanitize(result.artist or "Unknown Artist")
        title_slug = _sanitize(result.title)
        filename = f"{title_slug}--{result.source}.{result.format.value}"
        return os.path.join(self.base_dir, fmt_dir, artist_dir, filename)

    def build_metadata_path(self, file_path: str) -> str:
        """Build the companion metadata JSON path for a downloaded file."""
        return f"{file_path}.meta.json"

    # ------------------------------------------------------------------
    # Directory management
    # ------------------------------------------------------------------

    def ensure_dir(self, path: str) -> str:
        """Ensure the parent directory for *path* exists and return *path*."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        return path

    # ------------------------------------------------------------------
    # Deduplication
    # ------------------------------------------------------------------

    def exists(self, result: SearchResult) -> bool:
        """Check if a file for this search result already exists on disk."""
        path = self.build_path(result)
        return os.path.isfile(path)

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def save_metadata(self, result: SearchResult, file_path: str) -> None:
        """Save a companion .json file with the search result's metadata.

        The metadata file is placed next to the audio file with a
        .meta.json extension.
        """
        meta_path = self.build_metadata_path(file_path)
        data = {
            "title": result.title,
            "artist": result.artist,
            "duration_seconds": result.duration,
            "format": result.format.value,
            "quality": result.quality.value,
            "source": result.source,
            "url": result.url,
            "file_size": result.file_size,
            "score": result.score,
            "metadata": result.metadata,
        }
        try:
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except OSError as exc:
            logger.warning(
                "Failed to save metadata for '%s': %s", file_path, exc)

    def load_metadata(self, file_path: str) -> Optional[dict]:
        """Load the companion metadata for a downloaded file.

        Returns:
            The metadata dict, or None if no metadata file exists.
        """
        meta_path = self.build_metadata_path(file_path)
        if not os.path.isfile(meta_path):
            return None
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                return json.load(f)  # type: ignore[no-any-return]
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Failed to load metadata '%s': %s", meta_path, exc)
            return None

    # ------------------------------------------------------------------
    # Post-download organisation
    # ------------------------------------------------------------------

    def organise(
        self,
        download_result: DownloadResult,
        overwrite: bool = False,
    ) -> DownloadResult:
        """Organise a downloaded file into the correct directory structure.

        If the download was successful, this:
        1. Ensures the target directory exists
        2. Renames/moves the file to the canonical path
        3. Saves companion metadata

        Args:
            download_result: The result from a download operation.
            overwrite: If True, overwrite existing files.

        Returns:
            The updated DownloadResult with the final file_path.
        """
        if not download_result.success:
            return download_result

        result = download_result.result
        target_path = self.build_path(result)

        # Skip if exists and not overwriting
        if os.path.isfile(target_path) and not overwrite:
            logger.debug("File already exists, skipping: %s", target_path)
            return DownloadResult(
                result=result,
                file_path=target_path,
                success=True,
            )

        # Move from temporary path to canonical path
        current_path = download_result.file_path
        if current_path and current_path != target_path:
            self.ensure_dir(target_path)
            try:
                os.renames(current_path, target_path)
            except OSError as exc:
                logger.error(
                    "Failed to move '%s' -> '%s': %s",
                    current_path,
                    target_path,
                    exc,
                )
                return DownloadResult(
                    result=result,
                    file_path=current_path,
                    success=True,
                    error=f"File saved but metadata move failed: {exc}",
                )
        else:
            self.ensure_dir(target_path)

        # Save companion metadata
        self.save_metadata(result, target_path)

        return DownloadResult(
            result=result,
            file_path=target_path,
            success=True,
        )
