#!/usr/bin/env python3
"""Monitor document processing progress."""
import sqlite3
import json
import time

def check_status():
    try:
        conn = sqlite3.connect('runtime/audit/audit.db')
        cursor = conn.cursor()
        
        # Get status distribution
        cursor.execute('SELECT current_status, COUNT(*) as count FROM file_state GROUP BY current_status')
        status_rows = cursor.fetchall()
        
        # Get extended metadata count
        cursor.execute('SELECT COUNT(*) FROM file_state WHERE extended_metadata_json IS NOT NULL AND extended_metadata_json != ""')
        extended_count = cursor.fetchone()[0]
        
        # Get sample with extended metadata
        cursor.execute('SELECT file_name, category, department, extended_metadata_json FROM file_state WHERE extended_metadata_json IS NOT NULL AND extended_metadata_json != "" LIMIT 1')
        sample = cursor.fetchone()
        
        print(f'\n=== Processing Status at {time.strftime("%H:%M:%S")} ===')
        print('\nFile Status Distribution:')
        total = 0
        for row in status_rows:
            print(f'  {row[0]}: {row[1]}')
            total += row[1]
        
        print(f'\nTotal files: {total}')
        print(f'With Extended Metadata: {extended_count}')
        
        if sample:
            print(f'\nSample Document:')
            print(f'  File: {sample[0]}')
            print(f'  Category: {sample[1]}')
            print(f'  Department: {sample[2]}')
            if sample[3]:
                try:
                    extended = json.loads(sample[3])
                    print(f'  Extended metadata keys: {list(extended.keys())}')
                    print(f'  Extended metadata sample: {json.dumps(extended, indent=4)[:300]}...')
                except:
                    print(f'  Extended (raw): {sample[3][:200]}...')
        
        conn.close()
        return total, extended_count
    except Exception as e:
        print(f'Error: {e}')
        return 0, 0

if __name__ == '__main__':
    check_status()
