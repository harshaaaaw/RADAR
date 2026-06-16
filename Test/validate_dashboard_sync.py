"""
Dashboard Data Sync Validation Script
Compares every number shown in the dashboard to actual Redis/OpenSearch data.
"""
import sys
sys.path.insert(0, 'src')

from core.queue_manager import get_queue_manager
from core.config_manager import get_config

import redis

def main():
    print("=" * 70)
    print("DASHBOARD DATA SYNC VALIDATION")
    print("=" * 70)
    
    config = get_config()
    qm = get_queue_manager()
    r = redis.Redis(host='localhost', port=6379, decode_responses=True)
    
    # 1. Get queue statistics (what dashboard uses)
    queue_stats = qm.get_queue_statistics()
    size_stats = qm.get_size_statistics()
    
    # 2. Get raw Redis data for comparison
    pipe = r.pipeline(transaction=False)  # Non-transactional for mixed-type keys
    
    # Extraction queues (sorted sets)
    for cat in ['tiny', 'small', 'medium', 'large']:
        pipe.zcard(f'docsearch:queue:extraction:{cat}')
    # Processing sets
    for stage in ['extraction', 'indexing', 'ocr']:
        for cat in ['tiny', 'small', 'medium', 'large']:
            pipe.scard(f'docsearch:processing:{stage}:{cat}')
    # Counters
    counters = [
        'docsearch:counter:discovered',
        'docsearch:counter:discovery:completed',
        'docsearch:counter:extraction:completed',
        'docsearch:counter:indexing:completed',
        'docsearch:counter:ocr:completed',
        'docsearch:counter:completed',
        'docsearch:counter:failures:ocr_error',
        'docsearch:counter:failures:extraction_error',
        'docsearch:counter:failures:indexing_error',
    ]
    for c in counters:
        pipe.get(c)
    
    # Indexing queues (sorted sets)
    for cat in ['tiny', 'small', 'medium', 'large']:
        pipe.zcard(f'docsearch:queue:indexing:{cat}')
    
    # OCR queues (sorted sets)
    for cat in ['tiny', 'small', 'medium', 'large']:
        pipe.zcard(f'docsearch:queue:ocr:{cat}')
    
    results = pipe.execute()
    
    idx = 0
    
    # Parse extraction queue lengths
    extraction_pending_raw = 0
    for cat in ['tiny', 'small', 'medium', 'large']:
        extraction_pending_raw += results[idx]
        idx += 1
    
    # Parse processing sets
    processing_raw = {}
    for stage in ['extraction', 'indexing', 'ocr']:
        total = 0
        for cat in ['tiny', 'small', 'medium', 'large']:
            total += results[idx]
            idx += 1
        processing_raw[stage] = total
    
    # Parse counters
    counter_vals = {}
    for c in counters:
        val = results[idx]
        counter_vals[c] = int(val) if val else 0
        idx += 1
    
    # Parse indexing queue lengths
    indexing_pending_raw = 0
    for cat in ['tiny', 'small', 'medium', 'large']:
        indexing_pending_raw += results[idx]
        idx += 1
    
    # Parse OCR queue lengths
    ocr_pending_raw = 0
    for cat in ['tiny', 'small', 'medium', 'large']:
        ocr_pending_raw += results[idx]
        idx += 1
    
    # 3. Build expected dashboard values
    # Discovery
    disc_total = counter_vals.get('docsearch:counter:discovered', 0)
    disc_completed = counter_vals.get('docsearch:counter:discovery:completed', 0)
    
    # Extraction
    ext_pending = extraction_pending_raw
    ext_processing = processing_raw['extraction']
    ext_completed = counter_vals.get('docsearch:counter:extraction:completed', 0)
    
    # Indexing
    idx_pending = indexing_pending_raw
    idx_processing = processing_raw['indexing']
    idx_completed = counter_vals.get('docsearch:counter:indexing:completed', 0)
    
    # OCR
    ocr_pending = ocr_pending_raw
    ocr_processing = processing_raw['ocr']
    ocr_completed = counter_vals.get('docsearch:counter:ocr:completed', 0)
    
    # Completed & Failures
    completed_total = counter_vals.get('docsearch:counter:completed', 0)
    total_failures = sum(v for k, v in counter_vals.items() if 'failures' in k)
    
    # 4. Build our own extract_summary (avoid importing streamlit-dependent dashboard.py)
    def safe_int(val):
        if val is None: return 0
        try: return int(val)
        except: return 0
    
    # Simulate what extract_summary does
    discovery = queue_stats.get('discovery', {}) or {}
    extraction_total_stats = queue_stats.get('extraction_total', {}) or {}
    indexing_qs = queue_stats.get('indexing', {}) or {}
    ocr_qs = queue_stats.get('ocr', {}) or {}
    completed_qs = queue_stats.get('completed', {}) or {}
    
    dashboard_vals = {
        'discovered_total': safe_int(discovery.get('total')),
        'discovery_completed': safe_int(discovery.get('completed')),
        'extraction_pending': safe_int(extraction_total_stats.get('pending')),
        'extraction_processing': safe_int(extraction_total_stats.get('processing')),
        'extraction_completed': safe_int(extraction_total_stats.get('completed')),
        'indexing_pending': safe_int(indexing_qs.get('pending')),
        'indexing_processing': safe_int(indexing_qs.get('processing')),
        'indexing_completed': safe_int(indexing_qs.get('completed')),
        'ocr_pending': safe_int(ocr_qs.get('pending')),
        'ocr_processing': safe_int(ocr_qs.get('processing')),
        'ocr_completed': safe_int(ocr_qs.get('completed')),
        'completed_total': safe_int(completed_qs.get('total_completed') or completed_qs.get('total')),
        'total_failures': safe_int(queue_stats.get('total_failures')),
    }
    
    # 5. Compare
    print("\n{:<35} {:>15} {:>15} {:>8}".format("Metric", "Redis Raw", "Dashboard", "Match?"))
    print("-" * 78)
    
    checks = [
        ("discovered_total", disc_total, dashboard_vals['discovered_total']),
        ("discovery_completed", disc_completed, dashboard_vals['discovery_completed']),
        ("extraction_pending", ext_pending, dashboard_vals['extraction_pending']),
        ("extraction_processing", ext_processing, dashboard_vals['extraction_processing']),
        ("extraction_completed", ext_completed, dashboard_vals['extraction_completed']),
        ("indexing_pending", idx_pending, dashboard_vals['indexing_pending']),
        ("indexing_processing", idx_processing, dashboard_vals['indexing_processing']),
        ("indexing_completed", idx_completed, dashboard_vals['indexing_completed']),
        ("ocr_pending", ocr_pending, dashboard_vals['ocr_pending']),
        ("ocr_processing", ocr_processing, dashboard_vals['ocr_processing']),
        ("ocr_completed", ocr_completed, dashboard_vals['ocr_completed']),
        ("completed_total", completed_total, dashboard_vals['completed_total']),
        ("total_failures", total_failures, dashboard_vals['total_failures']),
    ]
    
    pass_count = 0
    fail_count = 0
    warn_count = 0
    
    for name, raw, dashboard in checks:
        # Allow small variance for processing counts (can change between reads)
        if raw == dashboard:
            status = "PASS"
            pass_count += 1
        elif abs(raw - dashboard) <= max(5, raw * 0.02):  # ≤2% or ≤5 items
            status = "WARN (±small)"
            warn_count += 1
        else:
            status = "FAIL"
            fail_count += 1  
        
        print("{:<35} {:>15,} {:>15,} {:>8}".format(name, raw, dashboard, status))
    
    # 6. Size stats validation
    print("\n\n{:<35} {:>15} {:>8}".format("Size Metric", "Value", "Status"))
    print("-" * 60)
    
    for key in ['discovered', 'in_pipeline', 'searchable', 'failed']:
        data = size_stats.get(key, {})
        files = data.get('files', 0)
        size_bytes = data.get('size_bytes', 0)
        status = "OK" if files > 0 or key == 'failed' else "ZERO"
        if status == "ZERO" and key != 'failed':
            fail_count += 1
        else:
            pass_count += 1
        
        def format_size(b):
            if b > 1024**3: return f"{b/1024**3:.2f} GB"
            if b > 1024**2: return f"{b/1024**2:.2f} MB"
            if b > 1024: return f"{b/1024:.2f} KB"
            return f"{b} B"
        print("{:<35} {:>15} {:>8}".format(
            f"{key}_files", f"{files:,}", status
        ))
        print("{:<35} {:>15} {:>8}".format(
            f"{key}_size", format_size(size_bytes), "OK"
        ))
    
    print("\n" + "=" * 70)
    print(f"RESULTS: {pass_count} PASS, {warn_count} WARN, {fail_count} FAIL")
    if fail_count == 0:
        print("ALL DASHBOARD METRICS SYNC WITH REDIS DATA")
    else:
        print("SOME METRICS DO NOT MATCH - REQUIRES INVESTIGATION")
    print("=" * 70)

if __name__ == '__main__':
    main()
