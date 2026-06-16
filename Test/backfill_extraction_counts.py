
import redis

client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
PREFIX = "docsearch:"

counts = {'tiny': 0, 'small': 0, 'medium': 0, 'large': 0}

print("Scanning files...")
found = 0
for key in client.scan_iter(f"{PREFIX}files:*"):
    file_id = key.split(":")[-1]
    if not file_id.isdigit():
        continue
        
    data = client.hgetall(key)
    status = data.get('status', '')
    cat = data.get('size_category', '')
    
    if status in ['extracted', 'indexed', 'completed'] or data.get('extraction_completed_at'):
        if cat in counts:
            counts[cat] += 1
            found += 1

print(f"Found {found} extracted files.")
for cat, count in counts.items():
    print(f"  {cat}: {count}")
    key = f"{PREFIX}counter:extraction_completed:{cat}"
    client.set(key, count)
    print(f"  Set {key} = {count}")

print("Done.")
