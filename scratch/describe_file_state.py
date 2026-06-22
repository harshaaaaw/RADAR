import sqlite3

def main():
    conn = sqlite3.connect('runtime/audit/audit.db')
    cursor = conn.cursor()
    cursor.execute("PRAGMA table_info(file_state)")
    columns = [row[1] for row in cursor.fetchall()]
    print("file_state columns:", columns)
    conn.close()

if __name__ == '__main__':
    main()
