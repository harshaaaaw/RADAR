import urllib.request
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

def main():
    url = "http://localhost:9200/enterprise_documents/_search?size=1"
    req = urllib.request.urlopen(url)
    resp = json.loads(req.read().decode())
    hits = resp.get("hits", {}).get("hits", [])
    if hits:
        print(json.dumps(hits[0]["_source"], indent=2))
    else:
        print("No documents found in OpenSearch.")

if __name__ == "__main__":
    main()
