import urllib.request
import json
import sys

def main():
    output_path = r"C:\Users\DELL\Music\DocumentSearch\scratch\inspect_form_009_result.txt"
    with open(output_path, "w", encoding="utf-8") as out:
        sys.stdout = out
        
        file_hash = "a9f095ebf03671ff71c7e889fc71424e6d81eebbbb82f5b59eaf4581cac7ff7e"
        print(f"--- QUERYING DIRECT DOC ID: {file_hash} ---")
        try:
            url = f"http://localhost:9200/enterprise_documents/_doc/{file_hash}"
            req = urllib.request.Request(url)
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                if data.get("found"):
                    print("Document Found:")
                    print(json.dumps(data["_source"], indent=2))
                else:
                    print("Document not found by direct ID.")
        except Exception as e:
            print(f"Failed to query direct ID: {e}")
            
        print("\n--- QUERYING BY file_hash field ---")
        try:
            url = "http://localhost:9200/enterprise_documents/_search"
            query = {
                "query": {
                    "term": {
                        "file_hash.keyword": file_hash
                    }
                }
            }
            req = urllib.request.Request(
                url, 
                data=json.dumps(query).encode("utf-8"),
                headers={"Content-Type": "application/json"}
            )
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                hits = data.get("hits", {}).get("hits", [])
                print(f"Hits count: {len(hits)}")
                for hit in hits:
                    print(f"Doc ID: {hit['_id']}")
                    print(json.dumps(hit["_source"], indent=2))
        except Exception as e:
            print(f"Failed to query search by file_hash: {e}")

if __name__ == "__main__":
    main()
