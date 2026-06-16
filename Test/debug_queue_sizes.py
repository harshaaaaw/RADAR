
import sys
import os
sys.path.append(os.path.join(os.getcwd(), 'src'))
from core.redis_queue_manager import RedisQueueManager

def debug_queues():
    qm = RedisQueueManager()
    r = qm.client
    
    print("--- Extraction Queue Sizes ---")
    total = 0
    for cat in ['tiny', 'small', 'medium', 'large']:
        key = f"docsearch:queue:extraction:{cat}"
        count = r.zcard(key)
        print(f"{cat:<10}: {count}")
        total += count
        
    print(f"Total     : {total}")

if __name__ == "__main__":
    debug_queues()
