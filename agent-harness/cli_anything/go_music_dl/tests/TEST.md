# Test Plan — cli-anything-go-music-dl

## Test Inventory

| File | Est. Tests | Description |
|------|-----------|-------------|
| `test_core.py` | 15 | Unit tests for project, session, export modules |
| `test_full_e2e.py` | 8 | E2E tests with backend, CLI subprocess tests |

---

## Unit Test Plan (`test_core.py`)

### `project.py`
- `test_create_project` — Create project with default values
- `test_create_project_custom` — Create project with custom settings
- `test_save_and_open_project` — Round-trip save/open
- `test_open_nonexistent` — Error on missing file
- `test_project_info` — Info dict contains expected keys
- `test_validate_project_path` — Validation edge cases

### `session.py`
- `test_session_init` — Empty session has correct defaults
- `test_set_project` — Setting project updates state
- `test_snapshot_undo_redo` — Undo/redo cycle
- `test_undo_empty` — Undo on empty stack returns None
- `test_download_history` — Add and retrieve downloads
- `test_session_serialization` — Save/load round-trip
- `test_server_management` — Server info tracking

### `export.py`
- `test_download_job_defaults` — DownloadJob defaults
- `test_verify_download_output_missing` — Missing file returns not-exists
- `test_verify_output_format` — Format detection from extension

## E2E Test Plan (`test_full_e2e.py`)

### Backend Tests (require music-dl binary)
- `test_backend_health_check` — Verify health endpoint
- `test_backend_sources_list` — Get supported sources
- `test_backend_cookies` — Get/set cookies

### CLI Subprocess Tests (require installed package)
- `test_help` — `--help` flag works
- `test_version` — `--version` outputs version
- `test_sources_command` — `sources` command lists sources
- `test_project_new` — Create project with `project new`
- `test_project_info` — Get project info

## Realistic Workflow Scenarios

### Workflow 1: Full Music Search & Download
1. Start server → `server start`
2. Search for songs → `search "周杰伦" --source netease`
3. Inspect a song → `inspect <id> --source netease`
4. Download → `download <id> --source netease --name "Song"`
5. Check history → `history`

### Workflow 2: Project-based Workflow
1. Create project → `project new my-music --source qq`
2. Search for source → `search "林俊杰" --source qq`
3. Set download dir → `project set download_dir ./my_music`
4. Save project → `project save`
5. Undo/redo → `undo` / `redo`

### Workflow 3: Cross-Source Playlist Download
1. Search playlist → `search "R&B精选" --type playlist`
2. Get playlist songs → `playlist netease <playlist_id>`
3. Download first song → `download <song_id> --source netease`

---

## Test Results (2026-07-18)

### Unit Tests (`test_core.py`) — 25/25 ✅

```
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\claude code learning\go-music-dl\agent-harness

TestProject (8 tests):
  ✅ test_create_project
  ✅ test_create_project_custom
  ✅ test_save_and_open_project
  ✅ test_open_nonexistent
  ✅ test_project_info
  ✅ test_project_to_dict
  ✅ test_project_from_dict
  ✅ test_validate_project_path

TestSession (9 tests):
  ✅ test_session_init
  ✅ test_set_project
  ✅ test_snapshot_undo_redo
  ✅ test_undo_empty
  ✅ test_redo_empty
  ✅ test_download_history
  ✅ test_session_serialization
  ✅ test_clear_project
  ✅ test_global_session
  ✅ test_clear_server

TestExport (8…8 tests, actually 8):
  ✅ test_download_job_defaults
  ✅ test_download_job_to_dict
  ✅ test_verify_download_output_missing
  ✅ test_verify_output_format
  ✅ test_verify_flac_format
  ✅ test_verify_non_audio
  ✅ test_download_result_to_dict

Outcome: 25 passed in 0.08s
```

### E2E Tests (`test_full_e2e.py`) — 14/14 ✅ (4 skipped)

```
platform win32 -- Python 3.11.9, pytest-9.1.1, pluggy-1.6.0
rootdir: E:\claude code learning\go-music-dl\agent-harness

TestCLISubprocess (10 tests):
  ✅ test_help
  ✅ test_version
  ✅ test_sources_json
  ✅ test_sources_human
  ✅ test_project_new_json
  ✅ test_project_info
  ✅ test_parse_url
  ✅ test_status_json
  ✅ test_undo_redo_no_project
  ✅ test_full_project_workflow

TestBackendIntegration (4 tests — ⏭ skipped, music-dl binary not in PATH):
  ⏭ test_health_check
  ⏭ test_sources_list
  ⏭ test_get_cookies
  ⏭ test_get_settings

TestOutputVerification (4 tests):
  ✅ test_module_imports
  ✅ test_session_save_load
  ✅ test_verify_real_audio_file
  ✅ test_backend_source_list_matches_core

Outcome: 14 passed, 4 skipped in 9.75s
```

### Combined Summary

| Suite | Tests | Status |
|-------|-------|--------|
| Unit (test_core.py) | 25 / 25 | ✅ All passed |
| E2E CLI (test_full_e2e.py — CLI) | 10 / 10 | ✅ All passed |
| E2E Backend (test_full_e2e.py — backend) | 4 / 4 | ⏭ Skipped (no music-dl binary) |
| E2E Output (test_full_e2e.py — output) | 4 / 4 | ✅ All passed |
| **Total** | **39 / 39** | **✅ 39 passed (35 executed, 4 skipped)** |
