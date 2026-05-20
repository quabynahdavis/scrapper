"""Tests for source adapter base and registry."""

from typing import Optional

import pytest

from scrapper.models import AudioFormat, DownloadResult, Quality, SearchResult
from scrapper.sources import SourceAdapter, SourceRegistry


# ---------------------------------------------------------------------------
# Stub adapter for testing
# ---------------------------------------------------------------------------


class StubSource(SourceAdapter):
    name = "stub"
    priority = 50

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list[SearchResult]:
        return [
            SearchResult(
                title=song,
                artist=artist,
                duration=200,
                format=AudioFormat.MP3,
                quality=Quality.HIGH,
                source=self.name,
                url=f"https://stub.example/{song}",
                score=0.8,
            )
        ]

    def download(
        self,
        result: SearchResult,
        dest_dir: str,
    ) -> DownloadResult:
        return DownloadResult(
            result=result,
            file_path=f"{dest_dir}/stub.mp3",
            success=True,
        )


class HighPrioritySource(SourceAdapter):
    name = "high"
    priority = 100

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list[SearchResult]:
        return []

    def download(
        self,
        result: SearchResult,
        dest_dir: str,
    ) -> DownloadResult:
        return DownloadResult(result=result, file_path="", success=False)


class LowPrioritySource(SourceAdapter):
    name = "low"
    priority = 10

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list[SearchResult]:
        return []

    def download(
        self,
        result: SearchResult,
        dest_dir: str,
    ) -> DownloadResult:
        return DownloadResult(result=result, file_path="", success=False)


# ---------------------------------------------------------------------------
# SourceAdapter tests
# ---------------------------------------------------------------------------


class TestSourceAdapter:
    def test_name_property(self) -> None:
        assert StubSource().name == "stub"

    def test_search_returns_list(self) -> None:
        adapter = StubSource()
        results = adapter.search("Test", artist="Artist")
        assert isinstance(results, list)
        assert len(results) == 1
        assert results[0].title == "Test"

    def test_download_returns_result(self) -> None:
        adapter = StubSource()
        sr = SearchResult(
            title="S",
            artist="A",
            duration=100,
            format=AudioFormat.MP3,
            quality=Quality.MEDIUM,
            source="stub",
            url="https://example.com/s",
        )
        dr = adapter.download(sr, "/tmp")
        assert isinstance(dr, DownloadResult)
        assert dr.success is True


# ---------------------------------------------------------------------------
# SourceRegistry tests
# ---------------------------------------------------------------------------


class TestSourceRegistry:
    def test_register_and_get(self) -> None:
        registry = SourceRegistry()
        registry.register(StubSource())
        assert registry.get("stub") is not None
        assert registry.count == 1

    def test_register_duplicate_raises(self) -> None:
        registry = SourceRegistry()
        registry.register(StubSource())
        with pytest.raises(ValueError, match="already registered"):
            registry.register(StubSource())

    def test_unregister(self) -> None:
        registry = SourceRegistry()
        registry.register(StubSource())
        registry.unregister("stub")
        assert registry.get("stub") is None
        assert registry.count == 0

    def test_get_all(self) -> None:
        registry = SourceRegistry()
        registry.register(HighPrioritySource())
        registry.register(LowPrioritySource())
        assert len(registry.get_all()) == 2

    def test_get_by_priority_order(self) -> None:
        registry = SourceRegistry()
        registry.register(LowPrioritySource())  # priority 10
        registry.register(HighPrioritySource())  # priority 100
        ordered = registry.get_by_priority()
        assert ordered[0].name == "high"
        assert ordered[1].name == "low"

    def test_get_by_names(self) -> None:
        registry = SourceRegistry()
        registry.register(HighPrioritySource())
        registry.register(StubSource())
        registry.register(LowPrioritySource())
        selected = registry.get_by_names(["stub", "high"])
        # Should be ordered by priority: high (100) then stub (50)
        assert len(selected) == 2
        assert selected[0].name == "high"
        assert selected[1].name == "stub"
