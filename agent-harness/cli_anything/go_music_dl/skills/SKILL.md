---
name: cli-anything:go-music-dl
description: AI-agent-friendly CLI for go-music-dl — aggregated music search & download supporting 13+ platforms
author: go-music-dl contributors
version: 1.0.0
type: skill
namespace: cli_anything.go_music_dl
requires:
  - go-music-dl binary (for backend server: `music-dl web`)
---

# cli-anything-go-music-dl

An AI-agent-friendly CLI harness for **[go-music-dl](https://github.com/guohuiyuan/go-music-dl)**, the aggregated music search and download tool supporting 13+ music platforms.

## Installation

```bash
pip install cli-anything-go-music-dl

# Or from source:
cd agent-harness
pip install -e .
```

Optional extras:
```bash
pip install -e ".[repl]"     # REPL support (prompt-toolkit)
pip install -e ".[parsing]"  # URL parsing (beautifulsoup4)
```

## CLI Quick Reference

### Global Options

| Option | Description |
|--------|-------------|
| `--json` | Output as JSON (for AI agent consumption) |
| `--project <path>` | Path to project file (loads on start) |
| `--dry-run` | Run without saving changes |
| `--version` | Show version and exit |
| `--help` | Show help message |

### Commands

| Command | Description |
|---------|-------------|
| `sources` | List all supported music sources (netease, qq, kugou, kuwo, migu, etc.) |
| `search <keyword>` | Search songs across music sources |
| `inspect --id <id> -s <source>` | Inspect a song (download URL, size, bitrate) |
| `download --id <id> -s <source>` | Download a song by ID |
| `parse <url>` | Parse a music share URL to extract source and ID |
| `playlist <source> <id>` | Get songs from a playlist |
| `album <source> <id>` | Get songs from an album |
| `server start/stop/status` | Manage the backend music-dl web server |
| `cookies` | Manage authentication cookies per source |
| `settings` | View and modify configuration settings |
| `project new/save/info/set` | Manage music-dl projects |
| `status` | Show current session status |
| `history` | Show download history |
| `undo` / `redo` | Undo/redo project state changes |

### Project Commands

| Subcommand | Description |
|------------|-------------|
| `project new <name>` | Create a new project |
| `project info` | Show project info |
| `project save` | Save project to file |
| `project set <key> <value>` | Set project property |

### Server Commands

| Subcommand | Description |
|------------|-------------|
| `server start` | Start the backend web server |
| `server stop` | Stop the backend web server |
| `server status` | Check server health |

## Search Options

```bash
# Search by type
search "周杰伦" --type song          # Search songs (default)
search "R&B精选" --type playlist     # Search playlists
search "专辑" --type album           # Search albums

# Search specific sources
search "林俊杰" -s netease -s qq    # Search multiple sources

# Limit results
search "Taylor Swift" -l 20         # Max 20 results per source
```

## Download Options

```bash
download --id 123456 -s netease                      # Basic download
download --id 123456 -s netease -n "Song" -a "Artist"  # With metadata
download --id 123456 -o ./my_music                   # Custom output dir
download --id 123456 --no-cover --no-lyrics          # Exclude extras
```

## JSON Output (AI Agent Mode)

All commands support `--json` for structured output:

```bash
# List sources as JSON
cli-anything-go-music-dl --json sources

# Search as JSON
cli-anything-go-music-dl --json search "周杰伦" -s netease

# Project info as JSON
cli-anything-go-music-dl --json project info --project my-project.json

# Session status as JSON
cli-anything-go-music-dl --json status
```

JSON output format for search:

```json
[
  {
    "id": "123456",
    "name": "夜曲",
    "artist": "周杰伦",
    "album": "十一月的萧邦",
    "source": "netease"
  }
]
```

## REPL Mode

Enter the interactive REPL by running without subcommands:

```bash
cli-anything-go-music-dl
```

REPL commands are stateful and support undo/redo. Type `help` for available commands and `exit` to quit.

## Project Files

Projects are saved as JSON files and support the following structure:

```json
{
  "name": "my-music",
  "active_source": "netease",
  "download_dir": "./downloads",
  "with_cover": true,
  "with_lyrics": true,
  "filename_template": "{name} - {artist}"
}
```

## Agent Guidance

When using this CLI via subprocess from an AI agent:

1. **Always use `--json`** for machine-readable output.
2. **Pass `--project <path>`** when checking status or history in a new subprocess to load previous state.
3. **Use `parse <url>`** to extract source and ID from a music share link before downloading.
4. **Start the server first** (`server start`) before searching or downloading; check with `server status`.
5. **Projects save automatically** after mutation commands (unless `--dry-run` is set).

### Typical Agent Workflow

```python
# 1. Parse a share URL
r = subprocess.run(["cli-anything-go-music-dl", "--json", "parse", url], capture_output=True, text=True)
parsed = json.loads(r.stdout)  # {"source": "netease", "id": "123456"}

# 2. Inspect the song
r = subprocess.run(["cli-anything-go-music-dl", "--json", "inspect", "--id", parsed["id"], "-s", parsed["source"]], capture_output=True, text=True)

# 3. Download
r = subprocess.run(["cli-anything-go-music-dl", "download", "--id", parsed["id"], "-s", parsed["source"], "-n", "Song Name"], capture_output=True, text=True)
```

## Supported Sources

| Key | Platform |
|-----|----------|
| `netease` | 网易云音乐 |
| `qq` | QQ音乐 |
| `kugou` | 酷狗音乐 |
| `kuwo` | 酷我音乐 |
| `migu` | 咪咕音乐 |
| `qianqian` | 千千音乐 |
| `soda` | 汽水音乐 |
| `fivesing` | 5sing音乐 |
| `jamendo` | Jamendo |
| `joox` | JOOX |
| `bilibili` | Bilibili |
| `apple` | Apple Music |
| `local` | Local files |

## Testing

```bash
# Unit tests
pytest cli_anything/go_music_dl/tests/test_core.py -v

# E2E tests
pytest cli_anything/go_music_dl/tests/test_full_e2e.py -v

# All tests
pytest cli_anything/go_music_dl/tests/ -v
```
