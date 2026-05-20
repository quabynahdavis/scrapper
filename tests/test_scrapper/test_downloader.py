"""Tests for the Download Manager."""

from typing import Optional

from scrapper.downloader import DownloadConfig, DownloadManager
from scrapper.models import AudioFormat, DownloadResult, Quality, SearchResult
from scrapper.sources import SourceAdapter


# ---------------------------------------------------------------------------
# Stub adapter that always succeeds
# ---------------------------------------------------------------------------

class AlwaysSuccessSource(SourceAdapter):
    name = "success"
    priority = 100

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list:
        return []

    def download(
        self,
        result: SearchResult,
        dest_dir: str,
    ) -> DownloadResult:
        return DownloadResult(
            result=result,
            file_path=f"{dest_dir}/success.mp3",
            success=True,
        )


# ---------------------------------------------------------------------------
# Stub adapter that always fails
# ---------------------------------------------------------------------------

class AlwaysFailSource(SourceAdapter):
    name = "fail"
    priority = 50

    def search(
        self,
        song: str,
        artist: Optional[str] = None,
    ) -> list:
        return []

    def download(
        self,
        result: SearchResult,
        dest_dir: str,
    ) -> DownloadResult:
        return DownloadResult(
            result=result,
            file_path="",
            success=False,
            error="Simulated failure",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_result(title: str = "Test", source: str = "success") -> SearchResult:
    return SearchResult(
        title=title,
        artist="Artist",
        duration=180,
        format=AudioFormat.MP3,
        quality=Quality.HIGH,
        source=source,
        url=f"https://example.com/{title}",
        score=0.9,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDownloadManager:
    def test_single_success(self) -> None:
        manager = DownloadManager(DownloadConfig(max_retries=1))
        result = _make_result()
        adapter = AlwaysSuccessSource()
        dl = manager.download(result, adapter)
        assert dl.success is True
        assert dl.file_path != ""

    def test_single_failure_no_retries(self) -> None:
        manager = DownloadManager(DownloadConfig(max_retries=1))
        result = _make_result(source="fail")
        adapter = AlwaysFailSource()
        dl = manager.download(result, adapter)
        assert dl.success is False
        assert dl.error == "Simulated failure"

    def test_progress_callback(self) -> None:
        manager = DownloadManager(DownloadConfig(max_retries=1))
        result = _make_result()
        adapter = AlwaysSuccessSource()

        calls: list[tuple[int, int]] = []

        def callback(completed: int, total: int, _dl: DownloadResult) -> None:
            calls.append((completed, total))

        manager.download(result, adapter, progress_callback=callback)
        assert len(calls) == 1
        assert calls[0] == (1, 1)

    def test_download_many_all_success(self) -> None:
        manager = DownloadManager(DownloadConfig(max_retries=1, max_concurrent=2))
        adapter = AlwaysSuccessSource()
        results = [_make_result(title=f"Song {i}") for i in range(3)]
        items = [(r, adapter) for r in results]

        dl_results = manager.download_many(items)
        assert len(dl_results) == 3
        assert all(d.success for d in dl_results)

    def test_download_many_mixed(self) -> None:
        manager = DownloadManager(DownloadConfig(max_retries=1, max_concurrent=2))
        success_adapter = AlwaysSuccessSource()
        fail_adapter = AlwaysFailSource()

        items = [
            (_make_result(title="Good", source="success"), success_adapter),
            (_make_result(title="Bad", source="fail"), fail_adapter),
        ]

        dl_results = manager.download_many(items)
        assert len(dl_results) == 2
        assert dl_results[0].success is True
        assert dl_results[1].success is False
