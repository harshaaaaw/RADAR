import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def main():
    # Fetch all docs where is_embedded is True
    url = "http://localhost:9200/enterprise_documents/_search"
    req_data = json.dumps({
        "query": {
            "term": {
                "is_embedded": True
            }
        },
        "size": 10
    }).encode('utf-8')
    
    req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req) as response:
            resp = json.loads(response.read().decode('utf-8'))
        hits = resp.get("hits", {}).get("hits", [])
        print(f"Found {len(hits)} embedded documents in OpenSearch:")
        for idx, hit in enumerate(hits, 1):
            source = hit.get("_source", {})
            print(f"[{idx}] File Name: {source.get('file_name')} | Parent: {source.get('parent_file')} | Hash: {source.get('file_hash')}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    main()
