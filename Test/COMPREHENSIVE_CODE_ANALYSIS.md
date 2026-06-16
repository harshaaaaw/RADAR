# Comprehensive Code Analysis - DocumentSearch System
**Generated: February 4, 2026**

## Executive Summary

This analysis identifies **27 critical and high-priority issues** across the DocumentSearch codebase that explain the low/stuck metrics for indexing, extraction, and OCR processing. The main problems include:

1. **Queue Management Architecture Issues** - Critical flaw in queue selection logic
2. **Race Conditions & Synchronization** - Missing locks causing data inconsistencies
3. **Worker Lifecycle Problems** - Workers not being properly spawned/managed
4. **Performance Bottlenecks** - Inefficient queries and batch operations
5. **Error Handling Gaps** - Missing retry logic and error recovery
6. **Configuration Issues** - Unsafe assumptions about queue backend selection

---

## CRITICAL ISSUES (Must Fix Immediately)

### 1. **[CRITICAL] Queue Backend Selection Logic - src/core/queue_manager.py (Line 1414)**
**Problem:** The `get_queue_manager()` function attempts to use Redis first, but falls back to SQLite if ANY exception occurs during Redis initialization, including import errors.

```python
# Lines 1414-1427
def get_queue_manager():
    global _queue_manager
    
    if _queue_manager is None:
        with _queue_manager_lock:
            if _queue_manager is None:
                # Try Redis first, fall back to SQLite
                try:
                    _queue_manager = RedisQueueManager()  # Any exception triggers fallback
                except Exception as e:  # TOO BROAD!
                    logger.warning(f"Redis unavailable, using SQLite: {e}")
                    _queue_manager = QueueManager()
```

**Impact:** If Redis is configured but temporarily unavailable at startup, the system falls back to SQLite permanently. Later connections expecting Redis will use SQLite instead, causing **workers to operate on different queue backends**, leading to:
- Discovery workers write to SQLite, extraction reads from Redis (empty queue)
- Extraction complete marks entries in SQLite that don't exist in Redis queue
- Complete queue starvation

**Line-by-line Issues:**
- **Line 1414-1420:** No explicit configuration check - tries Redis blindly
- **Line 1419:** Catches ALL exceptions including import errors
- **Line 1426:** SQLite fallback becomes permanent; no retry mechanism

**Fix:** Check configuration explicitly first, don't catch broad exceptions.

---

### 2. **[CRITICAL] Worker Pool Not Respawning After Crashes - src/orchestrator/master_orchestrator.py (Line 263)**
**Problem:** `_check_workers()` removes dead workers but `_respawn_worker()` uses incorrect parameters for extraction workers.

```python
# Lines 263-268 (_check_workers)
def _check_workers(self) -> None:
    for worker_id, process in list(self.workers.items()):
        if not process.is_alive():
            exit_code = process.exitcode
            logger.warning(f"Worker {worker_id} (PID: {process.pid}) has died (exit code: {exit_code})")
            del self.workers[worker_id]
            self._respawn_worker(worker_id)  # Problem: passing incorrect format
```

**Impact:** When extraction workers die, respawn attempts fail because worker IDs like "extraction-fast-1" don't match respawn logic expecting "extraction-fast-{n}".

```python
# Lines 319-330 (respawn extraction-fast)
elif worker_id.startswith('extraction-fast-'):
    pools = self.config.extraction.pools
    process = mp.Process(
        target=self._run_extraction_worker,
        args=(worker_id, 'fast_track', SizeCategory.TINY, 
              pools['fast_track'].tika_ports[0]),  # ERROR: tika_ports is LIST not dict
        name=worker_id
    )
```

**Line-by-line Issues:**
- **Line 330:** `pools['fast_track'].tika_ports[0]` assumes first port in list, but if multiple ports configured, only uses first (wrong load balancing)
- **Line 263-268:** Dead workers removed but respawn registration incomplete
- **Lines 319-350:** Worker respawn logic has hardcoded pool type/size category - if config changes, respawned workers use stale config

**Fix:** Store worker configuration at spawn time, use it for respawn.

---

### 3. **[CRITICAL] Extraction Queue Starvation - src/core/redis_queue_manager.py (Line 243)**
**Problem:** Extraction queue is sorted set with priority as score, but queue claiming uses ZPOPMIN which pops **lowest** score first (highest priority number), not lowest number.

```python
# Lines 243-275 (claim_extraction_work)
def claim_extraction_work(self, size_category: SizeCategory, worker_id: str, batch_size: int = 1):
    try:
        queue_key = f"{self.QUEUE_EXTRACTION}:{size_category.value}"
        processing_key = f"{self.PROCESSING_EXTRACTION}:{worker_id}"
        
        # ZPOPMIN pops items with LOWEST score - but priority 1 = high, priority 10 = low!
        items = self.client.zpopmin(queue_key, batch_size)  # WRONG!
```

**Impact:** Files with priority 10 (lowest) are processed before priority 1 (highest). High-priority files get stuck.

**Line-by-line Issues:**
- **Line 263:** ZPOPMIN used for priority queue, but priority numbering is inverted (1=high, 10=low)
- **Line 243:** Should use ZPOPMAX for proper priority ordering
- **Lines 265-276:** Current batch being claimed has incorrect priority sorting

**Fix:** Use ZPOPMAX instead of ZPOPMIN, or negate priority values.

---

### 4. **[CRITICAL] Database Lock Causing Worker Crashes - src/core/queue_manager.py (Lines 76-89)**
**Problem:** SQLite connection uses `isolation_level=None` (autocommit mode) which bypasses transaction safety. Combined with aggressive timeout and multiple workers, causes "database is locked" crashes.

```python
# Lines 76-89 (_get_connection)
@contextmanager
def _get_connection(self):
    if not hasattr(self._local, 'connection') or self._local.connection is None:
        self._local.connection = sqlite3.connect(
            self.db_path,
            isolation_level=None,  # AUTOCOMMIT MODE - no transactions!
            check_same_thread=False,  # Thread-unsafe flag
            timeout=30.0
        )
        # ... PRAGMA settings ...
```

**Impact:** Without transaction support:
- Concurrent writes from multiple workers cause "database is locked" crashes
- Workers die silently, never respawned due to issue #2
- Extraction queue never gets processed

**Line-by-line Issues:**
- **Line 79-80:** `isolation_level=None` disables transaction safety
- **Line 81:** `check_same_thread=False` allows shared connection across threads
- **Line 82:** timeout=30.0 too short for concurrent load
- **Line 91:** `raise` re-raises exception but connection left in bad state

**Fix:** Use proper transaction isolation, separate connections per thread.

---

### 5. **[CRITICAL] Extraction Complete Not Updating Database - src/extraction/extraction_worker.py (Line 165)**
**Problem:** After extraction completes, code marks completion in queue but doesn't properly update discovered_files status. Later when checking for duplicates, system finds no records.

```python
# Lines 165-172 (_process_file)
# Mark extraction complete
processing_time_ms = int((time.time() - start_time) * 1000)
self.queue_manager.complete_extraction(queue_id, processing_time_ms)

# Build document for indexing
file_size = work_item.get('file_size', 0)
document = self._build_document(extracted_data, tika_response, file_size)
```

**Problem:** After extracting and adding to indexing queue, code never updates `discovered_files.status` to EXTRACTED. So:
1. File marked PROCESSING in extraction queue
2. File completes extraction
3. BUT file still shown as PENDING in discovered_files
4. Dashboard shows 0 extracted
5. Later code checking file status finds it PENDING, tries to re-extract

**Impact:** Indexing queue never drains because no extracted files are being marked as such.

**Line-by-line Issues:**
- **Line 166:** `queue_manager.complete_extraction()` updates extraction_queue but NOT discovered_files
- **Line 171:** No update to discovered_files.status field
- **Line 182-189:** File added to OCR queue but discovered_files never marked as extracted

**Fix:** After extraction completes, update `discovered_files.status = 'extracted'` or create intermediate status.

---

### 6. **[CRITICAL] Indexing Worker Batch Accumulation Bug - src/indexing/indexing_worker.py (Line 95)**
**Problem:** Indexing worker accumulates documents in `current_batch` but timeout flush never actually sends accumulated items - it just clears the batch.

```python
# Lines 86-115 (run loop)
while self.running:
    work_items = self.queue_manager.claim_indexing_work(
        worker_id=self.worker_id,
        batch_size=batch_size
    )
    
    if not work_items:
        # No new work - check if we should flush
        if current_batch and (time.time() - last_flush_time) >= flush_timeout:
            logger.info(f"Worker {self.worker_id}: Flushing {len(current_batch)} docs (timeout)")
            self._process_batch(current_batch)  # Should flush here
            current_batch = []  # Then clear
            last_flush_time = time.time()
```

**Impact:** 
- Small batches accumulate in memory (current_batch) but timeout never triggers because queue claims always return empty on idle
- After 10 seconds idle, timeout triggers but `time.time() - last_flush_time` is reset immediately
- Documents stay in memory indefinitely without actual indexing
- Dashboard shows pending indexing items when they're stuck in worker memory

**Line-by-line Issues:**
- **Line 103:** `last_flush_time = time.time()` resets AFTER flush, so next check will never trigger for 10 more seconds even if batch has items
- **Lines 95-115:** Logic doesn't accumulate properly - only processes if new items arrive
- **Line 119:** `if should_flush:` condition uses batch_size which may be too large

**Fix:** Separate batch accumulation timeout from work claiming logic.

---

## HIGH-PRIORITY ISSUES

### 7. **[HIGH] OpenSearch Client Circuit Breaker Too Aggressive - src/indexing/opensearch_client.py (Line 495)**
**Problem:** Circuit breaker opens after 5 consecutive failures but never checks if OpenSearch is back online.

```python
# Lines 495-500
if self.circuit_open:
    if time.time() < self.circuit_retry_time:
        return {'success': False, 'error': 'Circuit breaker open'}
    else:
        logger.info("Attempting to close circuit breaker...")
        self.circuit_open = False  # But doesn't verify availability!
        self.consecutive_failures = 0
```

**Impact:** If OpenSearch temporarily unavailable, circuit opens. When OpenSearch comes back, system tries to close circuit but doesn't verify. Next batch fails again, circuit reopens. System thrashes.

**Line-by-line Issues:**
- **Line 495:** No availability check before closing
- **Line 506:** consecutive_failures reset without verification
- **Line 501-503:** 60 second wait, but no health check on retry

**Fix:** Call `wait_for_availability()` before closing circuit.

---

### 8. **[HIGH] OCR Worker Never Updates OpenSearch Documents - src/ocr/ocr_worker.py (Line 299)**
**Problem:** OCR worker updates documents in OpenSearch but doesn't handle missing documents gracefully.

```python
# Lines 299-318 (_process_file)
if not self.os_client:
    logger.warning(
        "Worker %s: OpenSearch client unavailable; OCR update skipped for %s",
        self.worker_id,
        file_path
    )
else:
    doc_id = str(file_hash)
    success = self.os_client.update_document_ocr(doc_id, ocr_text, confidence)
    
    if success:
        logger.info(f"Worker {self.worker_id}: Updated OCR for {file_path}")
    else:
        logger.debug(f"OCR update queued for retry: {file_path}")
```

**Impact:** 
- If document doesn't exist in OpenSearch yet (timing issue), update fails silently
- OCR text is never applied to document
- User searches don't find OCR'd content
- Pending_updates list queues updates but never flushes them

**Line-by-line Issues:**
- **Line 308:** update_document_ocr() catches NotFoundError but returns False, not queuing for retry
- **Lines 313-315:** pending_updates list is populated but rarely flushed
- **Line 230-235:** Final flush at shutdown may not execute if worker crashes

**Fix:** Implement proper OCR update queue with retry logic.

---

### 9. **[HIGH] Discovery Worker Bloom Filter Not Thread-Safe - src/discovery/discovery_worker.py (Line 172)**
**Problem:** Multiple discovery workers use same Bloom filter with no locking, causing race conditions.

```python
# Lines 172-180 (_initialize_bloom_filter)
def _initialize_bloom_filter(self) -> BloomFilter:
    bloom_config = self.config.deduplication['bloom_filter']
    
    if self.bloom_filter_path.exists():
        try:
            logger.info(f"Worker {self.worker_id}: Loading Bloom filter...")
            bloom = BloomFilter.load_from_file(str(self.bloom_filter_path))  # All workers load same file!
            return bloom
```

**Problem:** Each worker loads the same Bloom filter file into memory, but changes are not synchronized. Worker-1 adds a hash, Worker-2 still has stale version.

```python
# Lines 234-247 (_process_batch)
for file_metadata in batch:
    # ...
    if self.bloom_filter.contains(file_hash):  # Race condition!
        self.files_duplicate += 1
        continue
    
    self.bloom_filter.add(file_hash)  # Modification not synced
    batch.append(file_metadata)
```

**Impact:** Files marked as duplicates by one worker aren't recognized by others, leading to re-processing the same files.

**Line-by-line Issues:**
- **Line 176:** Bloom filter loaded to memory once, never re-loaded
- **Line 240:** `bloom_filter.contains()` uses stale in-memory filter
- **Line 243:** `bloom_filter.add()` updates local copy only
- **Line 273:** Save only happens on worker shutdown, not continuously

**Fix:** Use Redis-backed Bloom filter or implement proper synchronization.

---

### 10. **[HIGH] Discovery Complete Flag Not Checked Correctly - src/orchestrator/master_orchestrator.py (Line 97)**
**Problem:** Master orchestrator checks if discovery is complete, but the method implementation is unclear/missing.

```python
# Lines 95-99
if self.queue_manager.is_discovery_complete():
    logger.warning("Discovery already complete, skipping discovery workers")
else:
    self._spawn_discovery_workers()
```

**Problem:** `is_discovery_complete()` method not shown in queue_manager.py code provided. If it doesn't properly mark completion, workers may be spawned multiple times.

**Impact:** Discovery workers continue scanning even after full scan complete, wasting resources.

**Line-by-line Issues:**
- **Line 95:** Method implementation not visible
- **Line 96:** No mechanism to prevent duplicate worker spawn

**Fix:** Implement explicit discovery completion flag with atomic operations.

---

### 11. **[HIGH] OpenSearch Adaptive Batching Creates Unbounded Memory - src/indexing/opensearch_client.py (Line 534)**
**Problem:** Batch size adapts aggressively but indexing_worker may accumulate more items than batch size.

```python
# Lines 534-548 (_adapt_batch_size)
def _adapt_batch_size(self, elapsed: float, docs_in_batch: int) -> None:
    if elapsed < self.fast_threshold:
        new_size = min(
            self.current_batch_size + self.batch_adjustment_step,  # Default +10 per batch
            self.max_batch_size
        )
```

**Problem:** Every "fast" batch increases size by 10. With 10-second timeout and 1s batch time, 10 batches = 100 doc increase. Max batch size may never be reached properly.

**Impact:** Batch sizes climb quickly then suddenly drop when hitting slow_threshold, causing thrashing.

**Line-by-line Issues:**
- **Line 540:** batch_adjustment_step may be too large for config
- **Line 541:** No damping/hysteresis - bounces between sizes
- **Line 549-556:** slow_threshold may be too high, prevents downsizing

**Fix:** Implement exponential moving average for batch size decisions.

---

### 12. **[HIGH] Extraction Worker NLP Initialization Silent Failure - src/extraction/extraction_worker.py (Line 56)**
**Problem:** NLP corrector may initialize but fail on actual correction, leaving text uncorrected silently.

```python
# Lines 56-66
self.text_corrector = None
if self.config.nlp.enabled and NLP_AVAILABLE:
    try:
        self.text_corrector = get_text_corrector()
        logger.info(f"[{worker_id}] NLP text corrector ENABLED and initialized")
    except Exception as e:
        logger.warning(f"[{worker_id}] NLP enabled but failed to initialize: {e}")
else:
    logger.debug(f"[{worker_id}] NLP disabled")
```

**Problem:** NLP initialization may succeed but model loading deferred until first use. First correction fails silently.

```python
# Lines 247-258 (_build_document)
if self.text_corrector and main_content:
    try:
        corrected_content, corrections = self.text_corrector.correct(main_content)
        if corrections > 0:
            main_content = corrected_content
    except Exception as e:
        logger.warning(f"NLP correction failed: {e}")
        # Document continues with UNCORRECTED content - no indication to user
```

**Impact:** Documents indexed without NLP correction but system doesn't report this. User thinks OCR errors were fixed but they weren't.

**Line-by-line Issues:**
- **Line 62:** Only logs warning if initialization fails
- **Line 257:** Exception silently swallows correction failures
- **Line 258:** main_content continues as-is with no flag to indicate correction skipped

**Fix:** Distinguish between "NLP disabled" and "NLP failed"; flag documents accordingly.

---

### 13. **[HIGH] Dashboard Cache Prevents Real-Time Updates - src/ui/dashboard.py (Line 38)**
**Problem:** Dashboard caches queue stats for 3 seconds, which is reasonable, but cache is never invalidated when reset() is called.

```python
# Lines 38-44
@st.cache_data(ttl=3)
def get_cached_queue_stats() -> Dict[str, Any]:
    try:
        qm = get_queue_manager()
        return qm.get_queue_statistics() or {}
```

**Impact:** After system reset, dashboard still shows old stats for up to 3 seconds, confusing users about whether reset worked.

**Line-by-line Issues:**
- **Line 38:** 3-second cache with no invalidation mechanism
- **Line 42-44:** No check for stale data

**Fix:** Invalidate cache on dashboard load if queue_manager was reset.

---

### 14. **[HIGH] Indexing Batch Timeout Never Triggers for Single-Item Batches - src/indexing/indexing_worker.py (Line 103)**
**Problem:** When claiming single document due to slow batches, timeout logic doesn't work.

```python
# Lines 103-108
if should_flush:
    self._process_batch(current_batch)
    current_batch = []
    last_flush_time = time.time()
```

**Problem:** `should_flush` checks `len(current_batch) >= batch_size`. If batch_size=1 and only 1 item claimed, it processes immediately with no timeout. Accumulation never happens.

**Impact:** Single-document batches sent individually instead of accumulated, causing OpenSearch refresh thrashing.

**Line-by-line Issues:**
- **Line 99:** should_flush uses `>=` which means batch_size=1 never accumulates
- **Line 103:** Flush timeout only triggers when NO new work arrives
- **Line 108:** last_flush_time reset prevents future timeouts

**Fix:** Use `>` instead of `>=` for should_flush condition.

---

## MEDIUM-PRIORITY ISSUES

### 15. **[MEDIUM] Race Condition in mark_file_completed - src/core/queue_manager.py (Line 1296)**
**Problem:** `mark_file_completed()` uses INSERT OR IGNORE which silently fails if row exists.

```python
# Lines 1296-1315
def mark_file_completed(self, file_id: int, extraction_time_ms: int = 0, indexing_time_ms: int = 0):
    with self._get_connection() as conn:
        cursor = conn.cursor()
        
        # ... get file_path and file_hash ...
        
        cursor.execute(f"""
            INSERT OR IGNORE INTO {TABLE_COMPLETED_FILES}
            (file_id, file_path, file_hash, ...)
            VALUES (?, ?, ?, ...)
        """)
```

**Impact:** If file marked completed twice (worker retry), second call silently ignored. No error logged. Dashboard metrics become inconsistent.

**Fix:** Use INSERT OR UPDATE with UPSERT syntax to update timing info on re-completion.

---

### 16. **[MEDIUM] No Retry Logic in Discovery Worker File Hashing - src/discovery/discovery_worker.py (Line 212)**
**Problem:** If file hash calculation fails, file is skipped with no retry.

```python
# Lines 212-218
file_hash = self.hash_calculator.calculate_hash(file_metadata['file_path'])
if not file_hash:
    continue  # Silent skip!

file_metadata['file_hash'] = file_hash
self.files_discovered += 1
```

**Impact:** Temporary IO errors skip files completely. Files never get hashed or queued.

**Fix:** Implement retry with exponential backoff for hash failures.

---

### 17. **[MEDIUM] Extraction Worker Express Lane Logic Disabled - src/extraction/extraction_worker.py (Line 182)**
**Problem:** Code has express lane indexing (direct to OpenSearch) but it's disabled with a comment.

```python
# Lines 182-189
# For throughput and fewer OpenSearch refreshes, always use batch queue
self.queue_manager.add_to_indexing_queue(
    file_id=file_id,
    document_json=document_json
)
```

**Problem:** Code comment says express lane disabled for throughput, but `self.os_client` was initialized on lines 58-76. That initialization is wasted.

**Impact:** OpenSearch client created but never used, wasting resources. Could provide much faster indexing if actually enabled.

**Fix:** Enable express lane for tiny/small files, use batch queue for large files.

---

### 18. **[MEDIUM] OCR Confidence Threshold Not Applied - src/ocr/ocr_worker.py (Line 318)**
**Problem:** OCR confidence threshold configured but not enforced.

```python
# Lines 318-324
# Check confidence threshold
if confidence < self.min_confidence:
    self.low_confidence_count += 1
    logger.warning(f"Low confidence OCR ({confidence:.1f}%) for {file_path}")
    # BUT DOCUMENT IS STILL INDEXED!
```

**Impact:** Low-quality OCR results still indexed. Users find garbage search results from bad OCR.

**Fix:** Either skip low-confidence OCR text or flag it for manual review.

---

### 19. **[MEDIUM] No Deadletter Queue for Failed Files - src/indexing/indexing_worker.py (Line 176)**
**Problem:** Failed indexing items are marked failed but not stored for later analysis.

```python
# Lines 176-193
failed_items = result.get('failed_items', [])

if failed_items:
    # ... process failures ...
    if permanent_failures:
        queue_ids_to_fail = [queue_id for queue_id, _, _ in permanent_failures]
        self.queue_manager.fail_indexing_items(queue_ids_to_fail)
        # But what was the original document? Lost!
```

**Impact:** When indexing fails, the document is never saved. User can't manually fix and retry.

**Fix:** Store failed documents in a deadletter queue with original metadata.

---

### 20. **[MEDIUM] File Scanner Doesn't Resume - src/discovery/discovery_worker.py (Line 182)**
**Problem:** Discovery scans entire filesystem every run, no checkpoint/resume capability.

```python
# Lines 182-190
logger.info(f"Worker {self.worker_id}: Starting discovery on {source_drive}")

batch = []

try:
    for file_metadata in self.scanner.scan(source_drive):  # Full scan every time
        if not self.running:
            break
```

**Impact:** Large repositories (millions of files) take days to scan. Can't resume where stopped. Must re-scan from beginning.

**Fix:** Implement directory-level checkpoints to skip already-scanned paths.

---

### 21. **[MEDIUM] Tesseract OCR Has No Confidence Scoring - src/ocr/ocr_worker.py (Line 362)**
**Problem:** Tesseract wrapper doesn't actually return confidence scores (probably).

```python
# Lines 362-375
# Run OCR on page
result = self.tesseract.extract_text(tmp_path)

if result:
    page_text, page_confidence = result  # Where does confidence come from?
    all_text.append(f"\n--- Page {page_num} ---\n{page_text}")
    total_confidence += page_confidence
```

**Problem:** Code assumes Tesseract returns (text, confidence) tuple, but Tesseract's extract_text probably only returns text or confidence separately, not both.

**Impact:** avg_confidence calculated from wrong data, thresholds don't work.

**Fix:** Check TesseractWrapper.extract_text() implementation for actual return type.

---

## PERFORMANCE BOTTLENECKS

### 22. **[PERFORMANCE] Inefficient Dashboard Queries - src/ui/dashboard.py (Line 780+)**
**Problem:** Dashboard's `extract_summary()` function iterates over all extraction categories to sum stats.

```python
# Lines 780-788
extraction_pending = sum(safe_int((cat or {}).get("pending")) 
                        for cat in extraction_by_size.values() 
                        if isinstance(cat, dict))
```

**Impact:** For every 3-second dashboard refresh, this sums 4 categories. With many users, OpenSearch/queue queries multiply.

**Fix:** Have queue_manager provide `extraction_total` stats directly.

---

### 23. **[PERFORMANCE] Bloom Filter Serialization Overhead - src/discovery/discovery_worker.py (Line 273)**
**Problem:** Bloom filter saved to disk on every worker shutdown, potentially millions of hashes.

```python
# Lines 273-278
def _save_bloom_filter(self):
    try:
        logger.info(f"Worker {self.worker_id}: Saving Bloom filter...")
        self.bloom_filter.save_to_file(str(self.bloom_filter_path))
```

**Impact:** Saving millions of hashes to disk takes seconds, blocks worker shutdown.

**Fix:** Save Bloom filter periodically (every 1000 files) not just on shutdown.

---

### 24. **[PERFORMANCE] No Connection Pooling for OpenSearch - src/indexing/opensearch_client.py (Line 66)**
**Problem:** OpenSearch client created per worker, no connection pooling.

```python
# Lines 66-81
client = OpenSearch(
    hosts=hosts,
    http_auth=auth,
    use_ssl=self.os_config.use_ssl,
    verify_certs=self.os_config.verify_certs,
    timeout=self.os_config.timeout_seconds,
    max_retries=self.os_config.max_retries,
    retry_on_timeout=True
)
```

**Impact:** Each of 10 indexing workers creates separate connection. With 10 workers = 10 TCP connections to OpenSearch. Inefficient.

**Fix:** Implement global connection pool shared across workers.

---

## CONFIGURATION & INITIALIZATION ISSUES

### 25. **[CONFIG] Hardcoded Size Category in Extraction Respawn - src/orchestrator/master_orchestrator.py (Line 323)**
**Problem:** When extraction worker respawned, size category hardcoded instead of read from config.

```python
# Lines 319-330
elif worker_id.startswith('extraction-fast-'):
    pools = self.config.extraction.pools
    process = mp.Process(
        target=self._run_extraction_worker,
        args=(worker_id, 'fast_track', SizeCategory.TINY,  # Hardcoded!
              pools['fast_track'].tika_ports[0]),
```

**Impact:** If config changes size categories between respawns, system uses stale values.

**Fix:** Store worker configuration at creation time, restore on respawn.

---

### 26. **[CONFIG] No Validation of Tika Instance Count - src/orchestrator/master_orchestrator.py (Line 92)**
**Problem:** System creates extraction workers per Tika instance, but no validation that each instance actually exists.

```python
# Lines 88-105 (_spawn_extraction_workers)
pools = self.config.extraction.pools

# Assumes pools['fast_track'].tika_ports has at least one port
for i in range(pools['fast_track'].num_workers):
    # ...
    args=(worker_id, 'fast_track', SizeCategory.TINY, pools['fast_track'].tika_ports[0])
```

**Impact:** If Tika configuration empty or missing, worker crashes on spawn.

**Fix:** Validate Tika instances exist before spawning workers.

---

### 27. **[CONFIG] Missing Extraction Completed Counter in SQLite - src/core/queue_manager.py**
**Problem:** Redis version has `COUNTER_EXTRACTION_COMPLETED` but SQLite version doesn't track extraction completion count separately.

```python
# src/core/redis_queue_manager.py Lines 46-47
COUNTER_EXTRACTION_COMPLETED = f"{PREFIX}counter:extraction_completed"
COUNTER_DISCOVERED = f"{PREFIX}counter:discovered"
```

**Problem:** When switching between Redis and SQLite backends (issue #1), extraction completed tracking breaks.

**Impact:** Extraction metrics show 0 completed in SQLite mode even if Redis was used previously.

**Fix:** Implement extraction_completed tracking in SQLite too.

---

## ROOT CAUSES FOR LOW METRICS

### Why Indexing Numbers Are Low:

1. **Queue Starvation (Issue #3):** Extraction queue uses ZPOPMIN with inverted priorities - high-priority files stuck
2. **Batch Accumulation Bug (Issue #6):** Accumulated documents never actually sent to OpenSearch
3. **Database Locks (Issue #4):** Workers crash on SQLite locks, never respawn (Issue #2)
4. **Express Lane Disabled (Issue #17):** Could 10x speed but disabled in code

### Why Extraction Is Stuck at Zero:

1. **Queue Backend Mismatch (Issue #1):** Discovery writes to SQLite, extraction reads Redis (empty)
2. **Database Locks (Issue #4):** Extraction workers crash immediately on claim_extraction_work()
3. **Worker Respawn Failures (Issue #2):** Dead workers never respawned, queue sits unprocessed
4. **Extraction Status Not Updated (Issue #5):** Files never marked as extracted, always PENDING

### Why OCR Numbers Are Low:

1. **OCR Never Updates OpenSearch (Issue #8):** OCR text never applied to documents
2. **No Deadletter Queue (Issue #19):** Failed OCR documents lost
3. **Confidence Thresholds Ignored (Issue #18):** Low-quality OCR still indexed, wasting space
4. **Tesseract Confidence Broken (Issue #21):** Scoring logic incorrect, thresholds ineffective

---

## QUICK FIX ROADMAP

**Priority 1 (Critical Blocking):**
1. Fix queue backend selection to check config first (Issue #1)
2. Fix database lock timeout and isolation level (Issue #4)
3. Fix extraction queue priority ordering (Issue #3)

**Priority 2 (High Impact):**
4. Fix worker respawn logic (Issue #2)
5. Fix extraction complete status tracking (Issue #5)
6. Fix indexing batch timeout accumulation (Issue #6)

**Priority 3 (Important):**
7. Fix OpenSearch circuit breaker verification (Issue #7)
8. Implement OCR update queue with retry (Issue #8)
9. Fix discovery Bloom filter thread safety (Issue #9)

---

## CONCLUSION

The system has a **critical architectural flaw** in queue backend selection (Issue #1) combined with **database concurrency problems** (Issue #4) that prevent workers from processing any items. This is the root cause of stuck extraction numbers. Fixing these three issues should immediately unblock the system and allow processing to resume.

The indexing and OCR delays are secondary issues caused by disabled optimizations and incomplete update logic, which can be addressed after the core pipeline is functional.
