# scrapper — Song Audio Scraper

> **Status**: Pre-Alpha | **License**: Proprietary

A modular song audio scraper that fetches MP3, MIDI, M4A, and other audio formats from multiple online sources. Given a **song name** and optional **artist**, it searches across YouTube, Spotify, Audiomack, Apple Music, and MIDI databases, then downloads the best match.

---

## Features

- **Multi-source search**: YouTube (yt-dlp), Spotify (Web API), Audiomack (scraping), Apple Music (iTunes API), MIDI databases
- **Plugin architecture**: Easy to add new sources — just implement the `SourceAdapter` interface
- **Concurrent downloads**: Configurable thread pool with retry and rate limiting
- **Smart ranking**: Results scored by relevance, deduplicated, and sorted by quality
- **CLI + Python API**: Use as a command-line tool or import as a library
- **Companion metadata**: Every download comes with a `.meta.json` file
- **Modular docs**: Per-component documentation with timestamped changelogs

---

## Quick Start

### Installation

```bash
# Install from source
pip install -e .

# With optional Spotify support
pip install -e ".[spotify]"

# Everything
pip install -e ".[all]"
```

### CLI Usage

```bash
# Search and download best result
scrapper search "Bohemian Rhapsody" --artist "Queen"

# Search only (list results without downloading)
scrapper search "Bohemian Rhapsody" --artist "Queen" --search-only

# Download all results from specific sources
scrapper search "Bohemian Rhapsody" --sources youtube,spotify --download-all

# Filter by format
scrapper search "Song Title" --format mp3

# Verbose logging
scrapper search "Song Title" --artist "Artist" --verbose
```

### Python API

```python
from scrapper import SongScraper

scraper = SongScraper()

# Search across all enabled sources
results = scraper.search("Bohemian Rhapsody", artist="Queen")

# Download the best match
downloaded = scraper.download_best(results)
print(f"Downloaded to: {downloaded.file_path}")

# Or download all results concurrently
all_downloads = scraper.download_all(results)
```

---

## Project Structure

```
./
├── scrapper/                # Main module
│   ├── __init__.py          # SongScraper — public API
│   ├── cli.py               # CLI entry point
│   ├── models.py            # Data models
│   ├── downloader.py        # Download Manager
│   ├── organizer.py         # File Organizer
│   ├── exceptions.py        # Custom exceptions
│   └── sources/             # Source adapters
│       ├── base.py           # Abstract base class
│       ├── registry.py       # Source registry
│       ├── youtube.py        # YouTube (yt-dlp)
│       ├── spotify.py        # Spotify (Web API)
│       ├── audiomack.py      # Audiomack (scraping)
│       ├── apple_music.py    # Apple Music (iTunes API)
│       └── midi_db.py        # MIDI databases
├── config/
│   └── scraper.yaml          # Configuration
├── tests/
│   └── test_scrapper/        # Unit tests
├── docs/                     # Documentation (not committed)
├── plans/                    # Architecture plans
└── pyproject.toml             # Dependencies & metadata
```

---

## Source Adapters

| Source      | Priority | Method                 | Formats            | Auth Required |
| ----------- | -------- | ---------------------- | ------------------ | ------------- |
| YouTube     | 100      | yt-dlp extraction      | MP3 (via FFmpeg)   | No            |
| Spotify     | 90       | Web API previews       | MP3 (30s clips)    | API keys      |
| Audiomack   | 85       | Web scraping           | MP3 (full songs)   | No            |
| Apple Music | 80       | iTunes Search API      | M4A (30s previews) | No            |
| MIDI DB     | 70       | Web scraping (3 sites) | MIDI               | No            |

### Spotify Setup

To enable the Spotify source, set these environment variables:

```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
```

You can also add them to a `.env` file in the project root.

---

## Configuration

See [`config/scraper.yaml`](config/scraper.yaml) for all available options:

```yaml
scraper:
  sources:
    youtube:
      enabled: true
      rate_limit: 1.0
    spotify:
      enabled: true
      rate_limit: 0.5

  download:
    max_concurrent: 3
    max_retries: 3
    timeout: 60
    directory: ./data/raw
```

---

## Development

### Running Tests

```bash
# Install dev dependencies
pip install pytest click

# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_scrapper/test_models.py -v
```

### Adding a New Source

1. Create `scrapper/sources/your_source.py`
2. Extend `SourceAdapter` and implement `search()` + `download()`
3. Set `name` and `priority` class attributes
4. Register it in `scrapper/__init__.py` `_DEFAULT_SOURCES` list
5. Create docs at `docs/your_source/overview.md` + `changelog.md`

### Commit Convention

Commits are chronological and grouped by common scope:

```
Project scaffold
Data models & base adapter
YouTube source adapter
Download Manager & File Organizer
Public API, CLI, config & exceptions
...
```

---

## Documentation

Documentation lives in `docs/` and is **not committed to version control** (see `.gitignore`). Each component has its own directory with a changelog:

```
docs/
├── overview.md
├── architecture.md
├── changelog.md              # Master changelog
├── youtube/overview.md       # YouTube source
├── youtube/changelog.md
├── spotify/overview.md       # Spotify source
├── spotify/changelog.md
├── audiomack/overview.md
├── audiomack/changelog.md
├── apple_music/overview.md
├── apple_music/changelog.md
├── midi/overview.md
├── midi/changelog.md
├── downloader/overview.md
├── downloader/changelog.md
└── api/overview.md
```
