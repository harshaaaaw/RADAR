
import redis

def dump_keys():
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    keys = []
    for key in r.scan_iter(match="*", count=1000):
        keys.append(key)
        
    print(f"Found {len(keys)} keys.")
    with open('all_keys.txt', 'w', encoding='utf-8') as f:
        for k in sorted(keys):
            f.write(k + '\n')
            
    print("Dumped to all_keys.txt")

if __name__ == "__main__":
    dump_keys()
