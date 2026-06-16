
import sys
import os
import logging
import json

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("debug_indexing")

from core.queue_manager import get_queue_manager
from core.config_manager import get_config
from indexing.document_builder import DocumentBuilder
from indexing.opensearch_client import OpenSearchClient

def debug_indexing():
    logger.info("Starting debug_indexing...")
    
    # Initialize components
    config = get_config()
    queue_manager = get_queue_manager()
    os_client = OpenSearchClient()
    doc_builder = DocumentBuilder()
    
    # Check stats
    stats = queue_manager.get_queue_stats()
    print("Queue Stats:", json.dumps(stats, indent=2))
    
    pending = stats.get('indexing', {}).get('pending', 0)
    if pending == 0:
        logger.info("No pending items in indexing queue.")
        return

    # Claim 1 item
    logger.info("Claiming 1 item...")
    work_items = queue_manager.claim_indexing_work("debug-worker", batch_size=1)
    
    if not work_items:
        logger.info("Claimed NO items (despite pending stats?)")
        return
        
    item = work_items[0]
    logger.info(f"Claimed item ID: {item.get('id')}, File ID: {item.get('file_id')}")
    
    # build document
    logger.info("Building document...")
    doc = doc_builder.build_document(item['document_json'])
    
    if not doc:
        logger.error("Failed to build document! (None returned)")
        return
        
    logger.info(f"Document built. ID: {doc.get('file_hash') or doc.get('content_hash')}")
    
    # Construct bulk item manually (mimic indexing_worker)
    doc_id = str(doc.get('file_hash') or f"file-{item.get('file_id')}")
    action = {
        '_index': os_client.index_name,
        '_id': doc_id,
        '_source': doc
    }
    
    bulk_items = [{
        'action': action,
        'queue_id': item['id'],
        'file_id': item['file_id'],
        'doc_id': doc_id,
        'retry_count': item.get('retry_count', 0)
    }]
    
    logger.info("Calling os_client.bulk_index with 1 item...")
    result = os_client.bulk_index(bulk_items)
    
    print("\nBulk Index Result:")
    print(json.dumps(result, indent=2, default=str))
    
    if result.get('success'):
        logger.info("Indexing SUCCESS")
    else:
        logger.error("Indexing FAILED")

if __name__ == "__main__":
    debug_indexing()
