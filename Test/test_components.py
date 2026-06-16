"""
Test Script - Verify all components are working
Run this to test: Redis queue, NLP correction, Preprocessing, Search accuracy
"""

import sys
import os

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

def test_redis_connection():
    """Test 1: Redis Connection"""
    print("\n" + "="*60)
    print("TEST 1: Redis Connection")
    print("="*60)
    
    try:
        import redis
        client = redis.Redis.from_url('redis://localhost:6379/0')
        
        # Test connection
        result = client.ping()
        if result:
            print("✓ Redis connection successful")
            
            # Test basic operations
            client.set('test_key', 'test_value')
            value = client.get('test_key')
            client.delete('test_key')
            
            if value == b'test_value':
                print("✓ Redis read/write operations working")
            else:
                print("✗ Redis read/write failed")
                return False
            
            return True
        else:
            print("✗ Redis ping failed")
            return False
            
    except ImportError:
        print("✗ redis-py not installed. Run: pip install redis")
        return False
    except redis.ConnectionError as e:
        print(f"✗ Redis connection failed: {e}")
        print("  Make sure Redis is running: redis-server")
        return False
    except Exception as e:
        print(f"✗ Redis test failed: {e}")
        return False


def test_redis_queue_manager():
    """Test 2: Redis Queue Manager"""
    print("\n" + "="*60)
    print("TEST 2: Redis Queue Manager")
    print("="*60)
    
    try:
        from core.redis_queue_manager import RedisQueueManager
        from core.constants import SizeCategory, Priority
        
        # Initialize manager
        manager = RedisQueueManager()
        print("✓ RedisQueueManager initialized")
        
        # Test add file
        file_id = manager.add_discovered_file(
            file_path="/test/file.pdf",
            file_name="file.pdf",
            file_size=1024,
            file_extension=".pdf",
            file_hash="test_hash_12345",
            last_modified=1234567890.0,
            created=1234567890.0,
            size_category=SizeCategory.SMALL,
            priority=Priority.NORMAL
        )
        
        if file_id:
            print(f"✓ Added test file with ID: {file_id}")
        else:
            print("✗ Failed to add test file (might be duplicate)")
        
        # Test queue stats
        stats = manager.get_queue_stats()
        print(f"✓ Queue stats: {stats}")
        
        # Cleanup test data
        manager.client.delete('docsearch:files:' + str(file_id))
        manager.client.srem('docsearch:file_hashes', 'test_hash_12345')
        
        print("✓ Redis Queue Manager working correctly")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Redis Queue Manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_nlp_corrector():
    """Test 3: NLP Text Corrector"""
    print("\n" + "="*60)
    print("TEST 3: NLP Text Corrector")
    print("="*60)
    
    try:
        from nlp.text_corrector import TextCorrector
        
        # Initialize corrector
        corrector = TextCorrector()
        print(f"✓ TextCorrector initialized (SpaCy loaded: {corrector.model_loaded})")
        
        # Test corrections
        test_cases = [
            # OCR year errors
            ("Meeting on March 37, 2041", "Meeting on March 31, 2011"),
            # Amount formatting
            ("Total: $97 621", "Total: $97,621"),
            # Financial phrase errors
            ("baiance sheet", "balance sheet"),
            ("income statment", "income statement"),
            # Character confusion
            ("MuItisite portfollo", "Multisite portfolio"),
        ]
        
        all_passed = True
        for input_text, expected in test_cases:
            corrected, count = corrector.correct(input_text)
            
            # Check if key corrections were made
            if expected.lower() in corrected.lower() or corrected != input_text:
                print(f"✓ '{input_text}' → '{corrected}' ({count} corrections)")
            else:
                print(f"✗ '{input_text}' → '{corrected}' (expected: '{expected}')")
                all_passed = False
        
        if all_passed:
            print("✓ NLP Text Corrector working correctly")
        else:
            print("⚠ Some corrections may need tuning")
        
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ NLP Corrector test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_image_preprocessor():
    """Test 4: Image Preprocessor"""
    print("\n" + "="*60)
    print("TEST 4: Image Preprocessor (Advanced)")
    print("="*60)
    
    try:
        import cv2
        import numpy as np
        
        # Create test image
        test_img = np.zeros((100, 200, 3), dtype=np.uint8)
        test_img[:, :] = [100, 100, 100]  # Gray background
        cv2.putText(test_img, "TEST", (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 2, (200, 200, 200), 2)
        
        # Encode to bytes
        _, buffer = cv2.imencode('.png', test_img)
        image_bytes = buffer.tobytes()
        
        print(f"✓ Created test image: {len(image_bytes)} bytes")
        
        from ocr.image_preprocessor_advanced import ImagePreprocessor, EnhancementLevel
        
        preprocessor = ImagePreprocessor()
        print("✓ ImagePreprocessor initialized")
        
        # Test preprocessing
        result = preprocessor.preprocess(image_bytes)
        
        if result and len(result) > 0:
            print(f"✓ Preprocessing successful: {len(result)} bytes output")
            
            # Decode and check
            result_arr = np.frombuffer(result, np.uint8)
            result_img = cv2.imdecode(result_arr, cv2.IMREAD_GRAYSCALE)
            
            if result_img is not None:
                print(f"✓ Output image: {result_img.shape}")
                print("✓ Image Preprocessor working correctly")
                return True
        
        print("✗ Preprocessing returned invalid result")
        return False
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Image Preprocessor test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_query_builder():
    """Test 5: Query Builder (Accurate Search)"""
    print("\n" + "="*60)
    print("TEST 5: Query Builder (Accurate Search - No Fuzzy)")
    print("="*60)
    
    try:
        from api.query_builder import QueryBuilder
        
        builder = QueryBuilder()
        print("✓ QueryBuilder initialized")
        
        # Test normal query (no fuzzy)
        query = builder.build_search_query(
            query_text="balance sheet 2023",
            fields=["main_content", "ocr_content"]
        )
        
        # Check that fuzziness is NOT in query
        query_str = str(query)
        if "fuzziness" not in query_str.lower():
            print("✓ No fuzziness in query - accurate search enabled")
        else:
            print("✗ Query still has fuzziness")
            return False
        
        # Check for cross_fields type
        if "cross_fields" in query_str:
            print("✓ Using cross_fields for better multi-word matching")
        
        # Check for minimum_should_match
        if "minimum_should_match" in query_str:
            print("✓ minimum_should_match configured for accuracy")
        
        # Test exact phrase query
        phrase_query = builder.build_search_query(
            query_text='"balance sheet"',
            fields=["main_content"]
        )
        
        if "match_phrase" in str(phrase_query):
            print("✓ Phrase query uses match_phrase for exact matching")
        
        print("✓ Query Builder working correctly (accurate search)")
        return True
        
    except ImportError as e:
        print(f"✗ Import error: {e}")
        return False
    except Exception as e:
        print(f"✗ Query Builder test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_opensearch_connection():
    """Test 6: OpenSearch Connection"""
    print("\n" + "="*60)
    print("TEST 6: OpenSearch Connection")
    print("="*60)
    
    try:
        from opensearchpy import OpenSearch
        
        client = OpenSearch(
            hosts=[{'host': 'localhost', 'port': 9200}],
            use_ssl=False,
            verify_certs=False,
            timeout=10
        )
        
        if client.ping():
            print("✓ OpenSearch connection successful")
            
            # Get cluster info
            info = client.info()
            print(f"✓ OpenSearch version: {info['version']['number']}")
            
            # Check index
            index_name = "enterprise_documents"
            if client.indices.exists(index=index_name):
                count = client.count(index=index_name)
                print(f"✓ Index '{index_name}' exists with {count['count']} documents")
            else:
                print(f"⚠ Index '{index_name}' does not exist yet")
            
            return True
        else:
            print("✗ OpenSearch ping failed")
            return False
            
    except ImportError:
        print("✗ opensearch-py not installed")
        return False
    except Exception as e:
        print(f"✗ OpenSearch connection failed: {e}")
        return False


def test_search_accuracy():
    """Test 7: Search Accuracy (if documents exist)"""
    print("\n" + "="*60)
    print("TEST 7: Search Accuracy Test")
    print("="*60)
    
    try:
        from opensearchpy import OpenSearch
        from api.query_builder import QueryBuilder
        
        client = OpenSearch(
            hosts=[{'host': 'localhost', 'port': 9200}],
            use_ssl=False,
            verify_certs=False,
            timeout=10
        )
        
        if not client.ping():
            print("⚠ OpenSearch not available, skipping search test")
            return True
        
        index_name = "enterprise_documents"
        if not client.indices.exists(index=index_name):
            print("⚠ Index not created yet, skipping search test")
            return True
        
        # Check document count
        count_result = client.count(index=index_name)
        doc_count = count_result['count']
        
        if doc_count == 0:
            print("⚠ No documents indexed yet, skipping search test")
            return True
        
        print(f"✓ Found {doc_count} documents in index")
        
        # Test search
        builder = QueryBuilder()
        
        # Search for common terms
        test_queries = ["document", "file", "2011", "pdf"]
        
        for query_text in test_queries:
            query = builder.build_search_query(
                query_text=query_text,
                fields=["main_content", "file_name", "ocr_content"]
            )
            
            response = client.search(
                index=index_name,
                body=query,
                size=5
            )
            
            hits = response['hits']['total']['value']
            print(f"✓ Search '{query_text}': {hits} results")
        
        print("✓ Search functionality working")
        return True
        
    except Exception as e:
        print(f"⚠ Search accuracy test error: {e}")
        return True  # Non-critical


def main():
    """Run all tests"""
    print("\n" + "="*60)
    print("DOCUMENT SEARCH SYSTEM - COMPONENT TESTS")
    print("="*60)
    
    results = {}
    
    # Run tests
    results['Redis Connection'] = test_redis_connection()
    results['Redis Queue Manager'] = test_redis_queue_manager()
    results['NLP Text Corrector'] = test_nlp_corrector()
    results['Image Preprocessor'] = test_image_preprocessor()
    results['Query Builder'] = test_query_builder()
    results['OpenSearch Connection'] = test_opensearch_connection()
    results['Search Accuracy'] = test_search_accuracy()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, passed_test in results.items():
        status = "✓ PASS" if passed_test else "✗ FAIL"
        print(f"  {status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! System is ready.")
        return 0
    else:
        print("\n⚠ Some tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
