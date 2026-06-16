
import sqlite3
import os

DB_PATHS = ["runtime/queue.db", "runtime/queue/queue.db", "data/queue.db"]

def inspect_file(filename):
    db_path = None
    for p in DB_PATHS:
        if os.path.exists(p):
            db_path = p
            break
            
    if not db_path:
        print(f"Database not found in: {DB_PATHS}")
        return

    print(f"Using database: {db_path}")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Find file_id
    print(f"Searching for {filename} in files table...")
    cursor.execute("SELECT id, path, status FROM files WHERE path LIKE ?", (f"%{filename}%",))
    files = cursor.fetchall()
    
    if not files:
        print("File not found in 'files' table.")
    
    for file_id, path, status in files:
        print(f"\nFile found: ID={file_id}, Path={path}, Status={status}")
        
        # 2. Check queue_ocr
        print(f"Checking queue_ocr for file_id {file_id}...")
        cursor.execute("SELECT id, status, worker_id, attempts, error_message FROM queue_ocr WHERE file_id = ?", (file_id,))
        ocr_tasks = cursor.fetchall()
        
        if ocr_tasks:
            for tid, tstatus, worker, attempts, error in ocr_tasks:
                print(f"  -> OCR Task: ID={tid}, Status={tstatus}, Worker={worker}, Attempts={attempts}, Error='{error}'")
        else:
            print("  -> No entry in queue_ocr.")
            
        # 3. Check queue_extraction (just in case)
        print(f"Checking queue_extraction for file_id {file_id}...")
        cursor.execute("SELECT id, status, worker_id FROM queue_extraction WHERE file_id = ?", (file_id,))
        ext_tasks = cursor.fetchall()
        for tid, tstatus, worker in ext_tasks:
            print(f"  -> Extraction Task: ID={tid}, Status={tstatus}, Worker={worker}")

    conn.close()

if __name__ == "__main__":
    inspect_file("stress_img_33.png")
