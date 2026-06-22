import sqlite3
from pathlib import Path

def main():
    db_file = Path("C:/Users/DELL/Music/DocumentSearch/runtime/audit/audit.db")
    if not db_file.exists():
        print("Database file does not exist!")
        return

    conn = sqlite3.connect(db_file)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    
    # Find smart_id for real_funsd_form_023.pdf
    cursor.execute("SELECT smart_id, file_name FROM file_state WHERE file_name LIKE '%real_funsd_form_023.pdf%';")
    rows = cursor.fetchall()
    if not rows:
        print("Document real_funsd_form_023.pdf not found in file_state table.")
        conn.close()
        return
        
    for r in rows:
        smart_id = r["smart_id"]
        print(f"Smart ID: {smart_id} | Name: {r['file_name']}")
        
        # Check breakdown
        cursor.execute("SELECT * FROM page_segmentation_breakdown WHERE smart_id=?", (smart_id,))
        pages = cursor.fetchall()
        print(f"Breakdown rows: {len(pages)}")
        for p in pages:
            print("Page composition metrics:")
            for k in ["clean_text_pct", "whitespace_pct", "faded_text_pct", "logo_pct", "stamp_pct", "handwritten_pct", "noise_pct"]:
                print(f"  {k}: {p[k]}")
                
        # Check snippet reviews
        cursor.execute("SELECT COUNT(*), snippet_type, status FROM snippet_reviews WHERE smart_id=? GROUP BY snippet_type, status", (smart_id,))
        snippets = cursor.fetchall()
        print("\nSnippet reviews:")
        for s in snippets:
            print(f"  Type: {s[1]} | Status: {s[2]} | Count: {s[0]}")
            
    conn.close()

if __name__ == "__main__":
    main()
