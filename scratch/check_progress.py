import sqlite3

def main():
    db_path = r"C:\Users\DELL\Music\DocumentSearch\runtime\audit\audit.db"
    try:
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        
        # Ingestion progress
        f_states = conn.execute(
            'SELECT COUNT(*), '
            'COUNT(CASE WHEN approval_status = "Full Baseline" THEN 1 END), '
            'COUNT(CASE WHEN approval_status = "Pending Review" THEN 1 END) '
            'FROM file_state'
        ).fetchone()
        
        # Review status
        reviews = conn.execute(
            'SELECT COUNT(*), '
            'COUNT(CASE WHEN status = "pending" THEN 1 END), '
            'COUNT(CASE WHEN status = "accepted" THEN 1 END) '
            'FROM snippet_reviews'
        ).fetchone()
        
        # Unique categories
        cats = conn.execute(
            'SELECT deficit_category, COUNT(*) FROM snippet_reviews GROUP BY deficit_category'
        ).fetchall()
        
        print("--- INGESTION PROGRESS ---")
        print(f"Total documents processed: {f_states[0]}")
        print(f"  Full Baseline: {f_states[1]}")
        print(f"  Pending Review: {f_states[2]}")
        print(f"Total snippets generated: {reviews[0]}")
        print(f"  Pending: {reviews[1]}")
        print(f"  Accepted (auto): {reviews[2]}")
        print("Snippet counts by category:")
        for cat in cats:
            print(f"  - {cat[0]}: {cat[1]}")
            
    except Exception as exc:
        print(f"Failed to check database: {exc}")

if __name__ == "__main__":
    main()
