"""Tests for the CLI interface using Click's CliRunner."""

from click.testing import CliRunner

from scrapper.cli import cli


class TestCLI:
    def setup_method(self) -> None:
        self.runner = CliRunner()

    def test_help(self) -> None:
        result = self.runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "Search and download" in result.output

    def test_search_help(self) -> None:
        result = self.runner.invoke(cli, ["search", "--help"])
        assert result.exit_code == 0
        assert "Search and optionally download" in result.output
        assert "SONG" in result.output

    def test_version(self) -> None:
        result = self.runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_search_empty_song_shows_error(self) -> None:
        # Click should reject empty required argument
        result = self.runner.invoke(cli, ["search"])
        assert result.exit_code != 0
        assert "Error" in result.output or "Missing argument" in result.output

    def test_search_with_artist_option(self) -> None:
        result = self.runner.invoke(
            cli,
            ["search", "Bohemian Rhapsody", "--artist", "Queen"],
        )
        # Should either succeed (mock) or show "No results" — not crash
        assert result.exit_code == 0

    def test_search_only_flag(self) -> None:
        result = self.runner.invoke(
            cli,
            ["search", "Test Song", "--search-only"],
        )
        assert result.exit_code == 0

    def test_download_all_flag(self) -> None:
        result = self.runner.invoke(
            cli,
            ["search", "Test Song", "--download-all"],
        )
        assert result.exit_code == 0

    def test_format_option(self) -> None:
        result = self.runner.invoke(
            cli,
            ["search", "Song", "--format", "mp3", "--search-only"],
        )
        assert result.exit_code == 0

    def test_sources_option(self) -> None:
        result = self.runner.invoke(
            cli,
            ["search", "Song", "--sources", "youtube,spotify", "--search-only"],
        )
        assert result.exit_code == 0
