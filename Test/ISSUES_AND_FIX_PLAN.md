# DocumentSearch - Issues Report & Fix Plan

## Executive Summary

Full codebase audit identified **8 bugs** across 5 source files. The most critical bug caused **100% extraction failure rate** — every document that entered the extraction pipeline crashed with a `NameError`. All 8 bugs have been fixed.

---

## Issues Found

### Bug #1 — CRITICAL: `file_size` NameError in Tika Client
- **File:** `src/extraction/tika_client.py` (lines 97, 109)
- **Symptom:** Every extraction attempt crashes with `NameError: name 'file_size' is not defined`
- **Root Cause:** The `extract()` method references `file_size` for logging and selecting Tika port, but the variable was never defined.
- **Impact:** 100% extraction failure. Nothing gets indexed. Nothing gets OCR'd. The entire pipeline is dead.
- **Fix:** Added `import os` and `file_size = os.path.getsize(file_path)` before the retry loop.
- **Status:** ✅ FIXED

### Bug #2 — CRITICAL: Wrong ErrorType Enum in Extraction Worker
- **File:** `src/extraction/extraction_worker.py` (line 243)
- **Symptom:** Error handling itself crashes with `AttributeError: type object 'ErrorType' has no attribute 'EXTRACTION_ERROR'`
- **Root Cause:** Code uses `ErrorType.EXTRACTION_ERROR` but the enum in `constants.py` defines `EXTRACTION_FAILED`.
- **Impact:** When extraction fails (which is every time due to Bug #1), the error handler also crashes, making failures unrecoverable.
- **Fix:** Changed `ErrorType.EXTRACTION_ERROR` → `ErrorType.EXTRACTION_FAILED`.
- **Status:** ✅ FIXED

### Bug #3 — CRITICAL: QueueManager Heartbeat Methods in Wrong Scope
- **File:** `src/core/queue_manager.py` (lines ~1632-1665)
- **Symptom:** `AttributeError` when calling `queue_manager.update_worker_heartbeat()` etc.
- **Root Cause:** Three heartbeat methods (`update_worker_heartbeat`, `get_worker_heartbeats`, `remove_worker_heartbeat`) were defined inside the module-level `sync_sqlite_to_redis()` function instead of inside the `QueueManager` class.
- **Impact:** Worker heartbeat tracking completely broken for SQLite queue backend.
- **Fix:** Removed methods from `sync_sqlite_to_redis()`, added them as proper methods of the `QueueManager` class.
- **Status:** ✅ FIXED

### Bug #4 — CRITICAL: RedisQueueManager Heartbeat Methods in Wrong Scope
- **File:** `src/core/redis_queue_manager.py` (lines ~1830-1873)
- **Symptom:** `AttributeError` when calling `redis_queue_manager.update_worker_heartbeat()` etc.
- **Root Cause:** Three heartbeat methods were defined inside the module-level `reset_redis_queue_manager()` function instead of inside the `RedisQueueManager` class.
- **Impact:** Worker heartbeat tracking completely broken for Redis queue backend.
- **Fix:** Removed methods from `reset_redis_queue_manager()`, added them as proper methods of the `RedisQueueManager` class.
- **Status:** ✅ FIXED

### Bug #5 — MEDIUM: Dead Code in File Scanner
- **File:** `src/discovery/file_scanner.py` (lines 93-96)
- **Symptom:** No runtime error, but duplicate unreachable return statement.
- **Root Cause:** Two consecutive return statements — the second one is dead code that could cause confusion during maintenance.
- **Fix:** Removed the duplicate return statement.
- **Status:** ✅ FIXED

### Bug #6 — MEDIUM: Duplicate Redis SADD for Content Hash
- **File:** `src/core/redis_queue_manager.py` (lines ~1005-1006)
- **Symptom:** Extra Redis command outside pipeline on every queue insert, wasting network round-trips.
- **Root Cause:** After a pipeline that already does `sadd` for content_hash, there's a duplicate standalone `sadd` call.
- **Fix:** Removed the duplicate standalone `sadd` call.
- **Status:** ✅ FIXED

### Bug #7 — MEDIUM: Wrong OCR Image Preprocessor Import
- **File:** `src/ocr/__init__.py` (line 3)
- **Symptom:** Advanced preprocessing (deskew, noise removal, contrast enhancement) never used.
- **Root Cause:** Package init imports from `image_preprocessor` (basic) instead of `image_preprocessor_advanced`.
- **Impact:** OCR accuracy degraded — missing advanced preprocessing pipeline.
- **Fix:** Changed import to use `image_preprocessor_advanced`.
- **Status:** ✅ FIXED

### Bug #8 — LOW: String/Int Cursor Type Mismatch in Redis SCAN
- **File:** `src/core/redis_queue_manager.py` (~line 1672)
- **Symptom:** `reconcile_missing_files()` could infinite-loop or error on cursor comparison.
- **Root Cause:** Redis SCAN returns integer cursor, but code initializes with `cursor = '0'` (string) and checks `if cursor == 0` (int comparison to string never matches).
- **Fix:** Changed initial cursor to `0` (int) and added `break` when cursor returns to 0.
- **Status:** ✅ FIXED

---

## Cascade Analysis

```
Bug #1 (file_size NameError)
  └─→ Every extraction crashes
       └─→ Bug #2 (wrong ErrorType) 
            └─→ Error handler also crashes
                 └─→ No recovery possible
                      └─→ 0 documents indexed
                           └─→ 0 documents OCR'd
                                └─→ Dashboard shows 0 completed
                                     └─→ "Nothing is working"
```

The root cause of the entire system failure was **a single missing variable definition** in `tika_client.py`.

---

## Files Modified

| File | Changes |
|------|---------|
| `src/extraction/tika_client.py` | Added `import os`, added `file_size = os.path.getsize(file_path)` |
| `src/extraction/extraction_worker.py` | `ErrorType.EXTRACTION_ERROR` → `ErrorType.EXTRACTION_FAILED` |
| `src/discovery/file_scanner.py` | Removed dead duplicate return statement |
| `src/core/queue_manager.py` | Moved 3 heartbeat methods into QueueManager class |
| `src/core/redis_queue_manager.py` | Moved 3 heartbeat methods into RedisQueueManager class, removed duplicate sadd, fixed cursor type |
| `src/ocr/__init__.py` | Changed import to advanced image preprocessor |

---

## Verification Plan

1. **Start system:** `python src/main.py start`
2. **Check extraction logs:** Should see successful extractions (Done > 0, Fail < 100%)
3. **Check OpenSearch:** Documents should appear in `enterprise_documents` index
4. **Check OCR:** Image/scanned PDF files should get OCR treatment
5. **Check dashboard:** Metrics should reflect actual processing state
6. **Check heartbeats:** Worker heartbeat tracking should function without errors
