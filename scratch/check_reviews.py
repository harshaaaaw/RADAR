import sqlite3

def main():
    conn = sqlite3.connect('runtime/audit/audit.db')
    cursor = conn.cursor()
    cursor.execute("SELECT review_id, page_num, snippet_type, bounding_box_json, accuracy_impact, status, reviewer_role, deficit_category FROM snippet_reviews WHERE smart_id='DOC-20260616-E4D4'")
    rows = cursor.fetchall()
    print("Reviews for DOC-20260616-E4D4:")
    for r in rows:
        print(r)
    conn.close()

if __name__ == '__main__':
    main()
