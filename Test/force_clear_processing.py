
import redis

def force_clear():
    # Connect to localhost
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    print("Scanning for processing keys...")
    keys = []
    for key in r.scan_iter(match="docsearch:processing:*"):
        keys.append(key)
        
    print(f"Found {len(keys)} processing keys.")
    for k in keys:
        print(f"Deleting {k}")
        r.delete(k)
        
    # Also check granular queues if they exist as keys (unlikely, they are ZSETS)
    # But check if there are any other weird keys
    
    print("Done.")

if __name__ == "__main__":
    force_clear()
