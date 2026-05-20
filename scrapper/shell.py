"""
Interactive shell (TUI) for the scrapper framework.

Provides a REPL with tab completion, history, auto-suggestions,
and a settings menu. Can be launched via:

    scrapper shell          # from the installed CLI
    python main.py          # standalone script
    python -m scrapper.shell
"""

from __future__ import annotations

import os
import sys
from typing import Optional

from prompt_toolkit import PromptSession
from prompt_toolkit.auto_suggest import AutoSuggestFromHistory
from prompt_toolkit.completion import Completer, Completion, PathCompleter
from prompt_toolkit.formatted_text import FormattedText
from prompt_toolkit.history import FileHistory
import yaml

from scrapper import SongScraper
from scrapper.models import AudioFormat, SearchResult

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

CONFIG_DIR = os.path.expanduser("~/.config/scrapper")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.yaml")
HISTORY_FILE = os.path.join(CONFIG_DIR, "history")


def _ensure_config_dir() -> None:
    os.makedirs(CONFIG_DIR, exist_ok=True)


def _load_user_config() -> dict:
    if os.path.isfile(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return yaml.safe_load(f) or {}
        except Exception:
            pass
    return {}


def _save_user_config(config: dict) -> None:
    _ensure_config_dir()
    with open(CONFIG_FILE, "w") as f:
        yaml.dump(config, f, default_flow_style=False)


# ---------------------------------------------------------------------------
# Terminal colors
# ---------------------------------------------------------------------------

RESET = "\033[0m"
BOLD = "\033[1m"
DIM = "\033[2m"
GREEN = "\033[92m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
RED = "\033[91m"
MAGENTA = "\033[95m"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


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


def _mask(value: str, visible: int = 4) -> str:
    if not value:
        return "(not set)"
    if len(value) <= visible:
        return "*" * len(value)
    return "*" * (len(value) - visible) + value[-visible:]


# ---------------------------------------------------------------------------
# Tab completer
# ---------------------------------------------------------------------------


class ScrapperCompleter(Completer):
    """Provides tab completion for the scrapper interactive shell."""

    COMMANDS = [
        "search", "s",
        "list", "l",
        "download", "dl",
        "download-all", "dla",
        "settings",
        "sources",
        "config",
        "stats",
        "clear", "cls",
        "help", "h",
        "quit", "q", "exit",
    ]

    FLAGS = ["--artist", "-a", "--sources", "-src"]

    SOURCES = [
        "youtube", "spotify", "audiomack",
        "apple_music", "midi_db",
    ]

    def get_completions(self, document, complete_event):
        text = document.text_before_cursor.lstrip()
        word = document.get_word_before_cursor()

        if not text:
            for cmd in self.COMMANDS:
                yield Completion(cmd, start_position=0)
            return

        parts = text.split()
        current = parts[-1] if parts else ""

        if current in ("--sources", "-src") or (
            len(parts) >= 2 and parts[-2] in ("--sources", "-src")
        ):
            for src in self.SOURCES:
                if src.startswith(word):
                    yield Completion(src, start_position=-len(word))
            return

        if current in ("--artist", "-a") or (
            len(parts) >= 2 and parts[-2] in ("--artist", "-a")
        ):
            return

        if len(parts) == 1 and text == current:
            for cmd in self.COMMANDS:
                if cmd.startswith(word):
                    yield Completion(cmd, start_position=-len(word))
            return

        if len(parts) >= 2:
            used_flags = {p for p in parts[1:] if p.startswith("-")}
            for flag in self.FLAGS:
                if flag not in used_flags and flag.startswith(word):
                    yield Completion(flag, start_position=-len(word))


# ---------------------------------------------------------------------------
# Interactive Shell
# ---------------------------------------------------------------------------


class InteractiveShell:
    """REPL for testing the scrapper framework interactively."""

    def __init__(self) -> None:
        _ensure_config_dir()

        self.user_config = _load_user_config()
        self._apply_env_overrides()

        self.scraper = SongScraper()
        self.results: list[SearchResult] = []
        self.last_query: str = ""

        self.session = PromptSession(
            history=FileHistory(HISTORY_FILE),
            completer=ScrapperCompleter(),
            auto_suggest=AutoSuggestFromHistory(),
            message=FormattedText([("", "\n"), ("bold", "scrapper> ")]),
        )

        self._show_help()

    def run(self) -> None:
        while True:
            try:
                cmd = self.session.prompt().strip()
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
    # Command dispatch
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
            "settings": self._cmd_settings,
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
    # Config helpers
    # ------------------------------------------------------------------

    def _apply_env_overrides(self) -> None:
        spotify = self.user_config.get("spotify", {})
        if spotify.get("client_id"):
            os.environ.setdefault("SPOTIFY_CLIENT_ID", spotify["client_id"])
        if spotify.get("client_secret"):
            os.environ.setdefault(
                "SPOTIFY_CLIENT_SECRET", spotify["client_secret"]
            )

    def _reload_scraper(self) -> None:
        self.scraper = SongScraper()

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------

    def _cmd_help(self, _: str = "") -> None:
        self._show_help()

    def _cmd_search(self, args: str) -> None:
        if not args:
            _print_error(
                "Usage: search <song> [--artist <name>] [--sources src1,src2]"
            )
            return

        song = args
        artist: Optional[str] = None
        sources: Optional[list[str]] = None

        for sep in (" --artist ", " -a "):
            if sep in args:
                parts = args.split(sep, 1)
                song = parts[0].strip()
                remainder = parts[1].strip()
                if " --sources " in remainder:
                    artist, src_part = remainder.split(" --sources ", 1)
                    sources = [s.strip() for s in src_part.split(",")]
                elif " -src " in remainder:
                    artist, src_part = remainder.split(" -src ", 1)
                    sources = [s.strip() for s in src_part.split(",")]
                else:
                    artist = remainder
                break

        if sources is None:
            for sep in (" --sources ", " -src "):
                if sep in song:
                    parts = song.split(sep, 1)
                    song = parts[0].strip()
                    sources = [s.strip() for s in parts[1].split(",")]
                    break

        self.last_query = f"{song} ({artist or 'any artist'})"
        src_str = f" [{', '.join(sources)}]" if sources else ""

        _print_header(
            f"🔍 Searching: {song}"
            + (f" by {artist}" if artist else "")
            + src_str
        )

        self.results = self.scraper.search(
            song, artist=artist, sources=sources
        )

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

    @staticmethod
    def _parse_indices(raw: str, max_index: int) -> list[int]:
        """Parse '1,2,3' or '1-5' or '1,3,5-7' into 0-based index list."""
        indices: set[int] = set()
        for part in raw.split(","):
            part = part.strip()
            if not part:
                continue
            if "-" in part:
                try:
                    start_s, end_s = part.split("-", 1)
                    start, end = int(start_s.strip()), int(end_s.strip())
                    for i in range(start, end + 1):
                        if 1 <= i <= max_index:
                            indices.add(i - 1)
                except ValueError:
                    continue
            else:
                try:
                    i = int(part)
                    if 1 <= i <= max_index:
                        indices.add(i - 1)
                except ValueError:
                    continue
        return sorted(indices)

    def _report_downloads(self, dl_results: list) -> None:
        """Print download results in a consistent format."""
        success = sum(1 for d in dl_results if d.success)
        failed = sum(1 for d in dl_results if not d.success)
        for d in dl_results:
            if d.success:
                print(f"  {GREEN}✅{RESET} {d.result.title}: {d.file_path}")
            else:
                print(f"  {RED}❌{RESET} {d.result.title}: {d.error}")
        print()
        _print_success(f"{success} downloaded, {failed} failed")

    def _cmd_download(self, args: str) -> None:
        if not self.results:
            _print_info("No cached results. Run 'search' first.")
            return
        if not args:
            _print_error(
                "Usage: download <index>    e.g. dl 1   dl 1,2,3   dl 1-5   dl 1,3,5-7"
            )
            return

        indices = self._parse_indices(args.strip(), len(self.results))
        if not indices:
            _print_error(
                f"Invalid index. Use numbers 1–{len(self.results)}. "
                "Examples: dl 1   dl 1,2,3   dl 1-5   dl 1,3,5-7"
            )
            return

        selected = [self.results[i] for i in indices]

        if len(selected) == 1:
            # Single download
            result = selected[0]
            _print_header(
                f"⬇️  Downloading: {result.title}"
                + (f" — {result.artist}" if result.artist else "")
            )
            dl = self.scraper.download_best([result])
            if dl.success:
                _print_success(f"Saved to: {dl.file_path}")
            else:
                _print_error(f"Download failed: {dl.error or 'Unknown error'}")
        else:
            # Multiple — download concurrently
            names = ", ".join(
                f"#{i+1}" for i in indices
            )
            _print_header(f"⬇️  Downloading {len(selected)} results ({names})")
            dl_results = self.scraper.download_all(selected)
            self._report_downloads(dl_results)

    def _cmd_download_all(self, _: str = "") -> None:
        if not self.results:
            _print_info("No cached results. Run 'search' first.")
            return
        _print_header(f"⬇️  Downloading all {len(self.results)} results")
        dl_results = self.scraper.download_all(self.results)
        self._report_downloads(dl_results)

    def _cmd_settings(self, _: str = "") -> None:
        config = _load_user_config()
        spotify = config.setdefault("spotify", {})
        download = config.setdefault("download", {})

        while True:
            _print_header("⚙️  Settings")
            print(
                f"  {BOLD}1.{RESET} Spotify Client ID     : "
                f"{_mask(spotify.get('client_id', ''))}\n"
                f"  {BOLD}2.{RESET} Spotify Client Secret : "
                f"{_mask(spotify.get('client_secret', ''))}\n"
                f"  {BOLD}3.{RESET} Download Directory    : "
                f"{download.get('directory', './data/raw')}\n"
                f"  {BOLD}4.{RESET} Max Concurrent        : "
                f"{download.get('max_concurrent', 3)}\n"
                f"  {BOLD}5.{RESET} Max Retries           : "
                f"{download.get('max_retries', 3)}\n"
                f"  {BOLD}6.{RESET} Timeout (seconds)     : "
                f"{download.get('timeout', 60)}\n"
                f"\n"
                f"  {DIM}Enter number to edit, 's' to save, 'q' to quit{RESET}\n"
            )

            choice = self.session.prompt("  choice> ").strip().lower()
            if choice == "q":
                break
            if choice == "s":
                _save_user_config(config)
                self.user_config = config
                self._apply_env_overrides()
                self._reload_scraper()
                _print_success("Settings saved")
                break

            if choice == "1":
                val = self.session.prompt(
                    "  Spotify Client ID: ",
                    default=spotify.get("client_id", ""),
                ).strip()
                spotify["client_id"] = val
            elif choice == "2":
                val = self.session.prompt(
                    "  Spotify Client Secret: ",
                    default=spotify.get("client_secret", ""),
                ).strip()
                spotify["client_secret"] = val
            elif choice == "3":
                val = self.session.prompt(
                    "  Download Directory (Tab to autocomplete): ",
                    default=download.get("directory", "./data/raw"),
                    completer=PathCompleter(),
                ).strip()
                download["directory"] = os.path.abspath(
                    os.path.expanduser(val)
                )
            elif choice == "4":
                try:
                    val = int(
                        self.session.prompt(
                            "  Max Concurrent: ",
                            default=str(download.get("max_concurrent", 3)),
                        ).strip()
                    )
                    download["max_concurrent"] = max(1, val)
                except ValueError:
                    _print_error("Enter a valid number")
            elif choice == "5":
                try:
                    val = int(
                        self.session.prompt(
                            "  Max Retries: ",
                            default=str(download.get("max_retries", 3)),
                        ).strip()
                    )
                    download["max_retries"] = max(0, val)
                except ValueError:
                    _print_error("Enter a valid number")
            elif choice == "6":
                try:
                    val = int(
                        self.session.prompt(
                            "  Timeout (seconds): ",
                            default=str(download.get("timeout", 60)),
                        ).strip()
                    )
                    download["timeout"] = max(5, val)
                except ValueError:
                    _print_error("Enter a valid number")
            else:
                _print_error(f"Invalid choice: '{choice}'")

    def _cmd_sources(self, _: str = "") -> None:
        _print_header("📡 Registered Sources")
        adapters = self.scraper.registry.get_by_priority()
        for a in adapters:
            print(f"  {BOLD}{a.name:^12}{RESET}  priority: {a.priority}")

    def _cmd_config(self, _: str = "") -> None:
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
        os.system("cls" if os.name == "nt" else "clear")

    def _cmd_stats(self, _: str = "") -> None:
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
        print(f"\n{YELLOW}👋 Goodbye!{RESET}")
        sys.exit(0)

    # ------------------------------------------------------------------
    # Help
    # ------------------------------------------------------------------

    @staticmethod
    def _show_help() -> None:
        _print_header("🎵 Scrapper Interactive Shell")
        print(
            f"  {BOLD}search <song> [--artist <name>]{RESET}\n"
            f"    {'':>4}{DIM}Search across all sources{RESET}\n"
            f"\n"
            f"  {BOLD}s <song> [-a name] [-src yt,spotify]{RESET}\n"
            f"    {'':>4}{DIM}Short form with source filter{RESET}\n"
            f"\n"
            f"  {BOLD}list{RESET}     {DIM}Show cached results{RESET}\n"
            f"  {BOLD}download <n>{RESET}  {DIM}dl 1  |  dl 1,2,3  |  dl 1-5  |  dl 1,3,5-7{RESET}\n"
            f"  {BOLD}download-all{RESET}  {DIM}Download all cached results{RESET}\n"
            f"  {BOLD}settings{RESET}  {DIM}Open settings editor{RESET}\n"
            f"  {BOLD}sources{RESET}   {DIM}List sources{RESET}\n"
            f"  {BOLD}config{RESET}    {DIM}Show configuration{RESET}\n"
            f"  {BOLD}stats{RESET}     {DIM}Search statistics{RESET}\n"
            f"  {BOLD}clear{RESET}     {DIM}Clear terminal{RESET}\n"
            f"  {BOLD}help{RESET}      {DIM}This help{RESET}\n"
            f"  {BOLD}quit{RESET}      {DIM}Exit{RESET}\n"
            f"\n"
            f"  {DIM}Tab / ↑↓ / auto-suggest enabled{RESET}\n"
            f"  {DIM}Config & history: ~/.config/scrapper/{RESET}\n"
        )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Launch the interactive shell."""
    shell = InteractiveShell()
    try:
        shell.run()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}👋 Goodbye!{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
