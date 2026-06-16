# FIX PLAN & APPROACH DOCUMENT
**Date:** February 4, 2026  
**Prepared For:** Complete System Recovery  
**Status:** Ready for Implementation

---

## APPROACH OVERVIEW

The DocumentSearch system has 27 identified issues across 4 severity levels. This document outlines the strategic approach to fix them efficiently without causing cascading failures.

### **Phase Strategy**
1. **Phase 1 (CRITICAL):** Fix the 3 blocking issues that prevent any processing
2. **Phase 2 (HIGH):** Fix 6 issues causing extremely low performance
3. **Phase 3 (MEDIUM):** Fix 7 issues affecting data quality and metrics
4. **Phase 4 (LOW):** Fix 11 maintenance and logging issues

### **Rollout Strategy**
- Fix issues in dependency order (don't fix A until B is fixed if A depends on B)
- Test after each phase
- Keep system running during fixes where possible

---

## PHASE 1: CRITICAL FIXES (Blocking Issues)

### **Goal:** Get extraction workers processing files from queue

---

### **Fix #1: Synchronize SQLite and Redis Queues**
**Current Issue:** Discovery writes to SQLite, extraction reads from Redis (empty)  
**Fix Location:** `src/core/queue_manager.py` lines 1414-1427  

#### **Approach:**
1. **Detect which backend has data:**
   ```
   - Check Redis: Count files in extraction queue
   - Check SQLite: Count files in discovery_queue table
   - If Redis = 0 AND SQLite > 0: Sync needed
   ```

2. **Implement automatic sync function:**
   ```python
   def sync_queues_to_redis():
       # Read all pending files from SQLite
       sqlite_files = get_sqlite_queue_manager().get_pending_extraction_files()
       
       # Add them to Redis extraction queue
       redis_qm = get_redis_queue_manager()
       for file in sqlite_files:
           redis_qm.add_to_extraction_queue(
               file_id=file.id,
               file_path=file.path,
               file_size=file.size,
               size_category=file.category,
               priority=file.priority
           )
       
       # Delete from SQLite (mark as synced)
       sqlite_qm.mark_synced(sqlite_files)
   ```

3. **Add sync trigger on startup:**
   ```python
   def __init__():
       # After initializing queue manager
       if is_redis_queue_manager():
           # Check if sync needed
           if redis_queue.is_empty() and sqlite_queue.has_pending():
               logger.info("Syncing SQLite queue to Redis...")
               sync_queues_to_redis()
   ```

4. **Add periodic sync check:**
   ```python
   # In master_orchestrator._main_loop()
   if not queue_manager.is_redis():  # If using SQLite fallback
       if time_since_last_sync > 60:  # Every 60 seconds
           sync_queues_to_redis()
   ```

**Estimated Impact:** ✅ Extraction queue populated with files  
**Risk Level:** LOW - Data only moves forward, never lost  
**Estimated Time:** 2 hours

---

### **Fix #2: Implement Worker Respawn Loop**
**Current Issue:** Dead workers never replaced, pipeline capacity decreases  
**Fix Location:** `src/orchestrator/master_orchestrator.py` lines 240-360  

#### **Approach:**

1. **Add worker health check in main loop:**
   ```python
   def _main_loop(self):
       dead_worker_respawn_counts = {}  # Track respawn attempts
       
       while self.running:
           for worker_id, process in list(self.workers.items()):
               if process.is_alive():
                   continue  # Still running, skip
               
               # Worker is dead!
               logger.warning(f"Worker {worker_id} is dead (exit code: {process.exitcode})")
               
               # Check respawn limit
               respawn_count = dead_worker_respawn_counts.get(worker_id, 0)
               if respawn_count >= 3:
                   logger.error(f"Worker {worker_id} exceeded max respawns, giving up")
                   continue
               
               # Respawn worker
               self._respawn_worker(worker_id)
               dead_worker_respawn_counts[worker_id] = respawn_count + 1
           
           time.sleep(5)  # Check every 5 seconds
   ```

2. **Implement respawn function:**
   ```python
   def _respawn_worker(self, worker_id):
       # Determine worker type and properties from worker_id
       worker_type = worker_id.split('-')[0]  # "discovery", "extraction", "indexing", "ocr"
       
       if worker_type == "extraction":
           pool_type = worker_id.split('-')[1]  # "fast", "std", "heavy", "extreme"
           # Re-spawn with same configuration
           process = mp.Process(target=self._run_extraction_worker, args=(...))
       elif worker_type == "indexing":
           process = mp.Process(target=self._run_indexing_worker, args=(worker_id,))
       elif worker_type == "ocr":
           process = mp.Process(target=self._run_ocr_worker, args=(worker_id,))
       elif worker_type == "discovery":
           # Parse worker number from ID
           process = mp.Process(target=self._run_discovery_worker, args=(worker_num,))
       
       process.start()
       self.workers[worker_id] = process
       logger.info(f"Respawned worker {worker_id} (PID: {process.pid})")
   ```

3. **Add respawn metrics:**
   ```python
   # Track in stats
   self.respawn_counts = {}
   self.total_respawns = 0
   
   # Log periodically
   if total_respawns % 10 == 0:
       logger.warning(f"Total worker respawns: {total_respawns}")
   ```

**Estimated Impact:** ✅ Maintain pipeline capacity even when workers crash  
**Risk Level:** LOW - Respawn only kicks in after death confirmed  
**Estimated Time:** 1.5 hours

---

### **Fix #3: Fix SQLite Database Locking**
**Current Issue:** Autocommit mode causes "database is locked" crashes  
**Fix Location:** `src/core/queue_manager.py` lines 76-89  

#### **Approach:**

**Option A: Use SQLite WAL (Write-Ahead Logging) mode - RECOMMENDED**
```python
def __init__(self, db_path: str):
    self.connection = sqlite3.connect(
        db_path,
        timeout=30.0,  # Increased timeout
        check_same_thread=False
    )
    
    # Enable WAL mode (allows concurrent writes)
    self.connection.execute("PRAGMA journal_mode=WAL")
    
    # Set transaction isolation
    self.connection.isolation_level = "DEFERRED"  # Not autocommit
    
    self.cursor = self.connection.cursor()
```

**Option B: Switch to Redis-only (if Redis stable)**
```python
# In queue_manager.py:
# Always use Redis, never fallback to SQLite for production
def __init__(self):
    redis_qm = get_redis_queue_manager()  # Will raise if Redis unavailable
    return redis_qm  # No fallback
```

**Recommendation:** Use **Option A** because:
- Maintains SQLite as valid backend
- WAL mode designed for concurrent access
- Solves locking without losing fallback capability

**Implementation:**
```python
# src/core/queue_manager.py
class SQLiteQueueManager:
    def __init__(self, db_path):
        self.connection = sqlite3.connect(
            db_path,
            timeout=30.0,
            check_same_thread=False
        )
        
        # Enable WAL mode
        cursor = self.connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        
        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys=ON")
        
        # Set timeout for lock wait
        cursor.execute("PRAGMA busy_timeout=30000")  # 30 seconds
        
        # Proper transaction handling
        self.connection.isolation_level = "DEFERRED"
        
        self.cursor = self.connection.cursor()
        
    def execute_with_retry(self, query, params=None, max_retries=3):
        """Execute query with retry logic for locked databases"""
        for attempt in range(max_retries):
            try:
                if params:
                    result = self.cursor.execute(query, params)
                else:
                    result = self.cursor.execute(query)
                self.connection.commit()
                return result
            except sqlite3.OperationalError as e:
                if "database is locked" in str(e):
                    if attempt < max_retries - 1:
                        time.sleep(0.1 * (2 ** attempt))  # Exponential backoff
                        continue
                raise
```

**Estimated Impact:** ✅ Eliminate "database is locked" crashes  
**Risk Level:** LOW - WAL is standard SQLite feature  
**Estimated Time:** 1 hour

---

## PHASE 2: HIGH SEVERITY FIXES (Performance Issues)

### **Goal:** Maximize throughput and remove performance bottlenecks

---

### **Fix #4: Implement Extraction Status Updates**
**Current Issue:** Extracted files remain PENDING forever  
**Fix Location:** `src/indexing/indexing_worker.py` lines 218-230  

#### **Approach:**

1. **Track extraction completion in queue manager:**
   ```python
   # In redis_queue_manager.py (already has this)
   # But ensure it's called correctly from extraction worker
   
   def complete_extraction(self, queue_id, processing_time_ms):
       # Remove from extraction queues
       # Mark file as extraction_complete
   ```

2. **Ensure extraction worker calls it:**
   ```python
   # In extraction_worker.py _process_file()
   
   def _process_file(self, work_item):
       # ... extraction happens ...
       
       # MUST call this to update status
       processing_time_ms = int((time.time() - start_time) * 1000)
       self.queue_manager.complete_extraction(queue_id, processing_time_ms)
       
       # Then queue for indexing
       self.queue_manager.add_to_indexing_queue(...)
   ```

3. **Add verification logging:**
   ```python
   # Every 100 files processed
   if self.files_processed % 100 == 0:
       pending_extraction = self.queue_manager.get_extraction_queue_size()
       logger.info(f"Extraction complete count: {self.files_processed}, "
                  f"Pending extraction: {pending_extraction}")
   ```

**Estimated Impact:** ✅ Accurate extraction metrics  
**Risk Level:** VERY LOW - Just ensures proper function calls  
**Estimated Time:** 30 minutes

---

### **Fix #5: Fix Batch Accumulation Timeout**
**Current Issue:** Documents accumulate in memory forever  
**Fix Location:** `src/indexing/opensearch_client.py` lines 412-445  

#### **Approach:**

```python
# In opensearch_client.py

class BatchAccumulator:
    def __init__(self, batch_size, batch_timeout):
        self.pending_batch = []
        self.batch_size = batch_size
        self.batch_timeout = batch_timeout
        self.batch_start_time = time.time()  # IMPORTANT: Initialize
    
    def add_item(self, item):
        """Add item to batch, return batch if ready to send"""
        self.pending_batch.append(item)
        
        # Check if batch is ready
        current_time = time.time()
        batch_age = current_time - self.batch_start_time
        
        if len(self.pending_batch) >= self.batch_size:
            # Batch full - send it
            return self._flush_batch()
        elif batch_age >= self.batch_timeout:
            # Batch timed out - send it even if not full
            return self._flush_batch()
        else:
            return None  # Not ready yet
    
    def _flush_batch(self):
        """Flush and reset batch"""
        batch = self.pending_batch
        self.pending_batch = []
        self.batch_start_time = time.time()  # CRITICAL: Reset timer
        return batch if batch else None
    
    def force_flush(self):
        """Force send current batch regardless of size/time"""
        return self._flush_batch()
```

**Usage:**
```python
# In indexing_worker.py

accumulator = BatchAccumulator(batch_size=1000, batch_timeout=5.0)

for work_item in claimed_items:
    batch_ready = accumulator.add_item(work_item)
    
    if batch_ready:
        result = self.os_client.bulk_index(batch_ready)
        self.batches_sent += 1

# On shutdown or timeout
remaining = accumulator.force_flush()
if remaining:
    result = self.os_client.bulk_index(remaining)
```

**Estimated Impact:** ✅ Continuous document flow, no accumulation  
**Risk Level:** VERY LOW - Standard batch pattern  
**Estimated Time:** 1 hour

---

### **Fix #6: Optimize Extraction Queue Priority**
**Current Issue:** Queue uses ZPOPMIN when should use priority correctly  
**Fix Location:** `src/core/redis_queue_manager.py` line 263  

#### **Approach:**

```python
# Current (BROKEN):
def claim_extraction_work(self, size_category, worker_id, batch_size=1):
    items = self.client.zpopmin(queue_key, batch_size)  # Gets LOWEST priority

# Fixed:
def claim_extraction_work(self, size_category, worker_id, batch_size=1):
    items = self.client.zpopmax(queue_key, batch_size)  # Gets HIGHEST priority
```

**Why:** Priority values: 1 (highest) to 10 (lowest)
- ZPOPMIN returns score 1 (correct - highest priority)
- ZPOPMAX returns score 10 (wrong - lowest priority)
- Current code is accidentally correct? Verify actual usage.

**Action:** Review actual priority scheme and adjust if needed.

**Estimated Impact:** ✅ Better request prioritization (minor impact)  
**Risk Level:** LOW - Just changes sort order  
**Estimated Time:** 30 minutes

---

### **Fix #7: Implement OCR→OpenSearch Update**
**Current Issue:** OCR text extracted but never applied to document  
**Fix Location:** `src/ocr/ocr_worker.py` lines 310-340  

#### **Approach:**

1. **Implement OCR content merge:**
   ```python
   # In ocr_worker.py
   
   def _process_file(self, work_item):
       file_id = work_item['file_id']
       file_path = work_item['file_path']
       
       # Extract OCR text
       ocr_text = self.tesseract.extract_text(file_path)
       confidence = self.tesseract.get_confidence(ocr_text)
       
       # Update OpenSearch document with OCR content
       self._update_document_ocr(file_id, ocr_text, confidence)
       
       # Mark complete
       self.queue_manager.complete_ocr(queue_id, confidence, processing_time_ms)
   
   def _update_document_ocr(self, file_id, ocr_text, confidence):
       """Update document in OpenSearch with OCR text"""
       try:
           # Use UPDATE API to add OCR content to existing document
           update_body = {
               "doc": {
                   "ocr_content": ocr_text,
                   "ocr_confidence": confidence,
                   "ocr_timestamp": datetime.now().isoformat()
               },
               "doc_as_upsert": True  # Create if doesn't exist
           }
           
           self.os_client.client.update(
               index=self.os_client.index_name,
               id=file_id,
               body=update_body,
               retry_on_conflict=3
           )
           
           logger.info(f"Updated document {file_id} with OCR text ({len(ocr_text)} chars, "
                      f"{confidence:.0f}% confidence)")
           
       except Exception as e:
           logger.error(f"Failed to update document with OCR: {e}")
           # Still mark as complete, even if update failed
   ```

2. **Add verification:**
   ```python
   # After OCR processing, verify update succeeded
   retrieved_doc = self.os_client.client.get(index=..., id=file_id)
   if 'ocr_content' in retrieved_doc['_source']:
       logger.debug(f"OCR content verified in index")
   else:
       logger.warning(f"OCR content NOT in index for file {file_id}")
   ```

**Estimated Impact:** ✅ OCR text appears in search results  
**Risk Level:** LOW - Adds new field to document  
**Estimated Time:** 2 hours

---

### **Fix #8: Implement OCR Confidence Thresholds**
**Current Issue:** Low-quality OCR indexed without filtering  
**Fix Location:** `src/ocr/tesseract_wrapper.py` lines 165-195  

#### **Approach:**

```python
# In tesseract_wrapper.py

from core.constants import OCR_MIN_CONFIDENCE, OCR_GOOD_CONFIDENCE

def extract_text(self, image_path):
    """Extract text with confidence filtering"""
    
    # Preprocess image
    processed = self.preprocess_image(image_path)
    
    # Extract with Tesseract
    result = pytesseract.image_to_data(processed, output_type=Output.DICT)
    text = pytesseract.image_to_string(processed)
    
    # Calculate confidence
    confidence = self.calculate_weighted_confidence(result)
    
    # Filter by confidence threshold
    if confidence < OCR_MIN_CONFIDENCE:
        logger.warning(f"OCR text rejected: confidence {confidence:.0f}% < minimum {OCR_MIN_CONFIDENCE}%")
        return None, 0  # Return None + confidence 0
    
    # Quality tier
    if confidence >= OCR_EXCELLENT_CONFIDENCE:  # >= 90%
        quality = "excellent"
    elif confidence >= OCR_GOOD_CONFIDENCE:  # >= 70%
        quality = "good"
    else:
        quality = "acceptable"  # 25-70%
    
    logger.info(f"OCR extracted {len(text)} chars at {confidence:.0f}% confidence ({quality})")
    
    return text, confidence

def calculate_weighted_confidence(self, tesseract_result):
    """Calculate confidence weighted by character count"""
    confidence_scores = tesseract_result['conf']
    word_lengths = tesseract_result['width']  # Approximate
    
    valid_scores = []
    total_weight = 0
    
    for conf_str, length in zip(confidence_scores, word_lengths):
        try:
            conf = int(conf_str)
            if conf >= 0:  # Valid confidence (Tesseract uses -1 for spaces)
                weight = length  # Weight by width
                valid_scores.append((conf, weight))
                total_weight += weight
        except ValueError:
            pass
    
    if not valid_scores or total_weight == 0:
        return 0
    
    # Weighted average
    weighted_sum = sum(conf * weight for conf, weight in valid_scores)
    weighted_avg = weighted_sum / total_weight
    
    return weighted_avg
```

**Estimated Impact:** ✅ Only high-quality OCR indexed  
**Risk Level:** LOW - Just adds filtering, no data loss  
**Estimated Time:** 1.5 hours

---

## PHASE 3: MEDIUM SEVERITY FIXES (Data Quality)

### **Goal:** Improve search accuracy and dashboard metrics

---

### **Fix #9: Add Numeric Field Search Support**
**Current Issue:** Financial numbers split incorrectly  
**Fix Location:** `src/indexing/opensearch_client.py` lines 62-90  

#### **Approach:**

```python
# Add custom analyzer for numeric fields

custom_analyzer = {
    "settings": {
        "analysis": {
            "analyzer": {
                "standard": {
                    "type": "standard"
                },
                "numeric_analyzer": {
                    "type": "custom",
                    "tokenizer": "numeric_tokenizer"
                }
            },
            "tokenizer": {
                "numeric_tokenizer": {
                    "type": "pattern",
                    "pattern": "[^0-9]+"  # Split on non-digits
                }
            }
        }
    },
    "mappings": {
        "properties": {
            # Numeric fields
            "invoice_number": {
                "type": "text",
                "analyzer": "numeric_analyzer",
                "fields": {
                    "keyword": {"type": "keyword"}
                }
            },
            "amount": {
                "type": "text",
                "analyzer": "numeric_analyzer"
            },
            # Standard text fields
            "main_content": {
                "type": "text",
                "analyzer": "standard"
            }
        }
    }
}
```

**Usage:**
```python
# When indexing document
document = {
    "invoice_number": "1234567",  # Indexed with numeric_analyzer
    "amount": "1,234,567.89",      # Commas preserved in search
    "main_content": "..."
}
```

**Estimated Impact:** ✅ Number searches work correctly  
**Risk Level:** MEDIUM - Requires index recreation  
**Estimated Time:** 2 hours

---

### **Fix #10: Implement Dashboard Metric Caching Improvements**
**Current Issue:** Stale metrics during high-speed processing  
**Fix Location:** `src/ui/dashboard.py` lines 168-195  

#### **Approach:**

```python
# Add per-metric cache timing

cache_ttls = {
    'queue_stats': 2,      # 2 seconds (volatile)
    'size_stats': 3,       # 3 seconds (volatile)
    'failed_files': 10,    # 10 seconds (stable)
    'ocr_pending': 10,     # 10 seconds (stable)
    'completed_files': 15  # 15 seconds (stable)
}

@st.cache_data(ttl=2)  # Shorter cache during active processing
def get_cached_queue_stats():
    qm = get_queue_manager()
    stats = qm.get_queue_statistics()
    
    # Annotate with timestamp
    stats['cached_at'] = datetime.now().isoformat()
    stats['cache_age_seconds'] = 0
    
    return stats

# Display cache age in UI
if 'cached_at' in stats:
    import streamlit as st
    col1, col2 = st.columns([4, 1])
    with col1:
        st.metric("Queue Status", format_number(total_items))
    with col2:
        cache_age = (datetime.now() - datetime.fromisoformat(stats['cached_at'])).total_seconds()
        st.caption(f"Updated {cache_age:.1f}s ago")
```

**Estimated Impact:** ✅ Faster metric refresh, user aware of staleness  
**Risk Level:** VERY LOW - Just display improvement  
**Estimated Time:** 1 hour

---

### **Fix #11: Add Content Truncation Warning**
**Current Issue:** Large files silently truncated  
**Fix Location:** `src/extraction/content_extractor.py` lines 278-295  

#### **Approach:**

```python
# In content_extractor.py

MAX_TEXT_LENGTH = 499640  # 500KB limit
TRUNCATION_WARNING_THRESHOLD = 0.8 * MAX_TEXT_LENGTH  # Warn at 80%

def process_tika_response(self, tika_response):
    main_content = tika_response.get('X-TIKA:content', '')
    original_length = len(main_content)
    
    if original_length > MAX_TEXT_LENGTH:
        # Document will be truncated
        logger.warning(f"Document truncated: {original_length} chars → {MAX_TEXT_LENGTH} chars")
        
        # Store truncation metadata
        truncation_info = {
            'original_length': original_length,
            'truncated_to': MAX_TEXT_LENGTH,
            'truncation_percent': (1 - MAX_TEXT_LENGTH / original_length) * 100
        }
        
        main_content = main_content[:MAX_TEXT_LENGTH]
        
        return {
            'content': main_content,
            'truncated': True,
            'truncation_info': truncation_info
        }
    elif original_length > TRUNCATION_WARNING_THRESHOLD:
        logger.debug(f"Document approaching truncation limit: {original_length} chars")
        
        return {
            'content': main_content,
            'truncated': False,
            'approaching_truncation': True
        }
    else:
        return {
            'content': main_content,
            'truncated': False,
            'approaching_truncation': False
        }

# In indexing, include truncation metadata
document = {
    'main_content': content['content'],
    'truncated': content.get('truncated', False),
    'truncation_info': content.get('truncation_info'),
    ...
}
```

**Dashboard display:**
```python
if stats.get('truncated'):
    st.warning(f"⚠️ Document truncated: "
              f"{stats['truncation_info']['original_length']:,} → "
              f"{stats['truncation_info']['truncated_to']:,} chars "
              f"({stats['truncation_info']['truncation_percent']:.1f}% lost)")
```

**Estimated Impact:** ✅ Users aware of truncation  
**Risk Level:** VERY LOW - Just visibility  
**Estimated Time:** 1.5 hours

---

## PHASE 4: LOW SEVERITY FIXES (Maintenance)

### **Goal:** Improve code quality, logging, and maintainability

---

### **Fix #12-27: Low Priority Issues**

| #  | Issue | Fix | Time |
|----|-------|-----|------|
| 12 | Unused imports | Code cleanup pass | 1h |
| 13 | Dead code | Remove unreachable branches | 1h |
| 14 | Incomplete docstrings | Add documentation | 2h |
| 15 | Hard-coded constants | Move to constants.py | 1h |
| 16 | No graceful shutdown | Add signal handling | 1.5h |
| 17 | Circular imports | Refactor module structure | 2h |
| 18 | No rate limiting | Add token bucket | 1.5h |
| 19 | No circuit breaker | Add exponential backoff | 1.5h |
| 20 | Mixed output streams | Structured logging | 2h |
| 21 | No distributed tracing | Add request IDs | 2h |
| 22 | No health endpoints | Add /health endpoint | 1.5h |
| 23 | No Prometheus metrics | Export metrics | 2h |
| 24 | Config not validated | Add validation function | 1h |
| 25 | Error logging generic | Add context to errors | 1.5h |
| 26 | No unit tests | Create test suite | 4h |
| 27 | Dashboard UX issues | Improve UI layout | 2h |

**Total Phase 4:** ~27 hours

---

## IMPLEMENTATION ROADMAP

### **Week 1: Critical Fixes**
- Monday: Fix #1 (Queue sync) + Fix #3 (SQLite WAL)
- Tuesday: Fix #2 (Respawn loop) + Testing
- Wednesday: Testing + Fix #4 (Extraction status)

### **Week 2: High-Severity Fixes**
- Monday: Fix #5 (Batch timeout) + Fix #6 (Priority)
- Tuesday: Fix #7 (OCR update) + Fix #8 (Confidence)
- Wednesday-Friday: Testing + Integration

### **Week 3: Medium + Low**
- Distributed across team
- Prioritize #9 (Numeric search) first
- Then #10-15 (Quick wins)

---

## TESTING STRATEGY

### **Post-Fix Testing**

**After Fix #1-3 (Must complete before others):**
```
1. Start system fresh
2. Verify extraction queue has files (from SQLite sync)
3. Verify extraction workers start without crashes
4. Verify workers respawn if killed
5. Monitor for "database is locked" errors (should be zero)
```

**After Fix #4-8:**
```
1. Run 100 files through extraction→indexing→OCR
2. Verify extraction status updated
3. Verify batch timeout triggers
4. Verify OCR content in index
5. Verify low confidence OCR rejected
```

**After Fix #9-11:**
```
1. Search for "$1,234,567" - should find results
2. Search for "2013" range - should find results
3. Dashboard should show truncation warnings
4. Metrics should not be stale
```

### **Performance Benchmarks**

| Metric | Before Fix | Target After Fix |
|--------|-----------|-----------------|
| Extraction throughput | 0-3 files/sec | 200+ files/sec |
| Indexing throughput | < 50 docs/sec | 1000+ docs/sec |
| OCR pipeline | Stuck | Processing files |
| Queue starvation | 13,559 files | 0 files |
| Worker crashes | Frequent | < 1/hour |
| Worker respawns | 0 | Automatic |

---

## DEPENDENCIES & ORDERING

```
Fix #1 (Queue sync)
    ├─→ Fix #2 (Respawn) [Independent]
    ├─→ Fix #3 (SQLite) [Independent]
    ├─→ Fix #4 (Extraction status) [Depends on #1]
    ├─→ Fix #5 (Batch timeout) [Depends on #1]
    ├─→ Fix #6 (Priority) [Depends on #1]
    ├─→ Fix #7 (OCR update) [Depends on #1]
    └─→ Fix #8 (Confidence) [Depends on #7]

Fix #9 (Numeric search) [Independent, requires index recreation]
Fix #10 (Caching) [Independent]
Fix #11 (Truncation) [Independent]
Fix #12-27 (Maintenance) [All independent]
```

---

## RISK MITIGATION

| Phase | Risk | Mitigation |
|-------|------|-----------|
| 1 | Data loss during sync | Validate file counts before/after |
| 1 | Worker crashes increase | Have respawn loop ready before deploying |
| 2 | OCR overwrites data | Use upsert with retry_on_conflict |
| 3 | Index recreation breaks queries | Create new index, swap alias |
| 4 | Circular import breaks system | Test with import-check script |

---

## SUCCESS CRITERIA

- ✅ All 27 issues documented and tracked
- ✅ Phase 1 complete: Extraction processing 200+/sec
- ✅ Phase 2 complete: Indexing 1000+/sec, OCR working
- ✅ Phase 3 complete: Search accurate, metrics correct
- ✅ Phase 4 complete: Code quality improved
- ✅ Zero worker crashes in 24-hour test run
- ✅ Dashboard metrics align with system state
- ✅ Production deployment approved

---

## NEXT STEPS

1. ✅ Review this comprehensive audit (you are here)
2. ⏳ Approve fix plan and prioritization
3. ⏳ Create JIRA tickets for each issue
4. ⏳ Assign team members by expertise
5. ⏳ Begin Phase 1 implementation
6. ⏳ Run post-fix validation tests
7. ⏳ Deploy to production

---

**Prepared:** February 4, 2026  
**Status:** Ready for implementation approval  
**Contact:** DevOps/Platform Team
