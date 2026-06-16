import sqlite3
from pathlib import Path

DB = Path('D:/DocumentSearch/queue/queues.db')

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
c = conn.cursor()

print('DB:', DB)

# Completed stats
row = c.execute("""
SELECT COUNT(*) as cnt, COALESCE(SUM(d.file_size),0) as total_size, COALESCE(AVG(d.file_size),0) as avg_size
FROM completed_files c
JOIN discovered_files d ON c.file_id = d.id
WHERE c.is_duplicate = 0
""").fetchone()
print('completed_count', row['cnt'])
print('completed_total_size_bytes', row['total_size'])
print('completed_avg_size_bytes', int(row['avg_size']))

# Top 20 largest completed files
print('\nTop 20 largest completed files:')
for r in c.execute("""
SELECT d.file_path, d.file_size
FROM completed_files c
JOIN discovered_files d ON c.file_id = d.id
WHERE c.is_duplicate = 0
ORDER BY d.file_size DESC
LIMIT 20
"""):
    print(r['file_size'], r['file_path'])

# Distribution counts
print('\nSize buckets (completed):')
for threshold in [1024, 1024*1024, 10*1024*1024, 100*1024*1024]:
    cnt = c.execute("SELECT COUNT(*) as cnt FROM completed_files c JOIN discovered_files d ON c.file_id=d.id WHERE c.is_duplicate=0 AND d.file_size <= ?", (threshold,)).fetchone()['cnt']
    print(f'<= {threshold} bytes: {cnt}')

conn.close()
