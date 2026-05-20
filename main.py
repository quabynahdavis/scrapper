#!/usr/bin/env python3
"""
Interactive testing system for the scrapper framework.

Run:  python main.py

Provides a REPL-style interface to search, download, and inspect
results from all registered source adapters.
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from scrapper import SongScraper
from scrapper.models import AudioFormat, SearchResult

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
MAGENTA = "\033[95m"


def _fmt_duration(seconds: int) -> str:
    m, s = divmod(seconds, 60)
    return f"{m}:{s:02d}"


def _fmt_size(bytes_: Optional[int]) -> str:
    if bytes_ is None:
        return "?"
    size = float(bytes_)
    for unit in ("B", "KB", "MB", "GB"):
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def _print_header(text: str) -> None:
    width = 60
    print(f"\n{BOLD}{CYAN}{'=' * width}{RESET}")
    print(f"{BOLD}{CYAN}{text:^{width}}{RESET}")
    print(f"{BOLD}{CYAN}{'=' * width}{RESET}\n")


def _print_error(text: str) -> None:
    print(f"{RED}❌ {text}{RESET}")


def _print_success(text: str) -> None:
    print(f"{GREEN}✅ {text}{RESET}")


def _print_info(text: str) -> None:
    print(f"{YELLOW}ℹ️  {text}{RESET}")


# ---------------------------------------------------------------------------
# Interactive Shell
# ---------------------------------------------------------------------------


class InteractiveShell:
    """REPL for testing the scrapper framework interactively."""

    def __init__(self) -> None:
        self.scraper = SongScraper()
        self.results: list[SearchResult] = []
        self.last_query: str = ""
        self._show_help()

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(self) -> None:
        while True:
            try:
                cmd = input(f"\n{BOLD}scrapper>{RESET} ").strip()
            except (EOFError, KeyboardInterrupt):
                print()
                break

            if not cmd:
                continue

            parts = cmd.split(maxsplit=1)
            action = parts[0].lower()
            args = parts[1] if len(parts) > 1 else ""

            handler = self._get_handler(action)
            if handler:
                try:
                    handler(args)
                except Exception as exc:
                    _print_error(f"Command failed: {exc}")
            else:
                _print_error(f"Unknown command: '{action}'. Type 'help'.")

    # ------------------------------------------------------------------
    # Command registration
    # ------------------------------------------------------------------

    def _get_handler(self, action: str):
        handlers = {
            "help": self._cmd_help,
            "h": self._cmd_help,
            "?": self._cmd_help,
            "search": self._cmd_search,
            "s": self._cmd_search,
            "list": self._cmd_list,
            "l": self._cmd_list,
            "download": self._cmd_download,
            "dl": self._cmd_download,
            "download-all": self._cmd_download_all,
            "dla": self._cmd_download_all,
            "sources": self._cmd_sources,
            "config": self._cmd_config,
            "clear": self._cmd_clear,
            "cls": self._cmd_clear,
            "quit": self._cmd_quit,
            "q": self._cmd_quit,
            "exit": self._cmd_quit,
            "stats": self._cmd_stats,
        }
        return handlers.get(action)

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _cmd_help(self, _: str = "") -> None:
        self._show_help()

    def _cmd_search(self, args: str) -> None:
        """search <song> [--artist <name>]"""
        if not args:
            _print_error("Usage: search <song> [--artist <name>]")
            return

        # Parse optional --artist flag
        song = args
        artist: Optional[str] = None
        if " --artist " in args or " -a " in args:
            for sep in (" --artist ", " -a "):
                if sep in args:
                    parts = args.split(sep, 1)
                    song = parts[0].strip()
                    artist = parts[1].strip() if len(parts) > 1 else None
                    break

        self.last_query = f"{song} ({artist or 'any artist'})"

        _print_header(f"🔍 Searching: {song}" +
                      (f" by {artist}" if artist else ""))

        self.results = self.scraper.search(song, artist=artist)

        if not self.results:
            _print_info("No results found.")
            return

        _print_success(f"Found {len(self.results)} result(s)\n")

        for i, r in enumerate(self.results, 1):
            dur = _fmt_duration(r.duration)
            size = _fmt_size(r.file_size)
            print(
                f"  {BOLD}{i:>2}.{RESET} "
                f"[{MAGENTA}{r.source:^12}{RESET}] "
                f"{BOLD}{r.title}{RESET}"
                + (f" — {r.artist}" if r.artist else "")
                + f"\n{'':>6}{DIM}{r.format.value}, {r.quality.value}, "
                f"{dur}, {size}  |  score: {r.score:.2f}{RESET}"
            )

    def _cmd_list(self, _: str = "") -> None:
        """List cached results from last search."""
        if not self.results:
            _print_info("No cached results. Run 'search' first.")
            return

        _print_header(f"📋 Cached Results ({len(self.results)} total)")

        for i, r in enumerate(self.results, 1):
            dur = _fmt_duration(r.duration)
            size = _fmt_size(r.file_size)
            print(
                f"  {BOLD}{i:>2}.{RESET} "
                f"[{MAGENTA}{r.source:^12}{RESET}] "
                f"{BOLD}{r.title}{RESET}"
                + (f" — {r.artist}" if r.artist else "")
                + f"\n{'':>6}{DIM}{r.format.value}, {r.quality.value}, "
                f"{dur}, {size}  |  score: {r.score:.2f}{RESET}"
            )

    def _cmd_download(self, args: str) -> None:
        """download <index> — Download a specific result by its list index."""
        if not self.results:
            _print_info("No cached results. Run 'search' first.")
            return

        if not args or not args.strip().isdigit():
            _print_error("Usage: download <index_number>")
            return

        idx = int(args.strip()) - 1
        if idx < 0 or idx >= len(self.results):
            _print_error(
                f"Index out of range. Use 1–{len(self.results)}."
            )
            return

        result = self.results[idx]
        _print_header(
            f"⬇️  Downloading: {result.title}"
            + (f" — {result.artist}" if result.artist else "")
        )

        dl = self.scraper.download_best([result])

        if dl.success:
            _print_success(f"Saved to: {dl.file_path}")
        else:
            _print_error(f"Download failed: {dl.error or 'Unknown error'}")

    def _cmd_download_all(self, _: str = "") -> None:
        """Download all cached results."""
        if not self.results:
            _print_info("No cached results. Run 'search' first.")
            return

        _print_header(
            f"⬇️  Downloading all {len(self.results)} results"
        )

        dl_results = self.scraper.download_all(self.results)

        success = sum(1 for d in dl_results if d.success)
        failed = sum(1 for d in dl_results if not d.success)

        for d in dl_results:
            if d.success:
                print(f"  {GREEN}✅{RESET} {d.result.title}: {d.file_path}")
            else:
                print(f"  {RED}❌{RESET} {d.result.title}: {d.error}")

        print()
        _print_success(f"{success} downloaded, {failed} failed")

    def _cmd_sources(self, _: str = "") -> None:
        """List registered sources with their priority and status."""
        _print_header("📡 Registered Sources")

        adapters = self.scraper.registry.get_by_priority()
        for a in adapters:
            print(
                f"  {BOLD}{a.name:^12}{RESET}  "
                f"priority: {a.priority}"
            )

    def _cmd_config(self, _: str = "") -> None:
        """Show current configuration."""
        _print_header("⚙️  Current Configuration")

        config = self.scraper.config
        sources = config.get("sources", {})
        download = config.get("download", {})

        print(f"  {BOLD}Sources:{RESET}")
        for name, cfg in sources.items():
            enabled = cfg.get("enabled", True)
            status = f"{GREEN}enabled{RESET}" if enabled else f"{RED}disabled{RESET}"
            rl = cfg.get("rate_limit", "—")
            print(f"    {name:<12} {status}  rate_limit: {rl}s")

        print(f"\n  {BOLD}Download:{RESET}")
        print(f"    max_concurrent: {download.get('max_concurrent', 3)}")
        print(f"    max_retries:    {download.get('max_retries', 3)}")
        print(f"    timeout:        {download.get('timeout', 60)}s")
        print(f"    directory:      {download.get('directory', './data/raw')}")

    def _cmd_clear(self, _: str = "") -> None:
        """Clear the terminal."""
        os.system("cls" if os.name == "nt" else "clear")

    def _cmd_stats(self, _: str = "") -> None:
        """Show statistics about the last search."""
        if not self.results:
            _print_info("No cached results. Run 'search' first.")
            return

        _print_header("📊 Search Statistics")

        by_source: dict[str, int] = {}
        by_format: dict[str, int] = {}
        for r in self.results:
            by_source[r.source] = by_source.get(r.source, 0) + 1
            by_format[r.format.value] = by_format.get(r.format.value, 0) + 1

        print(f"  Query:        {BOLD}{self.last_query}{RESET}")
        print(f"  Total results: {len(self.results)}")
        print(f"\n  {BOLD}By source:{RESET}")
        for src, count in sorted(by_source.items(), key=lambda x: -x[1]):
            print(f"    {src:<12} {count}")
        print(f"\n  {BOLD}By format:{RESET}")
        for fmt, count in sorted(by_format.items(), key=lambda x: -x[1]):
            print(f"    {fmt:<12} {count}")

    def _cmd_quit(self, _: str = "") -> None:
        """Exit the interactive shell."""
        print(f"\n{YELLOW}👋 Goodbye!{RESET}")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Help text
    # ------------------------------------------------------------------

    @staticmethod
    def _show_help() -> None:
        _print_header("🎵 Scrapper Interactive Shell")

        print(
            f"  {BOLD}search <song> [--artist <name>]{RESET}\n"
            f"    {'':>4}{DIM}Search for a song across all sources{RESET}\n"
            f"  {BOLD}s{RESET}       {DIM}alias for search{RESET}\n"
            f"\n"
            f"  {BOLD}list{RESET}    {DIM}Show cached results from last search{RESET}\n"
            f"  {BOLD}l{RESET}       {DIM}alias for list{RESET}\n"
            f"\n"
            f"  {BOLD}download <n>{RESET}\n"
            f"    {'':>4}{DIM}Download result #n from the cached list{RESET}\n"
            f"  {BOLD}dl{RESET}      {DIM}alias for download{RESET}\n"
            f"\n"
            f"  {BOLD}download-all{RESET}\n"
            f"    {'':>4}{DIM}Download all cached results{RESET}\n"
            f"  {BOLD}dla{RESET}     {DIM}alias for download-all{RESET}\n"
            f"\n"
            f"  {BOLD}sources{RESET}  {DIM}List registered sources with priorities{RESET}\n"
            f"  {BOLD}config{RESET}   {DIM}Show current configuration{RESET}\n"
            f"  {BOLD}stats{RESET}    {DIM}Show statistics from last search{RESET}\n"
            f"  {BOLD}clear{RESET}    {DIM}Clear the terminal{RESET}\n"
            f"  {BOLD}help{RESET}     {DIM}Show this help{RESET}\n"
            f"  {BOLD}quit{RESET}     {DIM}Exit{RESET}"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    shell = InteractiveShell()
    try:
        shell.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}👋 Goodbye!{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
