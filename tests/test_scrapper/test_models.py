"""Unit tests for data models."""

from scrapper.models import AudioFormat, DownloadResult, Quality, SearchResult


class TestAudioFormat:
    def test_values(self) -> None:
        assert AudioFormat.MP3.value == "mp3"
        assert AudioFormat.MIDI.value == "midi"
        assert AudioFormat.M4A.value == "m4a"
        assert AudioFormat.WAV.value == "wav"
        assert AudioFormat.FLAC.value == "flac"
        assert AudioFormat.WEBM.value == "webm"
        assert AudioFormat.OPUS.value == "opus"

    def test_str(self) -> None:
        assert str(AudioFormat.MP3) == "mp3"


class TestQuality:
    def test_values(self) -> None:
        assert Quality.LOW.value == "low"
        assert Quality.MEDIUM.value == "medium"
        assert Quality.HIGH.value == "high"
        assert Quality.LOSSLESS.value == "lossless"

    def test_str(self) -> None:
        assert str(Quality.HIGH) == "high"


class TestSearchResult:
    def test_minimal(self) -> None:
        r = SearchResult(
            title="Test Song",
            artist="Test Artist",
            duration=180,
            format=AudioFormat.MP3,
            quality=Quality.HIGH,
            source="youtube",
            url="https://example.com/song",
        )
        assert r.title == "Test Song"
        assert r.artist == "Test Artist"
        assert r.duration == 180
        assert r.format == AudioFormat.MP3
        assert r.quality == Quality.HIGH
        assert r.source == "youtube"
        assert r.url == "https://example.com/song"
        assert r.score == 0.0
        assert r.file_size is None
        assert r.metadata == {}

    def test_with_all_fields(self) -> None:
        r = SearchResult(
            title="Full Song",
            artist="Artist",
            duration=240,
            format=AudioFormat.M4A,
            quality=Quality.LOSSLESS,
            source="apple_music",
            url="https://example.com/full",
            file_size=10_000_000,
            score=0.95,
            metadata={"album": "Greatest Hits"},
        )
        assert r.file_size == 10_000_000
        assert r.score == 0.95
        assert r.metadata["album"] == "Greatest Hits"

    def test_without_artist(self) -> None:
        r = SearchResult(
            title="Instrumental",
            artist=None,
            duration=120,
            format=AudioFormat.MIDI,
            quality=Quality.MEDIUM,
            source="midi_db",
            url="https://example.com/midi",
        )
        assert r.artist is None


class TestDownloadResult:
    def test_success(self) -> None:
        sr = SearchResult(
            title="Song",
            artist="Artist",
            duration=200,
            format=AudioFormat.MP3,
            quality=Quality.HIGH,
            source="youtube",
            url="https://example.com/song",
        )
        dr = DownloadResult(
            result=sr,
            file_path="/data/raw/mp3/Artist/Song--youtube.mp3",
            success=True,
        )
        assert dr.success is True
        assert dr.error is None
        assert dr.result is sr

    def test_failure(self) -> None:
        sr = SearchResult(
            title="Failed",
            artist=None,
            duration=0,
            format=AudioFormat.MP3,
            quality=Quality.LOW,
            source="test",
            url="https://example.com/fail",
        )
        dr = DownloadResult(
            result=sr,
            file_path="",
            success=False,
            error="Connection timeout",
        )
        assert dr.success is False
        assert dr.error == "Connection timeout"
