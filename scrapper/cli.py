"""
CLI entry point for the song scraper.

Usage:
    sgpt-scrape "Bohemian Rhapsody" --artist "Queen"
    sgpt-scrape "Song Title" --search-only
    sgpt-scrape "Song Title" --sources youtube,spotify
"""

from __future__ import annotations

import logging
import sys
from typing import Optional

import click

from . import SongScraper
from .models import AudioFormat


# ---------------------------------------------------------------------------
# Shared options
# ---------------------------------------------------------------------------

_artist_option = click.option(
    "--artist",
    "-a",
    help="Artist name to narrow the search.",
    type=str,
    default=None,
)

_format_option = click.option(
    "--format",
    "-f",
    help="Preferred audio format (mp3, midi, m4a, etc.).",
    type=click.Choice([f.value for f in AudioFormat], case_sensitive=False),
    default=None,
)

_sources_option = click.option(
    "--sources",
    "-s",
    help="Comma-separated list of sources (youtube,spotify,audiomack,apple_music,midi_db).",
    type=str,
    default=None,
)

_output_option = click.option(
    "--output-dir",
    "-o",
    help="Download directory.",
    type=click.Path(file_okay=False),
    default=None,
)

_verbose_option = click.option(
    "--verbose",
    "-v",
    help="Enable verbose logging.",
    is_flag=True,
    default=False,
)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


@click.group()
@click.version_option(version="0.1.0", prog_name="sgpt-scrape")
def cli() -> None:
    """Search and download audio files for a song."""


@cli.command()
@click.argument("song", type=str, required=True)
@_artist_option
@_format_option
@_sources_option
@_output_option
@_verbose_option
@click.option(
    "--search-only",
    help="Only search, do not download.",
    is_flag=True,
    default=False,
)
@click.option(
    "--download-all",
    help="Download all results (not just the best).",
    is_flag=True,
    default=False,
)
def search(
    song: str,
    artist: Optional[str],
    format: Optional[str],  # noqa: A002 — matches CLI option name
    sources: Optional[str],
    output_dir: Optional[str],
    verbose: bool,
    search_only: bool,
    download_all: bool,
) -> None:
    """Search and optionally download audio for SONG."""
    _setup_logging(verbose)

    scraper = SongScraper()

    # Parse format filter
    format_filter: Optional[list[AudioFormat]] = None
    if format:
        format_filter = [AudioFormat(format.lower())]

    # Parse source filter
    source_filter: Optional[list[str]] = None
    if sources:
        source_filter = [s.strip().lower() for s in sources.split(",")]

    click.echo(f"🔍 Searching for '{song}'" +
               (f" by {artist}" if artist else "") + "…")

    try:
        results = scraper.search(
            song=song,
            artist=artist,
            sources=source_filter,
            formats=format_filter,
        )
    except ValueError as exc:
        click.echo(f"❌ Error: {exc}", err=True)
        sys.exit(1)

    if not results:
        click.echo("😕 No results found.")
        sys.exit(0)

    click.echo(f"\n📋 Found {len(results)} result(s):\n")

    for i, r in enumerate(results, 1):
        duration_str = _format_duration(r.duration)
        size_str = _format_size(r.file_size) if r.file_size else "?"
        click.echo(
            f"  {i:>2}. [{r.source:^12}] {r.title}"
            + (f" — {r.artist}" if r.artist else "")
            + f" ({r.format.value}, {r.quality.value}, {duration_str}, {size_str})"
            + f"  score: {r.score:.2f}"
        )

    if search_only:
        click.echo("\n✅ Search complete (--search-only mode).")
        return

    # Download
    if download_all:
        click.echo(f"\n⬇️  Downloading all {len(results)} results…")
        dl_results = scraper.download_all(results, dest_dir=output_dir)
    else:
        click.echo("\n⬇️  Downloading best result…")
        dl_results = [scraper.download_best(results, dest_dir=output_dir)]

    # Summary
    success_count = sum(1 for d in dl_results if d.success)
    fail_count = len(dl_results) - success_count

    click.echo()
    if success_count:
        click.echo(f"✅ {success_count} file(s) downloaded successfully:")
        for d in dl_results:
            if d.success:
                click.echo(f"   📁 {d.file_path}")

    if fail_count:
        click.echo(f"❌ {fail_count} download(s) failed:")
        for d in dl_results:
            if not d.success:
                click.echo(f"   ❌ {d.result.title} — {d.error}")


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


def main() -> None:
    """Console-script entry point (see pyproject.toml)."""
    cli()


def _setup_logging(verbose: bool) -> None:
    """Configure logging based on verbosity."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )


def _format_duration(seconds: int) -> str:
    """Format seconds to mm:ss."""
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _format_size(size: int) -> str:
    """Format bytes to human-readable string."""
    fsize = float(size)
    for unit in ("B", "KB", "MB", "GB"):
        if fsize < 1024:
            return f"{fsize:.1f}{unit}"
        fsize /= 1024
    return f"{fsize:.1f}TB"


if __name__ == "__main__":
    main()
