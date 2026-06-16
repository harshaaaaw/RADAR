import sqlite3

def main():
    conn = sqlite3.connect('runtime/audit/audit.db')
    conn.row_factory = sqlite3.Row
    row = conn.execute("SELECT * FROM file_state WHERE smart_id = 'DOC-20260522-4AE0'").fetchone()
    if row:
        for k in row.keys():
            print(f"{k}: {row[k]}")
    else:
        print("Not found")

if __name__ == "__main__":
    main()
