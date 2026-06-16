
import sys
import redis

# Connect to Redis
try:
    client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    client.ping()
    print("[OK] Connected to Redis")
except Exception as e:
    print(f"[ERROR] Failed to connect to Redis: {e}")
    sys.exit(1)

PREFIX = "docsearch:"

def scan_keys(pattern):
    return sorted(client.keys(f"{PREFIX}{pattern}"))

print("\n=== DEBUGGING REDIS KEYS ===")

# 1. Check Counters (Primary source for totals)
print("\n[COUNTERS]")
counters = scan_keys("counter:*")
if counters:
    for key in counters:
        val = client.get(key)
        print(f"  {key}: {val}")
else:
    print("  No counter keys found!")

# 2. Check Queues (Pending work)
print("\n[QUEUES]")
queues = scan_keys("queue:*")
if queues:
    for key in queues:
        try:
            # Check type
            ktype = client.type(key)
            if ktype == 'zset':
                count = client.zcard(key)
                print(f"  {key} (ZSET): {count} items")
            elif ktype == 'list':
                count = client.llen(key)
                print(f"  {key} (LIST): {count} items")
            else:
                print(f"  {key} ({ktype})")
        except:
            print(f"  {key} (Error reading)")
else:
    print("  No queue keys found!")

# 3. Check Hash Maps (Completed/Failed)
print("\n[HASH MAPS]")
hashes = [f"{PREFIX}completed", f"{PREFIX}failed", f"{PREFIX}file_hashes"]
for key in hashes:
    if client.exists(key):
        count = client.hlen(key)
        print(f"  {key}: {count} items")
    else:
        print(f"  {key}: 0 items")

print("\nDone.")
