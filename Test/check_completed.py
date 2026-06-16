import sys
import json
sys.path.insert(0, r'c:\Users\hp212560601\Desktop\DocumentSearch\DocumentSearch\src')
from core.queue_manager import get_queue_manager

qm = get_queue_manager()
count = qm.client.hlen('completed_files')
print(f"Total completed files: {count}")

# Get a few samples
cursor = '0'
samples = 0
while samples < 3:
    cursor, data = qm.client.hscan('completed_files', cursor, count=5)
    for file_hash, info_json in data.items():
        try:
            info = json.loads(info_json)
            print(f"\nSample {samples + 1}:")
            for key in sorted(info.keys()):
                val = str(info[key])[:60]
                print(f"  {key}: {val}")
            samples += 1
            if samples >= 3:
                break
        except Exception as e:
            print(f"Error parsing: {e}")
    if cursor == 0 or cursor == b'0':
        break
