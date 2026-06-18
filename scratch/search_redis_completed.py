import redis
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def main():
    r = redis.Redis(decode_responses=True)
    completed_hash = r.hgetall("docsearch:completed")
    
    target_ids = {"1", "2", "3"}
    
    for h, payload_json in completed_hash.items():
        payload = json.loads(payload_json)
        fid = str(payload.get("file_id"))
        if fid in target_ids:
            print(f"ID {fid} | Hash: {h}")
            print(f"Path: {payload.get('file_path')}")
            print(f"Payload: {json.dumps(payload, indent=2)}")
            print("-" * 50)

if __name__ == "__main__":
    main()
