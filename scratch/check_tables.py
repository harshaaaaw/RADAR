import sys, os, sqlite3, json, requests
sys.path.insert(0, 'src')
os.chdir(r'c:\Users\DELL\Music\DocumentSearch')

db_path = r'C:\Users\DELL\Music\DocumentSearch\runtime\audit\audit.db'
conn = sqlite3.connect(db_path)

# Check what tables exist and their structure
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"Tables: {[t[0] for t in tables]}")

# The documents table may be named differently
for t in tables:
    name = t[0]
    count = conn.execute(f"SELECT COUNT(*) FROM {name}").fetchone()[0]
    if count > 0:
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({name})").fetchall()]
        print(f"\n{name} ({count} rows): {cols}")
        
conn.close()
