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
    
    cursor.execute("SELECT DISTINCT smart_id FROM snippet_reviews LIMIT 5;")
    smart_ids = [row[0] for row in cursor.fetchall()]
    
    for smart_id in smart_ids:
        print(f"\nSmart ID: {smart_id}")
        cursor.execute("SELECT * FROM page_segmentation_breakdown WHERE smart_id=?", (smart_id,))
        pages = cursor.fetchall()
        if not pages:
            print("  No page breakdown found.")
            continue
            
        print(f"  Found {len(pages)} pages.")
        
        # Calculate averages
        keys = ["clean_text_pct", "whitespace_pct", "faded_text_pct", "logo_pct", "stamp_pct", "handwritten_pct", "noise_pct"]
        sums = {k: 0.0 for k in keys}
        for p in pages:
            for k in keys:
                sums[k] += float(p[k] or 0.0)
                
        n = len(pages)
        averages = {k: v / n for k, v in sums.items()}
        total = sum(averages.values())
        print("  Averages (raw sum = {:.2f}%):".format(total))
        for k, v in averages.items():
            print(f"    {k}: {v:.2f}%")
            
    conn.close()

if __name__ == "__main__":
    main()
