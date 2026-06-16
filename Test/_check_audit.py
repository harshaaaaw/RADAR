import sqlite3, os

db_path = r'runtime\audit\audit.db'
if not os.path.exists(db_path):
    print("audit.db does not exist")
    exit()

print(f"audit.db size: {os.path.getsize(db_path)} bytes")
conn = sqlite3.connect(db_path)
cur = conn.cursor()

# List tables
cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
tables = [r[0] for r in cur.fetchall()]
print(f"Tables: {tables}")

# Row counts
for t in tables:
    count = conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
    print(f"  {t}: {count} rows")

# Sample audit_events
print("\n--- audit_events sample ---")
for row in conn.execute("SELECT * FROM audit_events LIMIT 5").fetchall():
    print(row)

# Sample file_state
print("\n--- file_state sample ---")
cur.execute("PRAGMA table_info(file_state)")
cols = [r[1] for r in cur.fetchall()]
print(f"Columns ({len(cols)}): {cols}")
for row in conn.execute("SELECT * FROM file_state LIMIT 3").fetchall():
    print(row)

conn.close()
