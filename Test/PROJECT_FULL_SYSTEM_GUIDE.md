# DocumentSearch Project Deep Dive

## 1. What this project is

This repository is a full document ingestion and search platform:
- Discovers files from a configured source path.
- Extracts text using Apache Tika (including embedded content where available).
- Indexes extracted data into OpenSearch for fast search.
- Runs OCR with Tesseract for scanned/image-heavy files.
- Applies local taxonomy-based tagging logic.
- Exposes monitoring through a Streamlit dashboard.

The runtime is worker-based and orchestrated by a master process.

## 2. Core runtime flow (line-by-line behavior summary)

### Entry point and command surface
- `src/main.py`
- CLI commands include: `check`, `init`, `start`, `stop`, `status`, `stats`, `reset`, `validate`, `health_check`.
- `start` launches `MasterOrchestrator` from `src/orchestrator/master_orchestrator.py`.

### Configuration loading and typing
- `src/core/config_manager.py`
- Loads `config/config.yaml`.
- Merges environment overrides (OpenSearch creds, SMTP creds, API token).
- Validates required sections and creates dataclass objects used by all components.
- Creates required directories on `init`.

### Queue backend behavior
- `src/core/queue_manager.py`
- Current code is in strict Redis mode (no silent SQLite fallback).
- Redis must be reachable for queue manager initialization.
- Queue/state counters drive dashboard and worker claims.

### Orchestrator behavior
- `src/orchestrator/master_orchestrator.py`
- Spawns pools for discovery, extraction, indexing, OCR, and tagging.
- Performs worker health checks and respawns crashed workers with crash-loop protection.
- Runs stale-processing cleanup and checkpointing loops.
- Supports full/resume behaviors and recovery manager startup scan.

### Extraction and OCR workers
- `src/extraction/*`
- Extraction workers route by size category and push normalized payloads to indexing.
- `src/ocr/ocr_worker.py` handles OCR and optional PDF conversion via Poppler.
- OCR updates OpenSearch docs asynchronously.

### Search/index side
- `src/indexing/*`
- OpenSearch client and mapping lifecycle are handled in indexing components.
- Index creation and bulk ingest are done by indexing workers.

### Dashboard
- `src/ui/dashboard.py`
- Reads queue counters and OpenSearch stats.
- Uses caching/state wrappers for smoother refresh behavior.

## 3. Repository structure reality

This repo contains:
- Production code under `src/`.
- Many debug/audit/validation scripts at repository root.
- A large volume of historical markdown reports from prior audits/fixes.

Operationally, the runtime-critical files are:
- `config/config.yaml`
- `src/main.py`
- `src/orchestrator/master_orchestrator.py`
- `src/core/*`
- `src/discovery/*`, `src/extraction/*`, `src/indexing/*`, `src/ocr/*`, `src/tagging/*`, `src/ui/*`

## 4. Changes applied to make it run on this macOS system

### Environment and services installed
Installed via Homebrew:
- openjdk@21
- redis
- opensearch
- tesseract
- poppler
- python@3.11

Python environment:
- Recreated `.venv` on Python 3.11 for compatibility with pinned dependencies.
- Installed `requirements.txt`.
- Added missing `redis` Python package.

### Configuration adaptation
`config/config.yaml` was updated from Windows paths to local macOS workspace paths:
- `paths.*` switched to this repository's absolute runtime paths.
- `tagging.taxonomy_path` switched to local runtime taxonomy file.
- `testing.test_data_path` switched to local test documents.
- OCR binary paths updated:
  - `ocr.poppler_path` -> `/opt/homebrew/bin`
  - `ocr.tesseract.command` -> `/opt/homebrew/bin/tesseract`
  - `ocr.tesseract.datapath` -> `/opt/homebrew/share/tessdata`
- Worker counts reduced for local stability.

### Health-check compatibility fix
`src/main.py` was updated so Tika health checks accept modern Tika behavior:
- First tries `GET /tika` (accepts `200` or `405`).
- Falls back to `GET /` expecting `200`.

This prevents false-negative Tika failures on newer server behavior.

## 5. Startup assets created

### macOS launcher
- `start_everything.sh`
- Starts Redis + OpenSearch (Homebrew services).
- Starts Tika instances on ports `9998, 9999, 10000, 10001`.
- Runs `check`, `init`, starts orchestrator, and starts dashboard.

### Windows launcher (requested)
- `start_everything.bat`
- Attempts to start Redis/OpenSearch if available in PATH.
- Starts Tika instances.
- Runs `check`, `init`, then launches orchestrator + dashboard.

## 6. Current runtime status from this setup session

Validated successfully:
- Redis reachable.
- OpenSearch reachable at `http://localhost:9200`.
- Tika instances healthy on configured 4 ports.
- Tesseract detected.
- `python src/main.py init` completed successfully.
- `python src/main.py start` is running.
- Streamlit dashboard is running on port 8501.

## 7. Command reference (macOS)

```bash
# Service health
.venv/bin/python src/main.py check

# Initialize
.venv/bin/python src/main.py init

# Start orchestrator (foreground)
.venv/bin/python src/main.py start

# Dashboard
.venv/bin/python -m streamlit run src/ui/dashboard.py --server.port 8501

# One-command startup
bash start_everything.sh
```

## 8. Important operational notes

- Redis is required by current queue-manager behavior.
- If OpenSearch starts cold, allow a short warm-up before `init/check`.
- If you need NLP model-backed tagging quality, install spaCy + model (`en_core_web_md`) separately.
- The repository includes many one-off diagnostics scripts; they are useful, but not all are part of core runtime.

## 9. Minimal troubleshooting map

- `check` fails Tika:
  - Confirm Java path and running Tika processes.
  - Inspect `runtime/logs/tika-*.log`.

- `check` fails OpenSearch:
  - Confirm `brew services list` includes `opensearch` as started.
  - Check `http://localhost:9200`.

- Queue/backend errors:
  - Confirm Redis is running (`redis-cli ping` should return `PONG`).

- Dashboard issues:
  - Restart dashboard process.
  - Check `runtime/logs` for worker and UI errors.
