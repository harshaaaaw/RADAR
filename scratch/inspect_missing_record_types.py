import sqlite3
from pathlib import Path

def main():
    db_path = Path(__file__).resolve().parent.parent / "runtime" / "audit" / "audit.db"
    if not db_path.exists():
        print(f"DB not found at {db_path}")
        return

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute(
        "SELECT file_key, file_name, file_path, category, department FROM file_state "
        "WHERE (record_type_code IS NULL OR record_type_code = '') "
        "AND current_status != 'deleted'"
    )
    rows = cursor.fetchall()
    print(f"Total active rows missing record_type_code: {len(rows)}")

    for idx, row in enumerate(rows[:25], 1):
        print(f"{idx}. {row['file_name']} | Path: {row['file_path']} | Category: {row['category']} | Dept: {row['department']}")

    conn.close()

if __name__ == '__main__':
    main()
