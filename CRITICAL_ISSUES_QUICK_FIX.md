# QUICK REFERENCE - Critical Issues Summary

## The Top 3 Issues Causing Your Stuck/Zero Metrics

### 🔴 CRITICAL ISSUE #1: Queue Backend Selection Logic Broken
**File:** `src/core/queue_manager.py` Lines 1414-1427
**Problem:** System tries Redis first, falls back to SQLite on ANY error. If Redis unavailable at startup, workers permanently use SQLite instead of Redis, causing complete queue starvation.
**Impact:** Discovery writes to SQLite queue, extraction reads Redis queue (empty) → No extraction happens
**Symptom:** Extraction stuck at 0

---

### 🔴 CRITICAL ISSUE #2: SQLite Database Locked - Workers Crash
**File:** `src/core/queue_manager.py` Lines 76-89
**Problem:** SQLite connections use autocommit mode (`isolation_level=None`) with multiple concurrent workers → "database is locked" crashes
**Impact:** Extraction workers crash immediately on queue claim, die silently
**Symptom:** Random worker deaths, extraction stuck

---

### 🔴 CRITICAL ISSUE #3: Extraction Queue Priority Inverted
**File:** `src/core/redis_queue_manager.py` Lines 263
**Problem:** Queue uses ZPOPMIN which pops LOWEST scores first. Priority 1=high, Priority 10=low. So low-priority files processed first, high-priority stuck.
**Impact:** Files with priority 10 stuck behind priority 1 files
**Symptom:** Indexing appears stuck on certain files

---

## The Top 3 Issues Causing Low Indexing

### 🔴 CRITICAL ISSUE #5: Extraction Complete Not Updating Database
**File:** `src/extraction/extraction_worker.py` Line 165-171
**Problem:** After extraction completes, `discovered_files.status` never updated. File stays PENDING forever.
**Impact:** Queue drains but files never marked as extracted
**Symptom:** Extraction complete counter shows 0

---

### 🟠 HIGH ISSUE #6: Indexing Batch Accumulation Timeout Broken
**File:** `src/indexing/indexing_worker.py` Lines 95-115
**Problem:** Timeout-flush for accumulated documents never actually triggers properly
**Impact:** Small batches sit in worker memory indefinitely
**Symptom:** Pending indexing items stuck

---

### 🟠 HIGH ISSUE #2: Worker Respawn Failures
**File:** `src/orchestrator/master_orchestrator.py` Lines 263-268
**Problem:** When extraction workers die, respawn logic fails. Dead workers never replaced.
**Impact:** Extraction workers die, queue never processes more work
**Symptom:** Extraction stuck after processing few files

---

## The Top 3 Issues Causing Low OCR

### 🟠 HIGH ISSUE #8: OCR Never Updates OpenSearch
**File:** `src/ocr/ocr_worker.py` Line 299-318
**Problem:** OCR text extracted but update to OpenSearch fails silently for missing documents
**Impact:** OCR results never applied to indexed documents
**Symptom:** OCR completed but search doesn't find OCR'd text

---

### 🟠 MEDIUM ISSUE #18: OCR Confidence Threshold Ignored
**File:** `src/ocr/ocr_worker.py` Line 318-324
**Problem:** Low-confidence OCR results still indexed despite threshold
**Impact:** Garbage OCR text in index
**Symptom:** OCR hits but low quality

---

### 🟠 MEDIUM ISSUE #21: Tesseract Confidence Broken
**File:** `src/ocr/ocr_worker.py` Line 362-375
**Problem:** Code assumes Tesseract returns (text, confidence) but probably doesn't
**Impact:** Confidence scores calculated incorrectly
**Symptom:** Threshold logic doesn't work

---

## Recommendations for Fixes

### IMMEDIATE (Do Now - 2 hours):
1. **Fix Issue #1**: Check queue config explicitly before trying Redis
   ```python
   if config.queue.backend == 'redis':
       try_redis()
   else:
       use_sqlite()
   ```

2. **Fix Issue #2**: Change SQLite isolation mode
   ```python
   isolation_level='DEFERRED'  # Instead of None
   timeout=60.0  # Instead of 30.0
   ```

3. **Fix Issue #3**: Use ZPOPMAX instead of ZPOPMIN
   ```python
   items = self.client.zpopmax(queue_key, batch_size)
   ```

### SHORT TERM (Next 2 hours):
4. **Fix Issue #5**: Update discovered_files status after extraction
   ```python
   self.queue_manager.mark_discovered_file_extracted(file_id)
   ```

5. **Fix Issue #2**: Implement proper worker respawn with stored config

6. **Fix Issue #6**: Fix batch accumulation timeout logic

### MEDIUM TERM (Next 4 hours):
7. **Fix Issue #8**: Implement OCR update retry queue
8. **Fix Issue #18**: Enforce OCR confidence thresholds
9. **Fix Issue #21**: Check TesseractWrapper return format

---

## Test Validation Plan

After fixing issues #1-3:
```
1. Reset system: python src/main.py reset --force
2. Start system: python src/main.py start
3. Monitor extraction metrics: Should increase immediately
4. Check for worker crashes: Should see no "database is locked" errors
```

After fixing issues #4-6:
```
1. Extraction should complete more files per minute
2. Indexing queue should drain consistently
3. Dashboard should show proper metrics
```

---

## Full Detailed Analysis

See: `COMPREHENSIVE_CODE_ANALYSIS.md` for all 27 issues with line numbers and detailed explanations.
