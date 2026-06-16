
import redis
import json

REDIS_URL = "redis://localhost:6379/0"
PREFIX = "docsearch:"
HASH_FILE_PATHS = f"{PREFIX}file_paths"
HASH_FILES = f"{PREFIX}files"
QUEUE_OCR = f"{PREFIX}queue:ocr"
PROCESSING_OCR = f"{PREFIX}processing:ocr"

def inspect_file(filename):
    try:
        r = redis.from_url(REDIS_URL, decode_responses=True)
        r.ping()
        print("Connected to Redis.")
    except Exception as e:
        print(f"Could not connect to Redis: {e}")
        return

    # Try to find the file ID by path (suffix match)
    # Since we don't know the exact absolute path used in Redis (might differ slightly),
    # we'll scan HASH_FILE_PATHS.
    print(f"Scanning for paths ending in '{filename}'...")
    
    found_id = None
    found_path = None
    
    cursor = '0'
    while cursor != 0:
        cursor, data = r.hscan(HASH_FILE_PATHS, cursor=cursor, count=1000)
        for path, fid in data.items():
            if str(path).endswith(filename):
                found_id = fid
                found_path = path
                break
        if found_id:
            break
            
    if not found_id:
        print("File not found in docsearch:file_paths")
        return

    print(f"Found File ID: {found_id} at Path: {found_path}")
    
    # Get Metadata
    metadata = r.hgetall(f"{HASH_FILES}:{found_id}")
    print("\nMetadata:")
    for k, v in metadata.items():
        print(f"  {k}: {v}")

    # Check Status in Metadata
    status = metadata.get('status')
    print(f"\nStatus in Metadata: {status}")

    # Check OCR Queue
    # ZSet: value=json_str, score=priority
    print("\nChecking OCR Queue (Pending)...")
    ocr_queue = r.zrange(QUEUE_OCR, 0, -1, withscores=True)
    in_queue = False
    for item_str, score in ocr_queue:
        item = json.loads(item_str)
        if str(item.get('file_id')) == str(found_id):
            print(f"  -> FOUND in Pending Queue! Priority: {score}")
            in_queue = True
            break
    if not in_queue:
        print("  -> Not in Pending Queue")

    # Check Processing Queues
    print("\nChecking OCR Processing Queues...")
    # Scan keys docsearch:processing:ocr:*
    proc_keys = r.keys(f"{PROCESSING_OCR}:*")
    in_proc = False
    for ind_key in proc_keys:
        # It's a Hash: field=file_id, value=json
        val = r.hget(ind_key, str(found_id))
        if val:
            print(f"  -> FOUND in Processing Queue: {ind_key}")
            print(f"     Value: {val}")
            in_proc = True
    
    if not in_proc:
        print("  -> Not in any Processing Queue")

    # Check Failed Hash
    print("\nChecking Failed Hash...")
    failed_data = r.hget(f"{PREFIX}failed", str(found_id))
    if failed_data:
        print(f"  -> FOUND in Failed Hash! Value: {failed_data}")
    else:
        print("  -> Not in Failed Hash")

    # Check Completed File IDs Set
    print("\nChecking Completed File IDs Set...")
    is_completed_id = r.sismember(f"{PREFIX}completed_file_ids", str(found_id))
    if is_completed_id:
        print("  -> FOUND in Completed File IDs Set! (Worker thought it was done)")
    else:
        print("  -> Not in Completed File IDs Set")

if __name__ == "__main__":
    inspect_file("stress_img_33.png")
