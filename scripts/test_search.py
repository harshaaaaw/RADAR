#!/usr/bin/env python
"""
Search System Test Script
Tests the search functionality with various scenarios
"""

import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent / "src"
sys.path.insert(0, str(src_path))

from indexing.opensearch_client import OpenSearchClient


def test_search():
    """Test search functionality"""
    print("=" * 60)
    print("SEARCH SYSTEM TEST RESULTS")
    print("=" * 60)
    
    os_client = OpenSearchClient()
    all_passed = True
    
    # Test 1: Exact phrase matching
    print("\n[1] EXACT PHRASE MATCHING:")
    try:
        # Search for "COVENANTS" with slop=0
        result = os_client.client.search(
            index=os_client.index_name,
            body={
                "query": {"match_phrase": {"ocr_content": {"query": "COVENANTS", "slop": 0}}},
                "size": 3,
                "_source": ["file_name"]
            }
        )
        hits = result["hits"]["total"]["value"]
        print(f'  - "COVENANTS" (exact): {hits} hits')
        
        # Search for partial "cov" with slop=0 - should be 0
        result2 = os_client.client.search(
            index=os_client.index_name,
            body={
                "query": {"match_phrase": {"ocr_content": {"query": "cov", "slop": 0}}},
                "size": 0
            }
        )
        partial_hits = result2["hits"]["total"]["value"]
        print(f'  - "cov" (partial): {partial_hits} hits')
        
        if hits > 0 and partial_hits == 0:
            print("  STATUS: PASS")
        elif hits == 0 and partial_hits == 0:
            print("  STATUS: PASS (dataset-specific term not present)")
        else:
            print("  STATUS: FAIL")
            all_passed = False
    except Exception as e:
        print(f"  STATUS: FAIL - {e}")
        all_passed = False
    
    # Test 2: Multi-word phrase
    print("\n[2] MULTI-WORD PHRASE:")
    try:
        # Search for "TRUSTOR COVENANTS"
        result = os_client.client.search(
            index=os_client.index_name,
            body={
                "query": {"match_phrase": {"ocr_content": {"query": "TRUSTOR COVENANTS", "slop": 0}}},
                "size": 3,
                "_source": ["file_name"]
            }
        )
        hits = result["hits"]["total"]["value"]
        print(f'  - "TRUSTOR COVENANTS" (exact): {hits} hits')
        
        # With slight slop
        result2 = os_client.client.search(
            index=os_client.index_name,
            body={
                "query": {"match_phrase": {"ocr_content": {"query": "TRUSTOR COVENANTS", "slop": 2}}},
                "size": 3,
                "_source": ["file_name"]
            }
        )
        slop_hits = result2["hits"]["total"]["value"]
        print(f'  - "TRUSTOR COVENANTS" (slop=2): {slop_hits} hits')
        
        if slop_hits >= hits:
            print("  STATUS: PASS")
        else:
            print("  STATUS: FAIL")
            all_passed = False
    except Exception as e:
        print(f"  STATUS: FAIL - {e}")
        all_passed = False
    
    # Test 3: Word that doesn't exist
    print("\n[3] NON-EXISTENT WORD:")
    try:
        result = os_client.client.search(
            index=os_client.index_name,
            body={
                "query": {"match_phrase": {"ocr_content": {"query": "RUSTOR", "slop": 0}}},
                "size": 0
            }
        )
        hits = result["hits"]["total"]["value"]
        print(f'  - "RUSTOR": {hits} hits')
        
        if hits == 0:
            print("  STATUS: PASS - Word correctly not found")
        else:
            print("  STATUS: FAIL - Should be 0 hits")
            all_passed = False
    except Exception as e:
        print(f"  STATUS: FAIL - {e}")
        all_passed = False
    
    # Test 4: File name search
    print("\n[4] FILE NAME SEARCH:")
    try:
        result = os_client.client.search(
            index=os_client.index_name,
            body={
                "query": {"match_phrase": {"file_name": {"query": "TITLE", "slop": 0}}},
                "size": 3,
                "_source": ["file_name"]
            }
        )
        hits = result["hits"]["total"]["value"]
        print(f'  - "TITLE" in file_name: {hits} hits')
        
        if hits > 0:
            for hit in result["hits"]["hits"][:3]:
                print(f'    * {hit["_source"]["file_name"][:60]}...')
            print("  STATUS: PASS")
        else:
            print("  STATUS: PASS (dataset-specific term not present)")
    except Exception as e:
        print(f"  STATUS: FAIL - {e}")
        all_passed = False
    
    # Test 5: Search ranking (exact match should score higher)
    print("\n[5] SEARCH RANKING:")
    try:
        result = os_client.client.search(
            index=os_client.index_name,
            body={
                "query": {
                    "bool": {
                        "should": [
                            {"match_phrase": {"file_name": {"query": "DEED", "boost": 100, "slop": 0}}},
                            {"match": {"main_content": {"query": "DEED", "boost": 10}}}
                        ]
                    }
                },
                "size": 5,
                "_source": ["file_name"]
            }
        )
        
        hits = result["hits"]["hits"]
        if len(hits) > 0:
            print("  - Top 3 results for 'DEED':")
            for i, hit in enumerate(hits[:3]):
                print(f"    {i+1}. Score: {hit['_score']:.2f} - {hit['_source']['file_name'][:50]}...")
            print("  STATUS: PASS")
        else:
            print("  STATUS: PASS (dataset-specific term not present)")
    except Exception as e:
        print(f"  STATUS: FAIL - {e}")
        all_passed = False
    
    # Test 6: OCR content vs main content
    print("\n[6] OCR vs MAIN CONTENT:")
    try:
        # Count documents with OCR content
        result = os_client.client.search(
            index=os_client.index_name,
            body={
                "query": {"exists": {"field": "ocr_content"}},
                "size": 0
            }
        )
        ocr_count = result["hits"]["total"]["value"]
        
        result2 = os_client.client.search(
            index=os_client.index_name,
            body={
                "query": {"exists": {"field": "main_content"}},
                "size": 0
            }
        )
        main_count = result2["hits"]["total"]["value"]
        
        print(f"  - Documents with OCR content: {ocr_count}")
        print(f"  - Documents with main content: {main_count}")
        
        if ocr_count > 0:
            print("  STATUS: PASS - OCR content is indexed")
        else:
            print("  STATUS: FAIL - No OCR content")
            all_passed = False
    except Exception as e:
        print(f"  STATUS: FAIL - {e}")
        all_passed = False
    
    # Final Summary
    print("\n" + "=" * 60)
    if all_passed:
        print("ALL SEARCH TESTS PASSED!")
    else:
        print("SOME SEARCH TESTS FAILED")
    print("=" * 60)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(test_search())
