import sys, os, requests, json
sys.path.insert(0, 'src')
os.chdir(r'c:\Users\DELL\Music\DocumentSearch')

# Check OpenSearch status
try:
    r = requests.get('http://localhost:9200', timeout=5)
    print(f"OpenSearch status: {r.status_code}")
    data = r.json()
    print(f"  cluster: {data.get('cluster_name')}, version: {data.get('version', {}).get('number')}")
except Exception as e:
    print(f"OpenSearch NOT reachable: {e}")

# Check index stats
try:
    r = requests.get('http://localhost:9200/enterprise_documents/_count', timeout=5)
    print(f"Index doc count: {r.json()}")
except Exception as e:
    print(f"Index query error: {e}")

# Try a sample search
try:
    body = {"query": {"match_all": {}}, "size": 3, "_source": ["file_name", "smart_id", "ocr_content"]}
    r = requests.post('http://localhost:9200/enterprise_documents/_search', json=body, timeout=10)
    hits = r.json().get('hits', {})
    total = hits.get('total', {}).get('value', 0)
    print(f"\nTotal docs in index: {total}")
    for h in hits.get('hits', []):
        src = h.get('_source', {})
        ocr = src.get('ocr_content', '')
        print(f"  {src.get('file_name')} | ocr={len(ocr)} chars")
except Exception as e:
    print(f"Search error: {e}")

# Check SQLite state
import sqlite3
db_path = r'C:\Users\DELL\Music\DocumentSearch\runtime\audit\reporting.db'
if os.path.exists(db_path):
    conn = sqlite3.connect(db_path)
    tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    print(f"\nSQLite tables: {[t[0] for t in tables]}")
    for t in tables:
        count = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
        print(f"  {t[0]}: {count} rows")
    conn.close()
else:
    print(f"\nDB not found at: {db_path}")
    # Find db files
    import glob
    dbs = glob.glob(r'C:\Users\DELL\Music\DocumentSearch\**\*.db', recursive=True)
    print(f"Found dbs: {dbs}")
