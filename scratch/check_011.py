import sqlite3

def main():
    db_path = r"C:\Users\DELL\Music\DocumentSearch\runtime\audit\audit.db"
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        row = conn.execute('SELECT * FROM file_state WHERE file_name LIKE "%011%"').fetchone()
        if row:
            print("=== File Info ===")
            print(f"File Name: {row['file_name']}")
            print(f"Smart ID: {row['smart_id']}")
            print(f"Approval Status: {row['approval_status']}")
            print(f"Extraction Accuracy: {row['extraction_accuracy']}")
            print(f"Enhanced Accuracy: {row['enhanced_accuracy']}")
            
            snippets = conn.execute('SELECT * FROM snippet_reviews WHERE smart_id=?', (row['smart_id'],)).fetchall()
            print(f"\nGenerated {len(snippets)} snippets:")
            for idx, sn in enumerate(snippets, 1):
                print(f"  {idx}. Review ID: {sn['review_id']}")
                print(f"     Type: {sn['snippet_type']}, Category: {sn['deficit_category']}")
                print(f"     Status: {sn['status']}, Role: {sn['reviewer_role']}")
                print(f"     BBox: {sn['bounding_box_json']}")
        else:
            print("No record found for form_011 yet.")
            
    except Exception as exc:
        print(f"Failed to check database: {exc}")

if __name__ == "__main__":
    main()
