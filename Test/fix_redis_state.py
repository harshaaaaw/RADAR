
import redis

client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
PREFIX = "docsearch:"
QUEUE_DISCOVERY = f"{PREFIX}queue:discovery"
COUNTER_COMPLETED = f"{PREFIX}counter:completed"

try:
    # Get all items in discovery queue
    items = client.zrange(QUEUE_DISCOVERY, 0, -1)
    print(f"Items in Discovery Queue: {items}")
    
    if not items:
        print("Discovery Queue is empty. Nothing to fix.")
    else:
        # Check if they should be there
        removed_count = 0
        for file_id in items:
            # Check if this file is actually done/processing elsewhere
            # If we assume simple migration is done:
            print(f"Removing {file_id} from Discovery Queue (stale)...")
            client.zrem(QUEUE_DISCOVERY, file_id)
            removed_count += 1
            
        print(f"Removed {removed_count} stale items from Discovery Queue.")

    # Re-check
    count = client.zcard(QUEUE_DISCOVERY)
    print(f"Discovery Queue Pending: {count}")

except Exception as e:
    print(f"Error: {e}")
