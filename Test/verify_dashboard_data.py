"""Quick test to verify dashboard data pipeline works end-to-end."""
import sys
sys.path.insert(0, 'src')
from core.queue_manager import get_queue_manager

qm = get_queue_manager()
qs = qm.get_queue_statistics()

print("=== get_queue_statistics() top-level keys:", list(qs.keys()))

# Simulate extract_summary exactly as dashboard does
discovery = qs.get('discovery', {}) or {}
extraction_total_stats = qs.get('extraction_total', {}) or {}
indexing = qs.get('indexing', {}) or {}
ocr = qs.get('ocr', {}) or {}
completed = qs.get('completed', {}) or {}

def safe_int(val):
    if val is None:
        return 0
    try:
        return int(val)
    except:
        return 0

metrics = {
    "discovered_total": safe_int(discovery.get("total")),
    "discovery_pending": safe_int(discovery.get("pending")),
    "discovery_completed": safe_int(discovery.get("completed")),
    "extraction_pending": safe_int(extraction_total_stats.get("pending")),
    "extraction_processing": safe_int(extraction_total_stats.get("processing")),
    "extraction_completed": safe_int(extraction_total_stats.get("completed")),
    "indexing_pending": safe_int(indexing.get("pending")),
    "indexing_processing": safe_int(indexing.get("processing")),
    "indexing_completed": safe_int(indexing.get("completed")),
    "ocr_pending": safe_int(ocr.get("pending")),
    "ocr_processing": safe_int(ocr.get("processing")),
    "ocr_completed": safe_int(ocr.get("completed")),
    "completed_total": safe_int(completed.get("total_completed") or completed.get("total")),
    "total_failures": safe_int(qs.get("total_failures")),
}

print("\n=== Summary metrics (what Pipeline Status should show):")
for k, v in metrics.items():
    status = "OK" if v > 0 else "ZERO"
    print(f"  {k}: {v:>10,}  [{status}]")

# Check critical non-zero metrics
critical = ["extraction_pending", "discovered_total", "completed_total"]
all_ok = all(metrics[k] > 0 for k in critical)
print(f"\n=== CRITICAL CHECK: {'PASS - real data available' if all_ok else 'FAIL - some metrics are zero!'}")
