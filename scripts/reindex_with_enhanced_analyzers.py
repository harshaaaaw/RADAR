#!/usr/bin/env python
"""
Reindex with Enhanced Analyzers - Recreates the OpenSearch index with improved search analyzers.

This script:
1. Backs up existing index settings/mappings
2. Deletes the old index
3. Creates a new index with enhanced analyzers for better search accuracy
4. Optionally reindexes all documents from the queue

WARNING: This will delete all indexed documents! Run reset_state.py first if you want
to re-crawl and reindex everything from scratch.

Usage:
    python scripts/reindex_with_enhanced_analyzers.py [--confirm]
"""

import sys
import argparse
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / 'src'))

from core.config_manager import get_config, get_config_manager
from core.logging_manager import get_logger
from indexing.opensearch_client import OpenSearchClient

logger = get_logger("scripts.reindex")


def main():
    parser = argparse.ArgumentParser(
        description="Recreate OpenSearch index with enhanced search analyzers"
    )
    parser.add_argument(
        "--confirm", "-y",
        action="store_true",
        help="Skip confirmation prompt"
    )
    args = parser.parse_args()
    
    print("=" * 80)
    print("REINDEX WITH ENHANCED ANALYZERS")
    print("=" * 80)
    print()
    
    # Initialize config
    config_path = PROJECT_ROOT / "config" / "config.yaml"
    try:
        get_config_manager(str(config_path))
        config = get_config()
    except Exception as e:
        print(f"❌ Failed to load configuration: {e}")
        return 1
    
    index_name = config.indexing.opensearch.index_name
    
    print("This will:")
    print(f"  • Delete the existing index: {index_name}")
    print("  • Create a new index with enhanced analyzers for better search accuracy")
    print()
    print("Enhanced analyzers include:")
    print("  • OCR character error correction (0↔O, 1↔l, 5↔S, etc.)")
    print("  • Business terminology synonyms")
    print("  • Edge n-grams for partial word matching")
    print("  • Word delimiter handling for compound words")
    print()
    print("⚠️  WARNING: All indexed documents will be lost!")
    print("   You will need to re-run the orchestrator to reindex documents.")
    print()
    
    if not args.confirm:
        response = input("Continue? [y/N]: ").strip().lower()
        if response != 'y':
            print("Cancelled.")
            return 0
    
    print()
    print("-" * 80)
    print("Creating OpenSearch client...")
    
    try:
        os_client = OpenSearchClient()
    except Exception as e:
        print(f"❌ Failed to connect to OpenSearch: {e}")
        return 1
    
    # Check current index status
    try:
        if os_client.client.indices.exists(index=index_name):
            # Get document count
            count_response = os_client.client.count(index=index_name)
            doc_count = count_response.get('count', 0)
            print(f"📊 Current index has {doc_count:,} documents")
            print()
            
            # Delete the index
            print(f"🗑️  Deleting index: {index_name}...")
            os_client.client.indices.delete(index=index_name)
            print("✅ Index deleted")
        else:
            print(f"ℹ️  Index {index_name} does not exist yet")
    except Exception as e:
        print(f"❌ Error checking/deleting index: {e}")
        return 1
    
    # Create new index with enhanced analyzers
    print()
    print("📝 Creating new index with enhanced analyzers...")
    try:
        if os_client.ensure_index():
            print(f"✅ Index {index_name} created successfully with enhanced analyzers!")
        else:
            print("❌ Failed to create index")
            return 1
    except Exception as e:
        print(f"❌ Error creating index: {e}")
        return 1
    
    print()
    print("=" * 80)
    print("REINDEX COMPLETE")
    print("=" * 80)
    print()
    print("Next steps:")
    print("  1. Run the orchestrator to reindex all documents:")
    print("     python src/main.py")
    print()
    print("  2. Or reset state and re-crawl everything:")
    print("     python scripts/reset_state.py --yes")
    print("     python src/main.py")
    print()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
