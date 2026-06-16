# Enterprise Document Search System — Full Codebase Analysis
## Generated: 2026-02-11

---

## 1. PROJECT OVERVIEW

A production-grade document processing pipeline that:
1. **Discovers** files from a source directory (filesystem walk)
2. **Extracts** text via Apache Tika (4 size-based worker pools)
3. **Indexes** documents into OpenSearch (bulk indexing with adaptive batching)
4. **OCRs** image/scanned PDFs via Tesseract (smart multi-strategy retry)
5. **Tags** documents using hybrid rule-based + optional SpaCy NLP engine
6. **Serves** a Streamlit dashboard + FastAPI search API

**Tech Stack:** Python 3.10+, Redis (queue/state), SQLite (fallback), OpenSearch 2.12, Tika 2.9.2, Tesseract OCR, Streamlit, FastAPI

### Architecture (Files → Pipeline)
```
Source Dir → [Discovery Workers] → Redis Queues (by size: tiny/small/medium/large)
  → [Extraction Workers + Tika] → [Indexing Workers + OpenSearch]
  → [OCR Workers + Tesseract] (for images/scans) → OpenSearch partial update
  → [Tagging Workers] → OpenSearch field update
  → [Dashboard / Search API] ← user queries
```

### File Inventory (src/)
| Module | Files | Lines | Purpose |
|--------|-------|-------|---------|
| core/ | 7 files | ~5,600 | Config, constants, logging, queue managers (SQLite+Redis), reporting |
| discovery/ | 3 files | ~535 | Filesystem scanning, hashing, bloom filter dedup |
| extraction/ | 3 files | ~1,160 | Tika client, content extraction, embedded file handling |
| indexing/ | 3 files | ~1,677 | OpenSearch client, document builder, bulk indexing |
| ocr/ | 4 files | ~2,491 | Tesseract wrapper, image preprocessing (basic+advanced), OCR worker |
| orchestrator/ | 5 files | ~1,191 | Master coordinator, checkpoint, health, recovery, resource monitor |
| ui/ | 2 files | ~2,502 | Streamlit dashboard + background state cache |
| api/ | 2 files | ~724 | FastAPI search API + query builder |
| nlp/ | 1 file | ~528 | SpaCy-based OCR text correction |
| tagging/ | 5 files | ~1,287 | Taxonomy-driven document tagging |
| utils/ | 1 file | ~460 | Production bloom filter |
| tools/ | 4 files | ~557 | Diagnostic/repair utilities |
| **Total** | **~40 files** | **~18,700** | |

---

## 2. CRITICAL BUGS (Must Fix)

### BUG-01: Hardcoded DELL machine path in extraction_worker.py
- **File:** `src/extraction/extraction_worker.py` ~line 700
- **Issue:** `'C:/Users/DELL/DocumentSearch'` used as fallback for `working_root`
- **Impact:** Crashes embedded file extraction on any non-DELL machine
- **Fix:** Use `config.paths.working_root` instead

### BUG-02: NLP text_corrector destroys numeric data
- **File:** `src/nlp/text_corrector.py` lines 177-178
- **Issue:** `'0' → 'O'` and `'1' → 'I'` character replacements applied unconditionally via `str.replace()`. Turns `$10,000` into `$IO,OOO`
- **Impact:** CRITICAL data corruption of all financial/numeric content
- **Fix:** These replacements must be context-aware (only in word boundaries, not inside numbers)

### BUG-03: OpenSearchClient missing close() method
- **File:** `src/indexing/opensearch_client.py`
- **Issue:** No `close()` method defined, but `indexing_worker.stop()` calls `self.os_client.close()` → `AttributeError` crash on shutdown
- **Fix:** Add `close()` method to OpenSearchClient

### BUG-04: OCR worker PSM hot-patching not restored
- **File:** `src/ocr/ocr_worker.py` ~line 517
- **Issue:** Smart OCR loop patches `self.tesseract.psm` to different values but never restores original. Affects all subsequent normal OCR runs.
- **Fix:** Save and restore original PSM value

### BUG-05: Config paths pointing to wrong machine
- **File:** `config/config.yaml`
- **Issue:** All paths reference `C:\Users\DELL\Downloads\DocumentSearch_v5\...` — wrong machine
- **Fix:** Update to current machine paths

### BUG-06: Content extractor normalization config always empty
- **File:** `src/extraction/content_extractor.py` line ~21
- **Issue:** `self.normalization_config = {}` — never populated from config. All `.get()` calls use hardcoded defaults.
- **Fix:** Load from `config.extraction.content_normalization`

### BUG-07: Redis reconcile_missing_files treats plain values as JSON
- **File:** `src/core/redis_queue_manager.py` ~line 2165
- **Issue:** `HASH_FILE_PATHS` stores `file_path → file_id` as plain strings, but `reconcile_missing_files` calls `json.loads()` → `JSONDecodeError`
- **Fix:** Don't JSON-parse plain string values

### BUG-08: complete_ocr hardcodes max 20 OCR workers
- **File:** `src/core/redis_queue_manager.py` ~line 854
- **Issue:** Fallback loop `for i in range(1, 20)` misses workers 20+
- **Fix:** Derive max from config `ocr.post_indexing_workers` or use a larger range

---

## 3. HIGH-SEVERITY ISSUES

### ISSUE-01: Dashboard dual data sources show different "completed" numbers
- **Sidebar** uses `SCARD SET_COMPLETED_FILE_IDS` (set membership)
- **Monitor** uses `GET COUNTER_ROOT_COMPLETED` (atomic counter)
- If recovery requeues items, counter is decremented but SET is not cleaned → numbers diverge
- **Fix:** Use a single authoritative source; reconcile the other

### ISSUE-02: In-pipeline count artificially capped
- **Dashboard** caps `in_pipeline = min(raw, discovered - completed - failed)`
- When extraction creates embedded files (more items than root discovered), the cap hides real queue depth
- **Fix:** Remove cap or account for embedded expansion

### ISSUE-03: Recovery always requeues to extraction regardless of pipeline stage
- **File:** `src/orchestrator/recovery_manager.py` line 299
- A file stuck at indexing stage gets re-extracted unnecessarily
- **Fix:** Check file's actual stage and requeue to the correct queue

### ISSUE-04: Rate limiter memory leak in search API
- **File:** `src/api/search_api.py` lines 65-76
- Cleanup only triggers at 10,000+ unique IPs
- **Fix:** Use a time-based expiry (e.g., TTL dict or LRU cache)

### ISSUE-05: Bloom filter pickle deserialization is unsafe (RCE vector)
- **File:** `src/utils/bloom_filter.py` lines 320-330
- `pickle.load()` executes arbitrary code
- **Fix:** Add HMAC validation or switch to safer serialization

### ISSUE-06: Year correction hardcoded to 2011
- **File:** `src/nlp/text_corrector.py` lines 272-280
- All OCR year patterns replaced with 2011 regardless of context
- **Fix:** Make configurable or use context-aware detection

---

## 4. MEDIUM-SEVERITY ISSUES

### Redis Key Naming Inconsistencies
- `HASH_FILES = "docsearch:files"` used as prefix for per-file hashes (`docsearch:files:{id}`) but `reconcile_missing_files` calls `HLEN` on it as if single hash → returns 0
- `TABLE_WORKER_HEARTBEATS` defined in queue_manager.py, not constants.py

### Race Conditions
- Redis `add_discovered_files_batch`: TOCTOU race on `sismember` outside pipeline
- `LoggerManager` and `ConfigurationManager` singletons have no thread locks
- Discovery completion detection is premature (folder queue empty ≠ done)
- `os.environ["PATH"]` manipulation in OCR worker not thread-safe

### Config Mismatches
- `OCR_MIN_CONFIDENCE = 25` in constants.py duplicated in OCRConfig dataclass
- Many timeout constants in constants.py are dead code (overridden by YAML config)
- `__version__` in `__init__.py` duplicates `VERSION` in constants.py

### Error Handling Gaps
- All Redis methods use broad `except Exception` with default returns — silently swallows errors
- `yaml.safe_load` can return None for empty files — no check
- `worker_heartbeats` table never created in SQLite queue manager
- `opensearch_client.py` missing `close()` causes AttributeError on shutdown
- Bare `except:` in recovery_manager.py catches SystemExit/KeyboardInterrupt

### Dead Code
- `image_preprocessor.py` (basic) — superseded by `image_preprocessor_advanced.py`
- `get_completed_items()` stub in both queue managers
- `sync_sqlite_to_redis()`, `try_switch_to_redis()` — dead with strict Redis mode
- `EnhancementLevel` enum defined but never used
- Many constants in constants.py overridden by YAML config

### Duplicated Logic
- Subtag/key_names/dates/location parsing duplicated between `extraction_worker.py` and `document_builder.py`
- Slash command parser duplicated between `dashboard.py` and `query_builder.py`
- `_is_real_data` duplicated between `dashboard.py` and `dashboard_state.py`

---

## 5. LOW-SEVERITY / STYLE ISSUES

- `datetime.utcnow()` deprecated since Python 3.12 — use `datetime.now(timezone.utc)`
- `hmset` deprecated in redis-py 4.x — use `hset(mapping=...)`
- `subprocess` import at module level in dashboard adds startup overhead
- Heartbeat interval hardcoded to 10s across all workers (should be configurable)
- `build_filter_query` accepts pagination params but never uses them
- Tagging engine `_MAX_RAW_SCORE = 1.6` but actual max is 1.8 → scores cluster near 0.99
- Shadow removal uses `np.ones((50,50))` kernel — extremely slow on large images
- `_correct_orientation` invokes Tesseract OSD per image (doubles Tesseract calls)
- Backfill tagging has no deduplication — re-running enqueues everything twice

---

## 6. DASHBOARD vs REDIS NUMBER MAPPING

| Dashboard Metric | Redis Key | Method | Potential Drift? |
|---|---|---|---|
| Files Discovered | `docsearch:counter:discovered` | `GET` | No |
| Fully Processed (sidebar) | `docsearch:completed_file_ids` | `SCARD` | YES — SET vs counter |
| Fully Processed (monitor) | `docsearch:counter:root_completed` | `GET` | YES — different source |
| In Pipeline | sum(pending+processing) across queues | Capped | YES — cap hides real depth |
| Failed | `docsearch:failed` | `HLEN` | No |
| Extraction Pending | `docsearch:queue:extraction:{size}` | `ZCARD` × 4 | No |
| Indexing Pending | `docsearch:queue:indexing` | `LLEN` | No |
| OCR Pending | `docsearch:queue:ocr` | `ZCARD` | No |
| OCR Completed | `docsearch:counter:ocr_completed` | `GET` | Counts events, not unique files |
| Data Discovered (bytes) | `docsearch:counter:discovered_bytes` | `GET` | No |
| Data Indexed (bytes) | `docsearch:counter:completed_bytes` | `GET` | No |
| Duplicates | `docsearch:counter:duplicates` | `GET` | No |

### Known Dashboard Discrepancy Scenarios:
1. **Sidebar "Searchable" ≠ Monitor "Completed"** — Different Redis sources (SET vs COUNTER)
2. **In-pipeline shows 0 when queues have items** — Cap logic suppresses real count
3. **OCR completed > actual files OCR'd** — Counter counts completion events, not unique files
4. **After recovery requeue** — Counter decremented but SET not cleaned

---

## 7. RECOMMENDED ARCHITECTURE IMPROVEMENTS

1. **Single Source of Truth for Completion**: Use only `SET_COMPLETED_FILE_IDS` (SCARD) or only `COUNTER_ROOT_COMPLETED` — not both
2. **Atomic Counter Groups**: Use Redis Lua scripts to update related counters atomically
3. **Stage-Aware Recovery**: Check file's pipeline stage before requeuing
4. **Context-Aware NLP**: The character replacement in text_corrector must be boundary-aware
5. **Config Validation**: Validate all paths, URLs, and numeric ranges at startup
6. **Proper Connection Pooling**: OpenSearch/Redis clients should handle reconnection gracefully
7. **Worker Metrics to Redis**: All worker-local counters should publish to Redis for dashboard aggregation
8. **Remove Dead Code**: image_preprocessor.py (basic), stubs, unused constants
9. **Consolidate Duplicated Logic**: Tag/metadata parsing, slash commands, data validity checks

---

## 8. FIXES APPLIED IN THIS SESSION

### Critical Fixes
| # | File | Issue | Fix |
|---|------|-------|-----|
| 1 | `config_manager.py` | Global config at `C:\DocumentSearch\config\config.yaml` overrode project-local config | Reordered search: project local → current dir → global fallback |
| 2 | `redis_queue_manager.py` | `hset(key, mapping={...})` sends multi-field HSET unsupported on Redis 3.2 | Changed to `hmset(key, dict)` for Redis 3.x compat (3 locations) |
| 3 | `config/config.yaml` | All paths pointed to DELL machine (`C:\Users\DELL\...`) | Updated all paths for hp212560601 machine |
| 4 | `extraction_worker.py` | Hardcoded `C:/Users/DELL/DocumentSearch` as fallback | Removed fallback, uses config `working_root` directly |
| 5 | `text_corrector.py` | NLP replaced `0→O` and `1→I`, corrupting numeric data | Removed dangerous character replacements |
| 6 | `opensearch_client.py` | Missing `close()` method caused shutdown crash | Added `close()` method |
| 7 | `ocr_worker.py` | Smart OCR loop permanently changed Tesseract PSM | Added save/restore of original PSM |
| 8 | `content_extractor.py` | Accessed `config.extraction.content_normalization` (doesn't exist) | Changed to read from `raw_config` dict |
| 9 | `redis_queue_manager.py` | Hardcoded `range(1, 20)` in `complete_ocr`/`complete_indexing` | Changed to config-based `max_ocr_workers + 1` / `max_idx_workers + 1` |

### Dashboard Bug Fixes
| # | File | Bug | Fix |
|---|------|-----|-----|
| 10 | `dashboard.py` | Progress % exceeded 100% when duplicates present (subtracted from denominator only) | Use `total_discovered` as denominator without subtracting duplicates |
| 11 | `redis_queue_manager.py` | `failed.size_bytes` always returned 0 | Now scans `HASH_FAILED` to sum actual failed file sizes |
| 12 | `redis_queue_manager.py` | `in_pipeline.size_bytes` didn't subtract failed file sizes | Now subtracts `failed_size` from calculation |
| 13 | `dashboard.py` | In Pipeline capping used wrong base (with duplicate subtraction) | Capping now uses `total_discovered` directly |
| 14 | `start-system.ps1` | Java path pointed to wrong JDK version | Updated to `jdk-17.0.11.9-hotspot` |

### Processing Cleanup Fixes
| # | File | Bug | Fix |
|---|------|-----|-----|
| 15 | `redis_queue_manager.py` | "Zombie" processing items left behind when workers crash after indexing but before marking complete | Added `cleanup_zombie_processing()` method to detect and clean items with `indexed_at` timestamp but not in completed set |
| 16 | `master_orchestrator.py` | Zombie cleanup never called | Added periodic call to `cleanup_zombie_processing()` every 2 minutes in main loop |

### System Validation Results (75 test documents)
- **Discovered**: 76 (75 unique + 1 race-condition duplicate)
- **Extracted**: 76 (includes duplicate)
- **Indexed**: 75 (OpenSearch docs)
- **Tagged**: 75
- **Failed**: 0
- **Processing items**: 0 (after zombie cleanup)
- **Pipeline complete**: ✓ All 75 documents processed end-to-end
- **Dashboard vs Redis**: All major counters match (±1 for race-condition duplicate)

### Root Cause of "1 Processing" Issue
- **File_id 1** (`budget_engineering_042.txt`) was successfully indexed to OpenSearch
- Indexing worker crashed/died **after** `bulk()` to OpenSearch but **before** calling `complete_indexing()`
- Processing key remained: `docsearch:processing:indexing:indexing-3`
- File status stuck at `extracted` (never reached `completed`)
- Created new `cleanup_zombie_processing()` method to detect and clean such items automatically

### Known Remaining Issues (Low Priority)
1. `discovery.completed` is derived (discovered - pending), not a real counter
2. `indexing.completed` aliased to `root_completed` — no indexing-specific counter
3. Tagging progress not shown in sidebar pipeline progress bars (only in monitoring tab)
4. Two discovery workers can double-scan root directory on startup (race condition in re-seed logic)
5. `searchable.files` fallback chain can inflate count if `root_completed` is 0 but `completed` != 0
