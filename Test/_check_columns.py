import sqlite3, json

conn = sqlite3.connect(r'runtime\audit\audit.db')
conn.row_factory = sqlite3.Row

# Get column info
cur = conn.cursor()
cur.execute("PRAGMA table_info(file_state)")
cols = [(r[1], r[2]) for r in cur.fetchall()]
print(f"file_state table columns ({len(cols)}):")
for name, typ in cols:
    print(f"  {name} ({typ})")

print()

# Get all rows
rows = conn.execute("SELECT * FROM file_state").fetchall()
print(f"Rows: {len(rows)}")
for row in rows:
    d = dict(row)
    print("\n--- File State Row ---")
    # Show the 14 Excel columns specifically
    excel_cols = [
        "smart_id", "file_name", "category", "department", "purpose",
        "key_names", "amount_found", "important_dates", "location_mentioned",
        "confidentiality", "current_status", "processed_on", "file_type", "file_size"
    ]
    for col in excel_cols:
        val = d.get(col, "N/A")
        empty = " [EMPTY]" if (val is None or val == "" or val == 0) else ""
        print(f"  {col:25s} = {repr(val)}{empty}")
    
    # Also show extra columns
    print("  --- Extra columns ---")
    for col in d:
        if col not in excel_cols and col != "file_key":
            val = d[col]
            print(f"  {col:25s} = {repr(val)}")

conn.close()
