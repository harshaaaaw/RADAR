
import sys
from pathlib import Path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from indexing.opensearch_client import OpenSearchClient
client = OpenSearchClient()
mapping = client.client.indices.get_mapping(index=client.index_name)
import json
print(json.dumps(mapping, indent=2))
