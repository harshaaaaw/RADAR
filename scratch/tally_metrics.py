#!/usr/bin/env python3
"""
Tally Metrics Script
Directly queries Redis, SQLite, and OpenSearch to audit and verify dashboard stats.
"""
import sys
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')
import json
import sqlite3
from pathlib import Path
import redis
import urllib.request

def main():
    print("=" * 80)
    print(" MULTI-STORE METRIC TALLY & INTEGRITY AUDIT")
    print("=" * 80)
    
    # 1. SQLite Verification
    db_path = Path("runtime/audit/audit.db")
    if not db_path.exists():
        print("ERROR: SQLite database not found at runtime/audit/audit.db")
        return 1
        
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    
    db_total = conn.execute("SELECT COUNT(*) FROM file_state").fetchone()[0]
    db_by_status = {}
    for r in conn.execute("SELECT current_status, COUNT(*) as cnt FROM file_state GROUP BY current_status").fetchall():
        db_by_status[r["current_status"]] = r["cnt"]
        
    db_tag_fields = [
        "metadata_level_code", "record_class_name", "record_category_name_functional",
        "record_type_code", "business_unit_name", "sub_business_unit_name",
        "iso_country_code", "record_format_name", "original_record_location_type_name",
        "data_classification_name", "divestiture_deal_name"
    ]
    
    db_populated = {f: 0 for f in db_tag_fields}
    for row in conn.execute("SELECT * FROM file_state").fetchall():
        row_dict = dict(row)
        for f in db_tag_fields:
            val = row_dict.get(f)
            if val is not None and str(val).strip() != "":
                db_populated[f] += 1
                
    conn.close()
    
    print("\n[1/3] SQLite Database Audit:")
    print(f"  - Total tracked documents: {db_total}")
    print("  - Status Breakdown:")
    for status, cnt in db_by_status.items():
        print(f"    * {status}: {cnt}")
    print("  - 12-Dimension Tag Population:")
    for f, cnt in db_populated.items():
        pct = (cnt / db_total * 100) if db_total > 0 else 0
        print(f"    * {f:<38}: {cnt:<5d} ({pct:>6.1f}%)")
        
    # 2. OpenSearch Verification
    os_total = 0
    os_healthy = False
    try:
        url = "http://localhost:9200/enterprise_documents/_count"
        req = urllib.request.urlopen(url)
        resp = json.loads(req.read().decode())
        os_total = resp.get("count", 0)
        os_healthy = True
    except Exception as e:
        print(f"\n[2/3] OpenSearch Audit: FAILED (Cannot connect: {e})")
        
    if os_healthy:
        print(f"\n[2/3] OpenSearch Audit:")
        print(f"  - Total indexed documents in 'enterprise_documents': {os_total}")
        
    # 3. Redis Verification
    r_keys_count = 0
    r_active_queues = {}
    r_healthy = False
    try:
        r = redis.from_url('redis://localhost:6379/0')
        r_ping = r.ping()
        r_healthy = True
        
        # Scan all docsearch:* keys
        all_keys = list(r.scan_iter("docsearch:*"))
        r_keys_count = len(all_keys)
        
        # Categorize keys
        for k in all_keys:
            k_str = k.decode()
            k_type = r.type(k).decode()
            if k_type == "list":
                r_active_queues[k_str] = r.llen(k)
    except Exception as e:
        print(f"\n[3/3] Redis Audit: FAILED (Cannot connect: {e})")
        
    if r_healthy:
        print(f"\n[3/3] Redis Audit:")
        print(f"  - Total Redis keys matching 'docsearch:*': {r_keys_count}")
        print("  - Active Lists/Queues Lengths:")
        if r_active_queues:
            for q, len_q in r_active_queues.items():
                print(f"    * {q}: {len_q}")
        else:
            print("    * No active/pending queues in Redis (all queues empty)")
            
    # 4. Multi-Store Tally Validation
    print("\n" + "=" * 80)
    print(" METRICS COMPARATIVE ANALYSIS")
    print("=" * 80)
    
    print(f"  - SQLite Tracked Files:     {db_total}")
    print(f"  - OpenSearch Indexed Docs:  {os_total}")
    
    # Check alignment
    if db_total == os_total:
        print("\n  ✓ STATUS: 100% ALIGNED (SQLite and OpenSearch counts match exactly)")
    else:
        diff = abs(db_total - os_total)
        print(f"\n  ✗ STATUS: DISCREPANCY DETECTED! SQLite ({db_total}) and OpenSearch ({os_total}) differ by {diff}")
        
    # Check if queues are empty
    non_empty_queues = {q: l for q, l in r_active_queues.items() if l > 0}
    if not non_empty_queues:
        print("  ✓ QUEUE STATUS: idle (All Redis processing queues are completely empty)")
    else:
        print("  ✗ QUEUE STATUS: active (Some Redis processing queues still have pending items)")
        for q, l in non_empty_queues.items():
            print(f"    * {q}: {l} items pending")
            
    print("=" * 80)

if __name__ == "__main__":
    sys.exit(main())
