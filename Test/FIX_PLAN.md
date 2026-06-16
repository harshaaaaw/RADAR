# COMPREHENSIVE FIX PLAN - DocumentSearch System Issues

## Executive Summary
Found 5 critical issues that need immediate fixing:
1. ✅ OpenSearch index NOT CREATED - No documents being stored (CRITICAL)
2. ✅ Reset command doesn't reset Redis - Only resets SQLite
3. ✅ Dashboard always auto-refreshing - Causes freezing
4. ✅ Search inaccurate for numeric values - Tokenization issue
5. ✅ OCR logs path incorrect

---

## Issue #1: OpenSearch Index Not Created (CRITICAL - ROOT CAUSE)
**Impact**: No documents are being indexed despite showing stats
**Root Cause**: Index creation logic missing or failing

### Files Affected:
- `src/indexing/opensearch_client.py` - Index creation
- `src/indexing/indexing_worker.py` - Index validation

### Fix Plan:
1. Check if OpenSearch client creates index on initialization
2. Add automatic index creation with proper mappings
3. Add index existence validation before indexing
4. Add retry logic for index creation

---

## Issue #2: Reset Command Doesn't Handle Redis
**Impact**: Stats persist after reset when using Redis

### Files Affected:
- `src/main.py` - reset() command (line 431-617)

### Current Code:
```python
# Only deletes SQLite database files
queue_dir = working_root / "queue"
for db_file in ["queues.db", "queues.db-wal", "queues.db-shm"]:
```

### Fix Plan:
1. Detect if Redis is being used (check config or connection)
2. If Redis: Call `redis_queue_manager.reset_database()`
3. If SQLite: Keep current file deletion
4. Reset both bloom filter and queue manager singleton

---

## Issue #3: Dashboard Always Auto-Refreshing
**Impact**: Dashboard freezes/stuck, high CPU usage

### Files Affected:
- `src/ui/dashboard.py` - render_monitoring_tab() (line ~1500)

### Current Code:
```python
# Auto-refresh logic
if auto_refresh:
    time.sleep(refresh_interval)
    st.rerun()
```

### Problem:
- This ALWAYS runs even when checkbox is False
- Causes infinite loop
- No way to stop refresh

### Fix Plan:
1. Move auto-refresh to END of function
2. Check auto_refresh BEFORE sleep
3. Return early if auto_refresh is False
4. Use st.session_state to prevent multiple reruns

---

## Issue #4: Search Inaccurate for Numeric Values
**Impact**: Searching "2,480,821.04" returns docs with "2", "480", etc.

### Files Affected:
- `src/api/query_builder.py` - Query construction
- `src/indexing/opensearch_client.py` - Index mappings

### Root Cause:
- Standard analyzer tokenizes "2,480,821.04" into ["2", "480", "821", "04"]
- Need keyword field for exact numeric matching

### Fix Plan:
1. Add `.keyword` subfield to content fields in mapping
2. For numeric/exact queries, search both:
   - Standard field (tokenized)
   - .keyword field (exact match) with high boost
3. Detect numeric patterns: /^\d[\d,\.]*$/
4. Use phrase query for comma-separated numbers

---

## Issue #5: OCR Logs Path Incorrect
**Impact**: Can't diagnose OCR errors

### Files Affected:
- OCR worker logging configuration

### Current: `D:\DocumentSearch\logs\ocr.worker.log`
### Actual: Likely `D:\DocumentSearch\logs\ocr\worker.log`

### Fix Plan:
1. Check logging_manager.py for log directory structure
2. Update log path references
3. Verify OCR errors in actual log location

---

## EXECUTION ORDER (Critical Path):

### Phase 1: OpenSearch Index Creation (CRITICAL - DO FIRST)
**Priority**: P0 - Nothing works without this
1. Read `opensearch_client.py` - Check index creation
2. Add index creation with proper mappings
3. Test index creation manually
4. Verify documents can be indexed

### Phase 2: Reset Command Fix
**Priority**: P1 - Needed for testing
1. Update `main.py reset()` to detect queue manager type
2. Add Redis reset logic
3. Test reset with both Redis and SQLite

### Phase 3: Dashboard Refresh Fix
**Priority**: P1 - UI unusable
1. Fix auto-refresh conditional logic
2. Test on/off toggle
3. Verify no infinite loops

### Phase 4: Search Accuracy Fix
**Priority**: P2 - Core functionality
1. Update index mapping with .keyword fields
2. Update query builder for numeric detection
3. Test with "2,480,821.04" query
4. Verify exact matches work

### Phase 5: OCR Logs Investigation
**Priority**: P3 - Monitoring
1. Find correct OCR log path
2. Check for actual OCR errors
3. Fix any found issues

---

## TESTING CHECKLIST:

### After Phase 1 (Index Creation):
- [ ] OpenSearch index exists
- [ ] Documents can be indexed
- [ ] Index count matches stats
- [ ] Mappings are correct

### After Phase 2 (Reset):
- [ ] `python src/main.py reset --force` completes
- [ ] Stats show 0 after reset
- [ ] Dashboard shows 0 after reset
- [ ] Redis keys are cleared (if using Redis)

### After Phase 3 (Dashboard):
- [ ] Auto-refresh toggle OFF stops refresh
- [ ] Dashboard doesn't freeze
- [ ] Stats display correctly
- [ ] Toggle ON resumes refresh

### After Phase 4 (Search):
- [ ] Search "2,480,821.04" returns exact doc
- [ ] Search doesn't return partial digit matches
- [ ] Search "contract" still works normally
- [ ] Phrase search "loan agreement" works

### After Phase 5 (OCR):
- [ ] OCR logs are accessible
- [ ] No critical OCR errors
- [ ] OCR confidence scores visible

---

## ESTIMATED TIME:
- Phase 1: 30-45 minutes (critical)
- Phase 2: 15-20 minutes  
- Phase 3: 10-15 minutes
- Phase 4: 30-40 minutes
- Phase 5: 10-15 minutes
**Total: ~2 hours**

---

## ROLLBACK PLAN:
- Git commit before each phase
- Keep backup of modified files
- Document all changes in comments

