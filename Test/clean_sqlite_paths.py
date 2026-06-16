"""Clean file paths from key_names and location_mentioned in SQLite."""
import sqlite3, glob

db = 'runtime/audit/audit.db'
print(f"DB: {db}")
conn = sqlite3.connect(db)

# Check current state
rows = conn.execute("SELECT file_name, key_names FROM file_state WHERE key_names LIKE '%users%' OR key_names LIKE '%.txt%' OR key_names LIKE '%documentsearch%'").fetchall()
print(f"Found {len(rows)} rows with path fragments in key_names:")
for r in rows:
    print(f"  {r[0]}: {r[1][:100]}")

# Clean: remove file paths from key_names
# Strategy: for rows with paths, extract only the clean person names
import re
PATH_RE = re.compile(r'[a-z]:\\|[\\/]users[\\/]|documentsearch|\.(?:txt|json|csv|xml|html|pdf|docx)\b', re.IGNORECASE)

for r in rows:
    file_name = r[0]
    key_names_raw = r[1] or ''
    # Split by comma, filter out path-containing segments
    parts = [p.strip() for p in key_names_raw.split(',')]
    clean_parts = [p for p in parts if p and not PATH_RE.search(p)]
    clean_value = ', '.join(clean_parts)
    if clean_value != key_names_raw:
        conn.execute("UPDATE file_state SET key_names = ? WHERE file_name = ?", (clean_value, file_name))
        print(f"  CLEANED: {file_name}: '{key_names_raw[:60]}' -> '{clean_value}'")

# Also clean location_mentioned with file paths
rows2 = conn.execute("SELECT file_name, location_mentioned FROM file_state WHERE location_mentioned LIKE '%users%' OR location_mentioned LIKE '%documentsearch%'").fetchall()
print(f"\nFound {len(rows2)} rows with path in location_mentioned:")
for r in rows2:
    print(f"  {r[0]}: {r[1][:100]}")
    conn.execute("UPDATE file_state SET location_mentioned = '' WHERE file_name = ?", (r[0],))
    print(f"  CLEANED -> ''")

# Also clean "item-3" and similar non-location values from location_mentioned
rows3 = conn.execute("SELECT file_name, location_mentioned FROM file_state WHERE location_mentioned LIKE 'item-%'").fetchall()
for r in rows3:
    conn.execute("UPDATE file_state SET location_mentioned = '' WHERE file_name = ?", (r[0],))
    print(f"  CLEANED location '{r[1]}' -> '' for {r[0]}")

conn.commit()
print("\nDone")
