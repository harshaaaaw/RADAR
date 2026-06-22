import sqlite3

def main():
    db_path = r"C:\Users\DELL\Music\DocumentSearch\runtime\audit\audit.db"
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        rows = conn.execute('SELECT current_status, COUNT(*), AVG(extraction_accuracy) FROM file_state GROUP BY current_status').fetchall()
        print("=== File States by current_status ===")
        for r in rows:
            print(f"Status: {r[0]}, Count: {r[1]}, Avg Accuracy: {r[2]}")
            
        print("\n=== Specific Statuses ===")
        all_files = conn.execute('SELECT file_name, current_status, approval_status, extraction_accuracy FROM file_state').fetchall()
        for idx, f in enumerate(all_files, 1):
            if f['current_status'] != 'pending' or f['extraction_accuracy'] > 0.0:
                print(f"  {idx}. Name: {f['file_name']}, Status: {f['current_status']}, Approval: {f['approval_status']}, Acc: {f['extraction_accuracy']}")
                
    except Exception as exc:
        print(f"Failed: {exc}")

if __name__ == "__main__":
    main()
