# cli-anything-go-music-dl

An AI-agent-friendly CLI for **go-music-dl** — the aggregated music search and download tool supporting 13+ music platforms.

## Prerequisites

1. **go-music-dl binary** — Build from source (Go 1.25+ required):
   ```bash
   cd go-music-dl
   go build -o music-dl ./cmd/music-dl
   ```

2. **Python** 3.10+ with pip

3. **Dependencies**:
   ```bash
   pip install click requests beautifulsoup4 prompt-toolkit
   ```

## Installation

```bash
cd agent-harness
pip install -e .
```

## Usage

### REPL (default)

```bash
cli-anything-go-music-dl
```

### One-shot commands

```bash
# Start the backend server
cli-anything-go-music-dl server start

# Search songs
cli-anything-go-music-dl search "周杰伦"
cli-anything-go-music-dl --json search "周杰伦" --source netease

# Search playlists/albums
cli-anything-go-music-dl search "热门歌单" --type playlist

# Inspect/download a song
cli-anything-go-music-dl inspect --id 123456 --source netease
cli-anything-go-music-dl download --id 123456 --source netease --name "Song" --artist "Artist"

# Get playlist/album songs
cli-anything-go-music-dl playlist netease 123456
cli-anything-go-music-dl album qq 789012

# List sources
cli-anything-go-music-dl sources

# Manage cookies
cli-anything-go-music-dl cookies set netease "MUSIC_U=xxx"
cli-anything-go-music-dl cookies list

# Project management
cli-anything-go-music-dl project new my-project
cli-anything-go-music-dl project info

# Session management
cli-anything-go-music-dl status
cli-anything-go-music-dl history
```

## Supported Sources

| Source | Name |
|--------|------|
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

## JSON Output

All commands support `--json` flag for machine-readable output:

```bash
cli-anything-go-music-dl --json search "周杰伦" --source netease
```

## Development

```bash
# Install in dev mode
pip install -e .

# Run tests
pytest cli_anything/go_music_dl/tests/ -v

# Run with force-installed check
CLI_ANYTHING_FORCE_INSTALLED=1 pytest cli_anything/go_music_dl/tests/ -v
```

## Architecture

The CLI uses the go-music-dl web server as its backend:

1. **Start** the Go binary's web server (`music-dl web`) as a managed subprocess
2. **Communicate** via HTTP to the web server's JSON API
3. **Parse** search result HTML when JSON endpoints are not available (BeautifulSoup)
4. **Manage** state via JSON session files with file locking

See `GO_MUSIC_DL.md` for the full architecture documentation.
