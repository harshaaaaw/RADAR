import sqlite3
from pathlib import Path

def main():
    db_file = Path("C:/Users/DELL/Music/DocumentSearch/runtime/audit/audit.db")
    if not db_file.exists():
        return

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    smart_id = "DOC-20260617-01BC"
    cursor.execute("SELECT review_id, snippet_type, accuracy_impact, status FROM snippet_reviews WHERE smart_id=?", (smart_id,))
    rows = cursor.fetchall()
    print(f"Total reviews for {smart_id}: {len(rows)}")
    for r in rows[:15]:
        print(f"  Type: {r['snippet_type']} | Impact: {r['accuracy_impact']}% | Status: {r['status']}")
    
    conn.close()

if __name__ == "__main__":
    main()
