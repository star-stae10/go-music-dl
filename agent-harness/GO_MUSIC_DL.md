# go-music-dl — Aggregated Music Search & Download CLI

## Overview

go-music-dl is a Go-based aggregated music search and download tool that supports
13+ Chinese and international music platforms. It provides a TUI (BubbleTea),
a web interface (Gin), and desktop apps.

This harness builds a Python CLI (`cli-anything-go-music-dl`) that wraps the
Go binary's web server as a backend HTTP API, providing structured JSON output
for AI agents and a stateful REPL for interactive use.

## Architecture

```
┌──────────────────────┐     HTTP      ┌────────────────────┐
│  Python CLI          │ ────────────→ │  music-dl web      │
│  (Click + REPL)      │ ←──────────── │  (Go Gin Web App)  │
│                      │    JSON/HTML  │                    │
│  cli-anything-       │               │  Backend:          │
│  go-music-dl         │               │  - music-lib API   │
│                      │               │  - Core download   │
└──────────────────────┘               └────────────────────┘
```

### Key Design Decisions

1. **Backend**: The Go binary's **web server** (`music-dl web`) serves as the
   real backend. The Python CLI starts it as a managed subprocess and communicates
   via HTTP. This follows HARNESS.md's "Use the Real Software" rule.

2. **Stateful Sessions**: Session state (project path, active source, download
   settings, cookies) is persisted to JSON session files with file locking.

3. **Output Modes**: All commands support `--json` for machine-readable output
   and human-readable formatted output by default.

4. **Dual Mode**: Both one-shot commands and a REPL mode (default).

## Command Groups

| Group | Description |
|-------|-------------|
| `search` | Search songs, playlists, albums across sources |
| `download` | Download songs by ID/URL |
| `playlist` | Browse and download playlists |
| `album` | Browse and download albums |
| `inspect` | Get download info (URL, size, bitrate) for a song |
| `cookies` | Manage authentication cookies per source |
| `settings` | View and modify web/download settings |
| `sources` | List supported music sources |
| `server` | Start/stop/manage the backend web server |
| `session` | Manage project sessions |

## Data Model

### Song
```
{
  "id": "123456",
  "name": "Song Name",
  "artist": "Artist Name",
  "album": "Album Name",
  "album_id": "789",
  "source": "netease",
  "cover": "https://...",
  "duration": 240,
  "link": "https://...",
  "extra": {"album": "..."}
}
```

### Playlist / Album
```
{
  "id": "123456",
  "name": "Playlist Name",
  "description": "Description",
  "cover": "https://...",
  "creator": "Creator Name",
  "track_count": 50,
  "source": "netease",
  "link": "https://..."
}
```

### Settings
```
{
  "embedDownload": true,
  "downloadToLocal": true,
  "downloadDir": "data/downloads",
  "downloadFilenameTemplate": "{name} - {artist}",
  "webPageSize": 30,
  "cliPageSize": 20,
  "downloadConcurrency": 3
}
```

## Supported Sources

| Key | Name |
|-----|------|
| `netease` | 网易云音乐 |
| `qq` | QQ音乐 |
| `kugou` | 酷狗音乐 |
| `kuwo` | 酷我音乐 |
| `migu` | 咪咕音乐 |
| `qianqian` | 千千音乐 |
| `soda` | 汽水音乐 |
| `fivesing` | 5sing |
| `jamendo` | Jamendo (CC) |
| `joox` | JOOX |
| `bilibili` | Bilibili |
| `apple` | Apple Music |
| `local` | 本地音乐 |

## Backend API Endpoints

| Endpoint | Method | Returns | Used For |
|----------|--------|---------|----------|
| `/music/healthz` | GET | JSON | Health check |
| `/music/search` | GET | HTML | Song/playlist/album search |
| `/music/inspect` | GET | JSON | Song download URL inspection |
| `/music/download` | GET | JSON/File | Download songs |
| `/music/playlist` | GET | HTML | Playlist songs |
| `/music/album` | GET | HTML | Album songs |
| `/music/cookies` | GET/POST | JSON | Cookie management |
| `/music/settings` | GET/POST | JSON | Settings management |
| `/music/switch_source` | GET | JSON | Switch music source |

## Session File Format

Session files (.json) store the CLI state between commands:

```json
{
  "version": "1.0",
  "project": {
    "name": "my-project",
    "created_at": "2026-07-18T12:00:00",
    "active_source": "netease",
    "download_dir": "./downloads",
    "with_cover": true,
    "with_lyrics": true
  },
  "server": {
    "port": 8080,
    "pid": 12345,
    "started_at": "2026-07-18T12:00:00",
    "status": "running"
  },
  "download_history": [
    {
      "song_id": "123456",
      "source": "netease",
      "name": "Song Name",
      "path": "./downloads/Song - Artist.mp3",
      "timestamp": "2026-07-18T12:05:00"
    }
  ]
}
```

## Auto-Save + --dry-run

The CLI implements auto-save for one-shot commands via `@cli.result_callback()`.
A `--dry-run` flag suppresses the save. See `guides/auto-save-dry-run.md`.
