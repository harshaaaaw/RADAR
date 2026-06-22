import sys, sqlite3, os
sys.path.insert(0, 'src')

audit_db = 'runtime/audit/audit.db'
queue_db = 'runtime/queue/queues.db'

print("=== AUDIT DB ===")
if os.path.exists(audit_db):
    conn = sqlite3.connect(audit_db)
    conn.row_factory = sqlite3.Row
    total = conn.execute('SELECT COUNT(*) FROM file_state').fetchone()[0]
    print(f'Total docs in file_state: {total}')
    stages = conn.execute('SELECT stage, status, COUNT(*) as cnt FROM file_state GROUP BY stage, status ORDER BY stage, status').fetchall()
    for r in stages:
        print(f'  stage={r["stage"]:15} status={r["status"]:15} count={r["cnt"]}')
    conn.close()
else:
    print("Audit DB not found")

print()
print("=== QUEUE DB ===")
if os.path.exists(queue_db):
    conn2 = sqlite3.connect(queue_db)
    tables = conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    for t in tables:
        tname = t[0]
        try:
            cnt = conn2.execute(f'SELECT COUNT(*) FROM {tname}').fetchone()[0]
            if cnt > 0:
                print(f'  Table {tname}: {cnt} rows')
        except:
            pass
    conn2.close()
else:
    print("Queue DB not found")
