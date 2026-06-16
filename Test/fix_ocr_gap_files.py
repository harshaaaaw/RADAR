
import redis
import json
import time

REDIS_URL = "redis://localhost:6379/0"
PREFIX = "docsearch:"
HASH_FILE_PATHS = f"{PREFIX}file_paths"
HASH_FILES = f"{PREFIX}files"
SET_COMPLETED_FILE_IDS = f"{PREFIX}completed_file_ids"
QUEUE_EXTRACTION = f"{PREFIX}queue:extraction"

def fix_ghost_files():
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        print("Connected to Redis.")
    except Exception as e:
        print(f"Could not connect to Redis: {e}")
        return

    print("Scanning for Ghost Files (In Completed Set but missing 'indexed_at')...")
    
    cursor = '0'
    ghost_files = []
    checked_count = 0
    
    while cursor != 0:
        cursor, data = r.hscan(HASH_FILE_PATHS, cursor=cursor, count=1000)
        for path, file_id in data.items():
            checked_count += 1
            if checked_count % 1000 == 0:
                print(f"Checked {checked_count} files...")

            # 1. Check if in Completed Set
            if r.sismember(SET_COMPLETED_FILE_IDS, file_id):
                # 2. Check metadata
                meta = r.hgetall(f"{HASH_FILES}:{file_id}")
                if not meta.get('indexed_at'):
                    print(f"FOUND GHOST: ID={file_id} Path={path}")
                    ghost_files.append((file_id, meta))
    
    print(f"Found {len(ghost_files)} ghost files.")
    
    if not ghost_files:
        return

    print("Restoring files to Extraction Queue...")
    pipe = r.pipeline()
    
    for file_id, meta in ghost_files:
        # 1. Remove from Completed Set
        pipe.srem(SET_COMPLETED_FILE_IDS, file_id)
        
        # 2. Update Status
        pipe.hset(f"{HASH_FILES}:{file_id}", "status", "pending")
        
        # 3. Re-queue for Extraction
        size_cat = meta.get('size_category', 'small')
        priority = int(meta.get('priority', 5))
        queue_key = f"{QUEUE_EXTRACTION}:{size_cat}"
        
        item = {
            'id': int(file_id),
            'file_id': int(file_id),
            'file_path': meta.get('file_path'),
            'file_size': int(meta.get('file_size', 0)),
            'size_category': size_cat,
            'priority': priority,
            'status': 'pending',
            'added_at': time.time(),
            # Important: Reset extraction fields to avoid confusion?
            # actually we want to re-extract.
        }
        
        # Add to Priority Queue
        pipe.zadd(queue_key, {json.dumps(item): priority})
        
        # Also remove from any stale processing keys if possible?
        # The worker should clean them up, or they expired.
        
    results = pipe.execute()
    print(f"Restored {len(ghost_files)} files. They should be picked up by Extraction Workers shortly.")

if __name__ == "__main__":
    fix_ghost_files()
