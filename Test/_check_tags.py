"""Check tag field coverage - Windows safe encoding."""
import sys
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
import requests
import sqlite3
from pathlib import Path

print("=" * 70)
print("TAG FIELD COVERAGE ANALYSIS")
print("=" * 70)

# 1. Tag field coverage in OpenSearch
print("\n--- OpenSearch: Tag Field Coverage (2611 total docs) ---")
tag_fields = ["smart_id", "category", "department", "purpose",
              "dynamic_subtags", "key_names", "amount_found",
              "important_dates", "location_mentioned", "confidentiality"]
try:
    total_resp = requests.get("http://localhost:9200/enterprise_documents/_count", timeout=5)
    total = total_resp.json().get("count", 0)

    for field in tag_fields:
        q = {"query": {"exists": {"field": field}}}
        resp = requests.post(
            "http://localhost:9200/enterprise_documents/_count",
            json=q, timeout=5
        )
        count = resp.json().get("count", 0)
        pct = (count / total * 100) if total > 0 else 0
        marker = "[YES]" if count > 0 else "[NO] "
        print(f"  {marker} {field:25s}: {count:>5}/{total} ({pct:.1f}%)")
except Exception as e:
    print(f"  Error: {e}")

# 2. Check a doc that has tag fields vs one that doesn't
print("\n--- Sample: Document WITH smart_id ---")
try:
    q = {"size": 2, "_source": ["file_name", "smart_id", "category", "department",
         "purpose", "key_names", "confidentiality", "file_type", "amount_found"],
         "query": {"exists": {"field": "smart_id"}}}
    resp = requests.post("http://localhost:9200/enterprise_documents/_search", json=q, timeout=10)
    hits = resp.json().get("hits", {}).get("hits", [])
    if hits:
        for h in hits:
            s = h["_source"]
            print(f"  File: {s.get('file_name')}")
            for k, v in s.items():
                if k != "file_name":
                    print(f"    {k}: {v if v else '(empty)'}")
    else:
        print("  No documents have smart_id set")
except Exception as e:
    print(f"  Error: {e}")

# 3. Check audit DB
print("\n--- Audit DB: File State Tags ---")
audit_db = Path(r"C:\Users\DELL\Downloads\DocumentSearch_v5\DocumentSearch\runtime\audit\audit.db")
if audit_db.exists():
    conn = sqlite3.connect(str(audit_db), timeout=5)
    cur = conn.cursor()

    cur.execute("SELECT COUNT(*) FROM file_state")
    total = cur.fetchone()[0]
    print(f"  Total rows: {total}")

    for col in ["smart_id", "category", "department", "purpose",
                 "key_names", "amount_found", "important_dates",
                 "location_mentioned", "confidentiality"]:
        cur.execute(f"SELECT COUNT(*) FROM file_state WHERE {col} IS NOT NULL AND TRIM({col}) != ''")
        cnt = cur.fetchone()[0]
        marker = "[YES]" if cnt > 0 else "[NO] "
        print(f"  {marker} {col:25s}: {cnt:>5}/{total}")

    print("\n  Sample rows:")
    cur.execute("SELECT smart_id, file_name, category, department, purpose, current_status, tag_confidence FROM file_state LIMIT 5")
    for row in cur.fetchall():
        print(f"    ID={row[0]} | {row[1]} | cat={row[2]} | dept={row[3]} | purpose={row[4]} | status={row[5]} | conf={row[6]}")

    conn.close()

# 4. Check WHERE the tags come from - document_builder
print("\n--- Root Cause: Where do tags originate? ---")
print("  document_builder.py builds the OpenSearch document.")
print("  Checking if it sets tag fields...")

# Check a raw doc from OpenSearch to see what document_builder produces
q = {"size": 1, "_source": True, "query": {"match_all": {}}}
resp = requests.post("http://localhost:9200/enterprise_documents/_search", json=q, timeout=10)
hits = resp.json().get("hits", {}).get("hits", [])
if hits:
    src = hits[0]["_source"]
    tag_status = {}
    for f in tag_fields:
        val = src.get(f)
        has_value = val is not None and val != "" and val != []
        tag_status[f] = has_value
    populated = sum(1 for v in tag_status.values() if v)
    print(f"  Tag fields with values: {populated}/{len(tag_fields)}")
    if populated == 0:
        print("\n  ** CONCLUSION: document_builder.py does NOT generate tag values.")
        print("     The mapping fields exist in OpenSearch but NO worker populates them.")
        print("     Tags (category, department, purpose, etc.) need a TAGGING STAGE")
        print("     that analyzes content and writes values into these fields.")

print("\n" + "=" * 70)
