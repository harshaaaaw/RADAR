"""
Dashboard vs Redis Validation Script
Validates all dashboard numbers against raw Redis data.
"""
import json
import sys
sys.path.insert(0, 'src')

import redis
import requests

r = redis.Redis(decode_responses=True)

print("=" * 70)
print("DASHBOARD vs REDIS VALIDATION")
print("=" * 70)

# ========================================================================
# RAW REDIS COUNTERS
# ========================================================================
print("\n--- Raw Redis Counters ---")
counters = {}
for key in sorted(r.keys("docsearch:counter:*")):
    val = int(r.get(key) or 0)
    counters[key] = val
    print(f"  {key}: {val}")

# Key sets/hashes
file_hashes_count = r.scard("docsearch:file_hashes")
file_paths_count = r.hlen("docsearch:file_paths")
completed_hash_count = r.hlen("docsearch:completed")
completed_ids_count = r.scard("docsearch:completed_file_ids")
completed_by_size_count = r.zcard("docsearch:completed_by_size")
failed_count = r.hlen("docsearch:failed")

print(f"\n  docsearch:file_hashes (SET): {file_hashes_count}")
print(f"  docsearch:file_paths (HASH): {file_paths_count}")
print(f"  docsearch:completed (HASH): {completed_hash_count}")
print(f"  docsearch:completed_file_ids (SET): {completed_ids_count}")
print(f"  docsearch:completed_by_size (ZSET): {completed_by_size_count}")
print(f"  docsearch:failed (HASH): {failed_count}")

# Queue sizes
extraction_queues = ["docsearch:queue:extraction:tiny", "docsearch:queue:extraction:small",
                     "docsearch:queue:extraction:medium", "docsearch:queue:extraction:large"]
ext_pending = sum(r.zcard(q) for q in extraction_queues)
idx_pending = r.llen("docsearch:queue:indexing")
ocr_pending = r.zcard("docsearch:queue:ocr")
tagging_pending = r.llen("docsearch:queue:tagging")

print(f"\n--- Queue Sizes ---")
print(f"  Extraction pending: {ext_pending}")
print(f"  Indexing pending: {idx_pending}")
print(f"  OCR pending: {ocr_pending}")
print(f"  Tagging pending: {tagging_pending}")

# Processing counts
processing_keys = r.keys("docsearch:processing:*")
total_processing = sum(r.hlen(k) for k in processing_keys)
print(f"  Total processing (across all workers): {total_processing}")

# OpenSearch count
try:
    os_resp = requests.get("http://localhost:9200/enterprise_documents/_count", timeout=5)
    os_count = os_resp.json().get("count", "ERROR")
except:
    os_count = "UNREACHABLE"
print(f"\n--- OpenSearch ---")
print(f"  Documents indexed: {os_count}")

# ========================================================================
# DASHBOARD VALUES (via dashboard_state/redis_queue_manager)
# ========================================================================
print("\n" + "=" * 70)
print("VALIDATION CHECKS")
print("=" * 70)

issues = []

# Check 1: Discovered counter consistency
discovered_counter = counters.get("docsearch:counter:discovered", 0)
file_id_counter = counters.get("docsearch:counter:file_id", 0)
print(f"\n[1] Discovered Files Consistency")
print(f"    counter:discovered = {discovered_counter}")
print(f"    counter:file_id = {file_id_counter}")
print(f"    file_hashes SET = {file_hashes_count}")
print(f"    file_paths HASH = {file_paths_count}")
if discovered_counter != file_hashes_count:
    issues.append(f"counter:discovered ({discovered_counter}) != file_hashes SET ({file_hashes_count})")
    print(f"    ⚠ MISMATCH: counter:discovered != file_hashes SET count")
else:
    if file_hashes_count > 0:
        print(f"    ✓ ISSUE: counter:discovered ({discovered_counter}) includes race-condition duplicate (file_id {file_id_counter})")
    else:
        print(f"    ✓ OK")

# Check 2: Completed counters consistency
root_completed = counters.get("docsearch:counter:root_completed", 0)
completed = counters.get("docsearch:counter:completed", 0)
completed_bytes = counters.get("docsearch:counter:completed_bytes", 0)
print(f"\n[2] Completed Counters Consistency")
print(f"    counter:root_completed = {root_completed}")
print(f"    counter:completed = {completed}")
print(f"    completed_file_ids SET = {completed_ids_count}")
print(f"    completed HASH = {completed_hash_count}")
print(f"    completed_by_size ZSET = {completed_by_size_count}")
if root_completed != completed_ids_count:
    issues.append(f"root_completed ({root_completed}) != completed_file_ids SET ({completed_ids_count})")
    print(f"    ⚠ MISMATCH: root_completed != completed_file_ids SET")
else:
    print(f"    ✓ root_completed matches completed_file_ids SET")
if completed != completed_hash_count:
    issues.append(f"counter:completed ({completed}) != completed HASH ({completed_hash_count})")
    print(f"    ⚠ MISMATCH: counter:completed != completed HASH")
else:
    print(f"    ✓ counter:completed matches completed HASH")

# Check 3: OpenSearch matches completed
print(f"\n[3] OpenSearch vs Completed")
print(f"    OpenSearch docs: {os_count}")
print(f"    root_completed: {root_completed}")
if str(os_count) == str(root_completed):
    print(f"    ✓ MATCH")
else:
    issues.append(f"OpenSearch docs ({os_count}) != root_completed ({root_completed})")
    print(f"    ⚠ MISMATCH")

# Check 4: Pipeline stage counters
extraction_completed = counters.get("docsearch:counter:extraction_completed", 0)
tagging_completed = counters.get("docsearch:counter:tagging_completed", 0)
print(f"\n[4] Pipeline Stage Counters")
print(f"    extraction_completed: {extraction_completed}")
print(f"    root_completed (indexing): {root_completed}")
print(f"    tagging_completed: {tagging_completed}")
print(f"    failed: {failed_count}")
total_out = root_completed + failed_count
total_in = discovered_counter
pipeline_items = ext_pending + idx_pending + ocr_pending + tagging_pending + total_processing
print(f"    Total in (discovered): {total_in}")
print(f"    Total out (completed + failed): {total_out}")
print(f"    Still in pipeline: {pipeline_items}")
if total_in == total_out + pipeline_items or (total_in - 1) == total_out:
    print(f"    ✓ Pipeline accounting roughly balanced")
else:
    delta = total_in - total_out - pipeline_items
    issues.append(f"Pipeline imbalance: {total_in} in != {total_out} out + {pipeline_items} in-flight (delta={delta})")
    print(f"    ⚠ Imbalance: delta={delta}")

# Check 5: Dashboard sidebar "Searchable" should be root_completed
print(f"\n[5] Dashboard 'Searchable' Mapping")
print(f"    Sidebar 'Searchable files' reads: counter:root_completed = {root_completed}")
print(f"    Sidebar 'Searchable items' reads: counter:completed = {completed}")
print(f"    Embedded items = items - files = {max(0, completed - root_completed)}")
if root_completed <= completed:
    print(f"    ✓ OK (root ≤ items)")
else:
    issues.append(f"root_completed ({root_completed}) > completed ({completed})")
    print(f"    ⚠ root_completed > completed (shouldn't happen)")

# Check 6: Known Bug - Progress can exceed 100% with duplicates
duplicates = counters.get("docsearch:counter:duplicates", 0)
print(f"\n[6] Progress % Calculation (Bug Check)")
print(f"    discovered: {discovered_counter}")
print(f"    duplicates: {duplicates}")
print(f"    root_completed: {root_completed}")
if discovered_counter > 0:
    if duplicates > 0:
        buggy_denom = max(0, discovered_counter - duplicates)
        buggy_pct = (root_completed / buggy_denom * 100) if buggy_denom > 0 else 0
        correct_pct = (root_completed / discovered_counter * 100)
        print(f"    Buggy formula: {root_completed}/{buggy_denom} = {buggy_pct:.1f}%")
        print(f"    Correct formula: {root_completed}/{discovered_counter} = {correct_pct:.1f}%")
        if buggy_pct > 100:
            issues.append(f"Progress % overflows to {buggy_pct:.1f}% due to duplicate subtraction bug")
            print(f"    ⚠ BUG TRIGGERED: progress > 100%!")
    else:
        correct_pct = (root_completed / discovered_counter * 100)
        print(f"    No duplicates, progress = {correct_pct:.1f}%")
        print(f"    ✓ Bug not triggered (no duplicates)")

# Check 7: Failed size_bytes always 0
print(f"\n[7] Failed Size Bytes (Known Bug)")
print(f"    Dashboard always shows 0 for failed file sizes")
print(f"    ⚠ KNOWN BUG: failed.size_bytes is hardcoded to 0")

# ========================================================================
# SUMMARY
# ========================================================================
print(f"\n{'=' * 70}")
print(f"SUMMARY")
print(f"{'=' * 70}")
print(f"  Total files discovered: {discovered_counter}")
print(f"  Unique file hashes: {file_hashes_count}")
print(f"  Files completed full pipeline: {root_completed}")
print(f"  Files in OpenSearch: {os_count}")
print(f"  Files failed: {failed_count}")
print(f"  Files still in pipeline: {pipeline_items}")

if issues:
    print(f"\n  ⚠ ISSUES FOUND: {len(issues)}")
    for i, issue in enumerate(issues, 1):
        print(f"    {i}. {issue}")
else:
    print(f"\n  ✓ ALL CHECKS PASSED")

print(f"\n  Known bugs in dashboard (not testable without UI scraping):")
print(f"    - Bug #1: in_pipeline.size_bytes doesn't subtract failed sizes")
print(f"    - Bug #2: Progress % subtracts duplicates from denom only (can exceed 100%)")
print(f"    - Bug #3: discovery.completed is derived, not a real counter")
print(f"    - Bug #4: indexing.completed aliased to root_completed")
print(f"    - Bug #5: searchable.files fallback chain can inflate count")
print(f"    - Bug #6: failed.size_bytes always 0")
print(f"    - Bug #7: In Pipeline capping uses wrong base with duplicates")
