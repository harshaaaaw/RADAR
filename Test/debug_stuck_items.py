
import redis

def debug_stuck_items():
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    print("--- Inspecting Processing Items (Wide Scan) ---")
    
    # Scan ALL docsearch keys to be sure
    count = 0
    for key in r.scan_iter(match="docsearch:processing:*", count=1000):
        count += 1
        print(f"\nFound Key: {key}")
        dtype = r.type(key)
        print(f"  Type: {dtype}")
        
        if dtype == 'hash':
            items = r.hgetall(key)
            print(f"  Item Count: {len(items)}")
            print(f"  TTL: {r.ttl(key)}")
            for k, v in items.items():
                print(f"    Field: {k[:10]}... => {v[:50]}...")
                
    print(f"\nTotal Processing Keys Found: {count}")


if __name__ == "__main__":
    debug_stuck_items()
