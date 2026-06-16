# Codebase Audit Report - February 2026

## Executive Summary
This report summarizes the current state of the Document Search System codebase following recent fixes. While critical "stuck at zero" metrics and Redis/SQLite mismatches have been addressed, several architectural flaws, code smells, and unimplemented features remain.

## Priority Matrix
| Severity | Count | Impact |
| :--- | :--- | :--- |
| **Critical** | 0 | None (Critical bugs are currently resolved) |
| **Major** | 2 | Hardware/Path hardcoding, Partial Checkpoint logic |
| **Minor** | 5 | Bare exceptions, Magic numbers, UI brittle logic |
| **Nit/Smell**| 3 | Lack of docstrings, type hint inconsistencies |

---



### 1.2 Potential Memory Spikes on Large Files (`src/extraction/tika_client.py`)
- **Location:** `src/extraction/tika_client.py:83`
- **Issue:** `file_data = f.read()` reads the entire file into RAM.
- **Impact:** Large files (e.g., 500MB+ ISOs or PDFs) will cause workers to crash with OOM (Out Of Memory) errors, especially with 60 parallel workers.
- **Proposed Fix:** Use streaming file upload: `self.session.put(url, data=f, ...)`

### 1.3 Unimplemented Checkpoint Restore (`src/orchestrator.py`)
- **Location:** `src/orchestrator.py:722`
- **Issue:** `_restore_from_checkpoint` is a TODO.
- **Impact:** System doesn't automatically recover "processing" items on restart.
- **Proposed Fix:** Implement logic to call `queue_manager.reset_stale_processing()` on startup.

### 1.4 Heavy Hashing in Discovery (`src/discovery/discovery_worker.py`)
- **Location:** `src/discovery/discovery_worker.py:143`
- **Issue:** Every file in a scanned folder is hashed regardless of metadata changes.
- **Impact:** Significant CPU/IO overhead during re-discovery of large stable datasets.
- **Proposed Fix:** Only hash if `path + size + mtime` doesn't match a known entry in the database.

---

## 2. Minor Issues & Code Quality

### 2.1 Bare Exception Handlers
- **Location:** `src/core/redis_queue_manager.py`, `src/orchestrator.py`
- **Issue:** Multiple instances of `except Exception: pass` or `except Exception as e: logger.error(e)`.
- **Impact:** Makes debugging difficult; hides potential connection errors or logic bugs.
- **Specific Examples:**
    - `redis_queue_manager.py:1482, 1497, 1512, 1608`
    - `orchestrator.py:221`



### 2.3 Redundant Client Initialization (`src/extraction/extraction_worker.py`)
- **Location:** `src/extraction/extraction_worker.py:79, 230`
- **Issue:** `OpenSearchClient` is initialized in every `ExtractionWorker` but the code explicitly chooses to always use the batch queue instead of the direct client.
- **Impact:** Unnecessary memory and connection overhead (60 extra OpenSearch connections).

### 2.4 Magic Numbers in Resource Monitoring
- **Location:** `src/orchestrator.py:596, 599, 602`
- **Issue:** Thresholds like 95% CPU, 90% Memory are hardcoded.
- **Proposed Fix:** Move these to `config.yaml`.

---

## 3. Findings from Workers

### 3.1 Extraction Redundancy
- **Issue:** `ExtractionWorker` initializes an `OpenSearchClient` but never uses it, opting for queue-based indexing instead.
- **Fix:** Remove unused client to save 60+ idle network connections.

### 3.2 OCR Robustness
- **Finding:** OCR pipeline is now robust with smart retries and image preprocessing.
- **Risk:** High memory usage if multiple large PDFs are converted to images simultaneously.

### 3.3 Redis Key Proliferation
- **Finding:** Database reset command (`src/main.py`) only deletes `docsearch:*` keys.
- **Risk:** If any code uses a different prefix or if Redis is shared, state might leak or be left behind.
