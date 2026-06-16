
import redis
from collections import Counter

def debug_zombies():
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    print("Scanning file statuses...")
    
    status_counts = Counter()
    zombie_processing = 0
    checked = 0
    
    # Get all file keys
    cursor = '0'
    while cursor != 0:
        cursor, keys = r.scan(cursor=cursor, match="docsearch:files:*", count=1000)
        
        for key in keys:
            file_id = key.split(":")[-1]
            status = r.hget(key, "status")
            status_counts[status] += 1
            checked += 1
            
            if status == 'processing':
                # Check if in any processing hash
                # We need to know which stage? 
                # Usually status is just 'processing', we don't know stage easily without more metadata
                # specific status like 'processing_extraction' would contain stage.
                # But looking at RedisQueueManager constants, status is QueueStatus enum.
                pass

    print(f"Total Files Checked: {checked}")
    print("Status Distribution:")
    for status, count in status_counts.items():
        print(f"  {status}: {count}")

if __name__ == "__main__":
    debug_zombies()
