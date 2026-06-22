import sys, os, sqlite3, json
sys.path.insert(0, 'src')
os.chdir(r'c:\Users\DELL\Music\DocumentSearch')

# Check audit.db
db_path = r'C:\Users\DELL\Music\DocumentSearch\runtime\audit\audit.db'
conn = sqlite3.connect(db_path)
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"audit.db tables: {[t[0] for t in tables]}")
for t in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
    print(f"  {t[0]}: {count} rows")
    if count > 0:
        cols = [c[1] for c in conn.execute(f"PRAGMA table_info({t[0]})").fetchall()]
        print(f"    cols: {cols}")
        row = conn.execute(f"SELECT * FROM {t[0]} LIMIT 1").fetchone()
        print(f"    sample: {dict(zip(cols, row))}")
conn.close()

# Check queue.db
db_path2 = r'C:\Users\DELL\Music\DocumentSearch\runtime\queue\queue.db'
conn2 = sqlite3.connect(db_path2)
tables2 = conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"\nqueue.db tables: {[t[0] for t in tables2]}")
for t in tables2:
    count = conn2.execute(f"SELECT COUNT(*) FROM {t[0]}").fetchone()[0]
    print(f"  {t[0]}: {count} rows")
conn2.close()

# Check where the reporting manager is writing
import glob
[print(f, i+1, line.strip()) for f in glob.glob('src/core/reporting_manager.py') 
 for i, line in enumerate(open(f, encoding='utf-8', errors='ignore'))
 if 'audit.db' in line or 'reporting.db' in line or 'DB_PATH' in line or 'db_path' in line.lower()]
