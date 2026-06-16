"""Quick system monitor - checks Redis queues, OpenSearch, and audit DB."""
import redis
import requests
import sqlite3
from pathlib import Path

print("=" * 60)
print("SYSTEM MONITOR")
print("=" * 60)

# 1. Redis Queue Stats
print("\n--- Redis Queue Stats ---")
try:
    r = redis.from_url("redis://localhost:6379/0")
    print(f"  Discovered files:    {r.hlen('docsearch:files')}")
    print(f"  Extraction (tiny):   {r.zcard('docsearch:queue:extraction:tiny')}")
    print(f"  Extraction (small):  {r.zcard('docsearch:queue:extraction:small')}")
    print(f"  Extraction (medium): {r.zcard('docsearch:queue:extraction:medium')}")
    print(f"  Extraction (large):  {r.zcard('docsearch:queue:extraction:large')}")
    print(f"  Indexing queue:      {r.zcard('docsearch:queue:indexing')}")
    print(f"  OCR queue:           {r.zcard('docsearch:queue:ocr')}")

    # Completed count - check type first
    completed_key = "docsearch:completed"
    key_type = r.type(completed_key)
    if key_type == b"zset" or key_type == "zset":
        print(f"  Completed:           {r.zcard(completed_key)}")
    elif key_type == b"set" or key_type == "set":
        print(f"  Completed:           {r.scard(completed_key)}")
    elif key_type == b"hash" or key_type == "hash":
        print(f"  Completed:           {r.hlen(completed_key)}")
    else:
        print(f"  Completed key type:  {key_type}")
except Exception as e:
    print(f"  Redis error: {e}")

# 2. OpenSearch Doc Count
print("\n--- OpenSearch ---")
try:
    resp = requests.get("http://localhost:9200/enterprise_documents/_count", timeout=5)
    data = resp.json()
    print(f"  Indexed documents: {data.get('count', 0)}")
except Exception as e:
    print(f"  OpenSearch error: {e}")

# 3. Audit DB Stats
print("\n--- Audit DB ---")
audit_db = Path(r"C:\Users\DELL\Downloads\DocumentSearch_v5\DocumentSearch\runtime\audit\audit.db")
if audit_db.exists():
    try:
        conn = sqlite3.connect(str(audit_db), timeout=5)
        cur = conn.cursor()

        cur.execute("SELECT COUNT(*) FROM audit_events")
        print(f"  Total audit events:  {cur.fetchone()[0]}")

        cur.execute("SELECT stage, status, COUNT(*) FROM audit_events GROUP BY stage, status ORDER BY stage, status")
        rows = cur.fetchall()
        if rows:
            print("  Breakdown:")
            for stage, status, count in rows:
                print(f"    {stage}/{status}: {count}")

        cur.execute("SELECT COUNT(*) FROM file_state")
        print(f"  File state rows:     {cur.fetchone()[0]}")

        conn.close()
    except Exception as e:
        print(f"  Audit DB error: {e}")
else:
    print("  audit.db not found yet (will appear after first indexing)")

print("\n" + "=" * 60)
