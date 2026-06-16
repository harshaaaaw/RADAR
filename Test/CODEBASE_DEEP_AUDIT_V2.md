# Codebase Deep Audit V2 — Line-by-Line Findings

**Generated:** 2026-02-10  
**Scope:** Every `.py` file under `src/` read line-by-line. This document lists **new** bugs, logic errors, race conditions, data-loss risks, and architectural issues **not already covered** in the existing `CODEBASE_ISSUES_AUDIT.md`.

---

## Legend

| Severity | Meaning |
|----------|---------|
| 🔴 **CRITICAL** | Will cause data loss, crashes, or silent corruption at runtime |
| 🟠 **HIGH** | Incorrect behavior under normal conditions; wrong results or degraded reliability |
| 🟡 **MEDIUM** | Problematic under edge cases, concurrency, or scale; latent failure risk |
| 🔵 **LOW** | Code quality, maintainability, or minor correctness issues |

---

## 🔴 CRITICAL Issues

### 1. `main.py` L547-548 — Redis reset scan loop never terminates

```python
cursor = '0'
while cursor != 0:
    cursor, keys = r.scan(cursor=cursor, match='docsearch:*', count=100)
```

**Bug:** `cursor` is initialized as the **string** `'0'`, but `r.scan()` returns an **integer** `0` when iteration is complete. The `while cursor != 0` comparison (`'0' != 0`) is **always True** in Python, causing an **infinite loop** during `reset --force`.

**Fix:** Initialize `cursor = 0` (integer).

---

### 2. `redis_queue_manager.py` L862 — `reset_stale_processing` ignores `timeout_minutes` parameter

```python
def reset_stale_processing(self, timeout_minutes: int = None) -> Dict[str, int]:
```

The parameter `timeout_minutes` is accepted but **never used** in the method body. All items in processing maps are unconditionally moved back to queues regardless of how long they've been processing. This means:
- Items being **actively processed** by a healthy worker are yanked away mid-flight
- On every 2-minute cycle in the orchestrator main loop (L347-354), healthy in-flight items are re-queued, causing **duplicate processing and indexing**

**Fix:** Check each processing item's timestamp against `timeout_minutes` before re-queuing.

---

### 3. `redis_queue_manager.py` L874-895 — `reset_stale_processing` uses `scan_iter` despite documented avoidance

The method uses `scan_iter(f"{self.PROCESSING_EXTRACTION}:*")` which was explicitly documented as problematic (L1067-1074: "SCAN over 600K+ keys was taking 15-30s per call"). The cached `_get_worker_keys()` method exists specifically to avoid this, but `reset_stale_processing` doesn't use it.

**Impact:** Each call blocks for 15-30s on large keyspaces, and this runs every 2 minutes from the orchestrator.

**Fix:** Use `self._get_worker_keys(self.PROCESSING_EXTRACTION)` instead of `scan_iter`.

---

### 4. `redis_queue_manager.py` L888 — Re-queued extraction items use raw JSON as sorted-set member

```python
self.client.zadd(queue_key, {item_json: 0})
```

The `item_json` here is the **bytes** value returned by `hgetall()` (via `items.values()`), not a decoded string. When the item is later claimed via `zpopmin`, the worker receives bytes, but `json.loads()` in the claim path expects a string. If `decode_responses` is not set on the Redis client, this causes **silent deserialization failures** or type mismatches.

**Fix:** Ensure `item_json` is decoded to string before `zadd`, or confirm `decode_responses=True` on client initialization.

---

### 5. `extraction_worker.py` L413-537 — Embedded file extraction creates unbounded temp directories

The `_extract_embedded_files` method creates temp directories (`tempfile.mkdtemp()`) for each ZIP-like container it unpacks but only cleans them up within its own `finally` block. If the method raises an unexpected exception type before the `finally`, or if the worker process is killed (SIGKILL from orchestrator L516), **orphaned temp directories accumulate indefinitely** on disk.

**Impact:** Over long runs processing many Office/ZIP files, disk space is consumed without bound.

**Fix:** Use `tempfile.TemporaryDirectory()` context manager for automatic cleanup, and add a startup sweep for stale temp dirs.

---

## 🟠 HIGH Issues

### 6. `redis_queue_manager.py` L903 — Indexing requeue pushes raw bytes to list

```python
self.client.lpush(self.QUEUE_INDEXING, *items)
```

`items` comes from `hvals(key)` which returns bytes when `decode_responses` is not set. The indexing claim path (`claim_indexing_work`) does `json.loads(item_json)` on the `lpop` result. If the byte/string encoding is inconsistent, items become **permanently stuck** — they're in the queue but fail to deserialize on claim.

---

### 7. `redis_queue_manager.py` L1779 — `reconcile_missing_files` uses `HASH_FILES` which is never populated

```python
cursor, data = self.client.hscan(self.HASH_FILES, cursor=cursor, count=1000)
```

The `HASH_FILES` key (`docsearch:files`) is defined at L64 but I found **no method that writes to it** using `hset(self.HASH_FILES, ...)` with file metadata. The `add_discovered_file` method writes to `HASH_FILE_PATHS` (path->ID mapping) and individual `HASH_FILES:{file_id}` keys, but **not** the root `HASH_FILES` hash. Therefore `reconcile_missing_files` always scans an **empty hash** and finds nothing.

**Impact:** The "self-healing" reconciliation feature is completely non-functional.

**Fix:** Either populate `HASH_FILES` during discovery, or change reconciliation to iterate `HASH_FILE_PATHS` or individual file keys.

---

### 8. `queue_manager.py` L79 — Duplicate table in reset list

```python
tables = [
    TABLE_DISCOVERED_FILES,
    TABLE_EXTRACTION_QUEUE,
    ...
    TABLE_FILE_HASHES,
    TABLE_FILE_HASHES,  # <-- duplicate
    TABLE_CONTENT_HASHES,
    ...
]
```

`TABLE_FILE_HASHES` appears twice. While `DROP TABLE IF EXISTS` won't crash, this indicates a missing table entry — likely another table that should be reset but isn't.

---

### 9. `master_orchestrator.py` L349 — `reset_stale_processing` return type assumption

```python
reset_counts = self.queue_manager.reset_stale_processing(timeout_minutes=5)
if any(reset_counts.values()):
```

If the queue manager is the SQLite `QueueManager`, `reset_stale_processing` has a different signature (`table_name, timeout`). The orchestrator's main loop (L348-353) wraps this in `try/except`, so it won't **crash**, but the error is silently swallowed — meaning stale processing items are **never recovered** when running in SQLite fallback mode. The log shows `"Stale cleanup failed"` but no remedial action is taken.

---

### 10. `discovery_worker.py` L90-198 — Discovery worker uses folder-based scanning but `push_folder` only stores path string

The discovery worker pushes subfolders via `queue_manager.push_folder()` which uses `rpush` (Redis list). Multiple discovery workers calling `pop_folder()` can pop the **same folder** if there's a race between `rpush` and `lpop`. While `lpop` is atomic, the bloom filter check per-file prevents duplicate processing at the file level, but **entire folder scans are duplicated**, wasting significant I/O and CPU on large directory trees.

**Fix:** Use a set-based approach for folder dedup, or accept the overhead as a design tradeoff.

---

### 11. `indexing_worker.py` L162-339 — No deduplication check before indexing

The indexing worker bulk-indexes everything it claims. If `reset_stale_processing` re-queues an item that was already indexed (because the completion ack was lost), the same document is indexed **twice** into OpenSearch. OpenSearch uses `doc_id` for upsert, so content isn't duplicated in the index, but:
- Completed counters are incremented twice
- `mark_file_completed` runs twice, potentially double-counting bytes/times

---

### 12. `ocr_worker.py` L818-825 — Heartbeat thread never cleaned up on stop

```python
def _heartbeat_loop(self) -> None:
    while self.running:
        try:
            self.queue_manager.update_worker_heartbeat(self.worker_id)
        except Exception:
            pass
        time.sleep(10)
```

The heartbeat thread is started as a daemon thread but `stop()` (L812-816) only sets `self.running = False`. Since the thread sleeps for 10 seconds, there's up to a 10-second window where the worker appears stopped but the heartbeat thread is still alive. More importantly, `remove_worker_heartbeat()` is **never called** on shutdown, leaving stale heartbeat entries permanently in Redis.

---

### 13. `config_manager.py` L490-540 — `_load_environment_variables` lacks type conversion

Environment variables are loaded as **strings** and assigned directly to config attributes that expect specific types (integers for ports, booleans for flags, floats for thresholds). For example:

```python
if os.getenv('API_PORT'):
    self.config.api.port = os.getenv('API_PORT')  # string, not int
```

FastAPI/Uvicorn will receive a string port where it expects an integer, causing either a crash or unexpected behavior.

---

## 🟡 MEDIUM Issues

### 14. `redis_queue_manager.py` L1191 — Extraction completed fallback is wrong

```python
extraction_completed = extraction_completed_counter if extraction_completed_counter > 0 else total_completed
```

If `COUNTER_EXTRACTION_COMPLETED` is 0 (e.g., first run, or counter not yet initialized), it falls back to `total_completed` (the overall completed count including indexing). This makes extraction look 100% complete when it hasn't started, and dashboard progress bars show misleading data.

---

### 15. `redis_queue_manager.py` L1208 — Extraction stats `total` excludes processing items

```python
stats['extraction'][cat] = {
    'pending': pending,
    'processing': processing,
    'completed': cat_completed,
    'total': pending + cat_completed  # <-- missing + processing
}
```

The `total` field doesn't include items currently being processed, making the sum incorrect and causing dashboard percentages > 100% when processing items exist.

---

### 16. `redis_queue_manager.py` L1282-1283 — Indexing total fallback masks real status

```python
if idx_total == 0:
    idx_total = ext_completed  # If indexing is empty, use extraction completed as estimate
```

When no indexing has happened yet, this makes `idx_total` equal to extraction completed count. Combined with `idx_completed = total_completed`, `idx_pending` and `idx_processing` are 0, making it look like all extraction output was indexed when none was.

---

### 17. `file_scanner.py` L67 — Floating-point mtime comparison is fragile

```python
if cached_mtime is not None and abs(current_mtime - cached_mtime) < 0.001:
    skip_files = True
```

`st_mtime` precision varies by filesystem (FAT32 has 2-second resolution, NTFS has 100ns). Using `0.001` threshold may cause:
- False matches on FAT32 (different files within 2s window)
- False misses on high-precision filesystems where float rounding creates > 0.001 drift

---

### 18. `bloom_filter.py` L296-307 — `load_from_file` creates a double-initialized bloom filter

```python
bloom = cls(
    expected_elements=state['expected_elements'],
    false_positive_rate=state['false_positive_rate']
)
# Then immediately overwrites:
bloom.size = state['size']
bloom.hash_count = state['hash_count']
bloom.bit_array = state['bit_array']
```

The constructor allocates a full-size `bitarray(self.size)` which is **immediately discarded** and replaced. For a 5M-element bloom filter, this wastes ~5.7MB of memory allocation (briefly doubling memory usage during load).

---

### 19. `search_api.py` L53-56 — API token defaults to `None` if env var unset

```python
api_token = os.getenv('API_TOKEN')
# Later used in:
if not api_token:
    return  # No auth required
```

If `API_TOKEN` env var is not set, **all API endpoints become unauthenticated**. Combined with the CORS `allow_origins=["*"]` at L30, this creates an open API accessible from any origin.

---

### 20. `opensearch_client.py` L139 — OCR char_filter maps digits to letters destructively

```python
'mappings': [
    '0 => o',  # zero to letter o
    '1 => l',  # one to letter l
    '5 => s',  # five to letter s
    '8 => b',  # eight to letter b
]
```

This char_filter is applied **at index time** to ALL `ocr_content` text. Any document containing legitimate numbers (invoices, financial reports, phone numbers) will have those numbers **permanently corrupted** in the index. Searching for "2024" or "$500" will fail because the stored text would be "2o24" and "$soo".

**Impact:** Search accuracy for any numeric content in OCR'd documents is severely degraded.

**Fix:** Remove this char_filter entirely, or apply it only as a **search-time** analyzer on a secondary field.

---

### 21. `master_orchestrator.py` L374-382 — Dead worker cleanup doesn't clean up processing keys

When a worker dies and is detected by `_check_workers()`, the worker is removed from the tracking dict and respawned, but its **Redis processing keys** (`docsearch:processing:extraction:{worker_id}`) still contain items. These items are only recovered by `reset_stale_processing`, which runs every 2 minutes and (per Issue #2) re-queues items unconditionally.

---

### 22. `extraction_worker.py` — No content size limit before indexing queue insertion

Extracted text content is passed directly into the indexing queue. For very large documents (e.g., multi-hundred-page PDFs), the extracted text can be **tens of megabytes**. This is stored as a JSON string in Redis (`lpush`), which:
- Bloats Redis memory
- Can exceed OpenSearch's `http.max_content_length` (default 100MB) when bulk-indexed
- Creates giant processing items that slow down all queue operations

---

## 🔵 LOW Issues

### 23. `redis_queue_manager.py` L1253 — Duplicate `safe_int` definition

`safe_int()` is defined at both L1180 (inside `get_queue_stats`) and L1253 (inside `get_queue_statistics`). These are identical helper functions that should be extracted to a module-level utility.

---

### 24. `master_orchestrator.py` L6 — Unused import `sys`

`sys` is imported at module level (from the static analysis in `CODEBASE_ISSUES_AUDIT.md`) but only re-imported inside `@staticmethod` worker runners. The module-level import is dead code.

---

### 25. `main.py` L489-491 — Redundant `gc.collect()` and `import time` inside loop

```python
import gc
gc.collect()
import time
time.sleep(0.5 * attempt)
```

Both `gc` and `time` are re-imported on every retry iteration inside a loop. They should be imported once at the top.

---

### 26. `redis_queue_manager.py` L1517-1519 — `get_completed_items` returns empty list stub

```python
def get_completed_items(self, count: int = 100) -> List[Dict]:
    """Get recently completed items"""
    return []
```

This is a stub that always returns empty. If any code calls this expecting data (e.g., dashboard), it silently produces empty results.

---

### 27. `bloom_filter.py` L125-126 — Negative hash positions are possible

```python
hash1 = mmh3.hash(item, seed=0) % self.size
hash2 = mmh3.hash(item, seed=1) % self.size
```

`mmh3.hash()` returns a **signed** 32-bit integer. In Python, `negative % positive` is always positive, so this is technically safe. However, using `mmh3.hash128()` or ensuring unsigned output with `& 0xFFFFFFFF` would be more explicit and portable.

---

### 28. `config_manager.py` L394-425 — `_find_config_file` searches 5+ locations silently

The config file search checks `config.yaml` in the CWD, then parent directories, then environment variable, with no clear precedence documentation. If multiple config files exist in different locations, the first match wins silently, which can cause confusing behavior in development vs production deployments.

---

### 29. `file_scanner.py` L101-103 — Dead code: `_walk_directory` method

```python
def _walk_directory(self, root: Path) -> Iterator[os.DirEntry]:
    """Deprecated: Recursive walk"""
    pass
```

This method is marked deprecated and contains only `pass`. It should be removed.

---

## Architectural Concerns

### A. No graceful drain on shutdown

When `orchestrator.stop()` is called, worker processes receive `SIGTERM` and then `SIGKILL` after the grace period. Items currently being processed are abandoned in processing state. While `reset_stale_processing` can recover them on next startup, any **partial work** (e.g., a file half-extracted, temp files created) is not cleaned up.

### B. Counter drift is systemic

The system maintains multiple redundant counters (`COUNTER_COMPLETED`, `COUNTER_ROOT_COMPLETED`, `COUNTER_DISCOVERED`, `HASH_COMPLETED` HLEN, `SET_COMPLETED_FILE_IDS` SCARD) that can drift apart. The `validate_metrics` method (L1694-1726) only checks root completed count vs set size. There's no periodic reconciliation of all counter sources.

### C. No backpressure between pipeline stages

If extraction produces items faster than indexing can consume them, the indexing queue (Redis list) grows without bound. There's no mechanism to throttle extraction workers when the indexing queue is deep, nor to alert when queue depth exceeds a threshold.

### D. Multiprocessing + module-level singletons cause re-initialization

Each `mp.Process` worker re-imports all modules, creating new `RedisQueueManager` singletons per process. While this is correct for multiprocessing, it means:
- Each process creates its own Redis connection pool
- Config is re-loaded and re-validated per process
- Bloom filters are **not shared** across discovery workers (each has its own, which is intended but means Bloom filter FPR is per-worker, not global)

---

## Summary Table

| Severity | Count | Key Themes |
|----------|-------|------------|
| 🔴 CRITICAL | 5 | Infinite loop, unconditional re-queue, dead reconciliation, encoding issues |
| 🟠 HIGH | 8 | Wrong stat fallbacks, missing cleanup, stale heartbeats, type mismatches |
| 🟡 MEDIUM | 9 | Misleading metrics, fragile comparisons, destructive text transforms |
| 🔵 LOW | 7 | Dead code, duplicate defs, unnecessary allocations |
| Architectural | 4 | No backpressure, counter drift, no graceful drain |

**Total new issues found: 33**
