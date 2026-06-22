import sqlite3
from pathlib import Path

def print_table_schema(db_file, table_name):
    print(f"\nSchema for table: {table_name}")
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA table_info({table_name});")
        info = cursor.fetchall()
        for col in info:
            print(f"  Col: {col[1]} ({col[2]})")
        conn.close()
    except Exception as e:
        print("  Error:", e)

def main():
    db_file = Path("C:/Users/DELL/Music/DocumentSearch/runtime/audit/audit.db")
    if not db_file.exists():
        print("Database file does not exist!")
        return

    print_table_schema(db_file, "snippet_reviews")
    print_table_schema(db_file, "page_segmentation_breakdown")
    print_table_schema(db_file, "file_state")

    # Let's run a query to check some actual document paths
    try:
        conn = sqlite3.connect(db_file)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT DISTINCT smart_id, file_name, file_path FROM file_state LIMIT 5;")
        print("\nSample file_state records:")
        for r in cursor.fetchall():
            print(f"  Smart ID: {r['smart_id']} | Name: {r['file_name']} | Path: {r['file_path']}")
        
        cursor.execute("SELECT DISTINCT smart_id, status, COUNT(*) FROM snippet_reviews GROUP BY smart_id, status LIMIT 10;")
        print("\nSnippet reviews summary:")
        for r in cursor.fetchall():
            print(f"  Smart ID: {r[0]} | Status: {r[1]} | Count: {r[2]}")
            
        conn.close()
    except Exception as e:
        print("Error during sample query:", e)

if __name__ == "__main__":
    main()
