
import sys
sys.path.append("src")

from src.indexing.opensearch_client import OpenSearchClient
import json

def check_doc():
    client = OpenSearchClient()
    # doc_id is file_hash if available
    doc_id = "93ed6a50683417c684fd6908025b115acbaefaac26546e3d000243842e243c54"
    
    print(f"Checking OpenSearch for {doc_id}...")
    try:
        # Access internal client directly if wrapper method doesn't exist
        response = client.client.get(index=client.index_name, id=doc_id)
        if response and response.get('found'):
            print("Document FOUND!")
            print(json.dumps(response['_source'], indent=2))
        else:
            print("Document NOT FOUND.")
    except Exception as e:
        print(f"Error checking document: {e}")

if __name__ == "__main__":
    check_doc()
