import requests
import urllib3
import sys
urllib3.disable_warnings()

# Default OpenSearch URL
OS_URL = "http://localhost:9200/enterprise_documents/_search"
QUERY = "Content inside zip"

data = {
    "query": {
        "match": {
            "file_name": "inner_text.txt"
        }
    },
    "size": 10
}

try:
    print(f"Searching for: '{QUERY}'")
    resp = requests.get(OS_URL, json=data, verify=False, auth=('admin', 'admin'))
    
    if resp.status_code == 200:
        results = resp.json()
        hits = results.get('hits', {}).get('hits', [])
        total = results.get('hits', {}).get('total', {}).get('value', 0)
        print(f"Total Hits: {total}")
        for hit in hits:
            source = hit['_source']
            print(f"- {source.get('file_name')} (Score: {hit['_score']})")
            print(f"  Path: {source.get('file_path')}")
            print(f"  Snippet: {source.get('content', '')[:100]}...")
            
        if total > 0:
            print("\nSUCCESS: Deep extracted content is indexed.")
            sys.exit(0)
        else:
            print("\nFAILURE: No results found for deep extracted content.")
            sys.exit(1)
    else:
        print(f"Search Failed: HTTP {resp.status_code}")
        print(resp.text)
        sys.exit(1)

except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)
