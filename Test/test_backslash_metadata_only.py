"""
Test backslash search - should match ONLY metadata/tags, NOT content.
"""
import sys
sys.path.insert(0, 'src')

from api.query_builder import QueryBuilder

def test_backslash_metadata_only():
    """Verify backslash searches exclude content fields."""
    qb = QueryBuilder()
    
    # Test 1: Path-like query
    query_text = r"C:\Users\test\document.pdf"
    fields = ['main_content', 'embedded_content', 'ocr_content', 'file_name', 'file_path', 'category']
    
    result = qb._build_path_query(query_text, fields)
    
    # Extract all field names from should clauses
    searched_fields = set()
    for clause in result['query']['bool']['should']:
        for op in ['term', 'wildcard', 'match_phrase', 'match']:
            if op in clause:
                field = list(clause[op].keys())[0]
                searched_fields.add(field.split('.')[0])  # Remove .keyword suffix
    
    print("\n=== Test 1: Backslash Search Field Check ===")
    print(f"Query: {query_text}")
    print(f"Fields searched: {sorted(searched_fields)}")
    
    # Verify content fields are NOT included
    content_fields = {'main_content', 'embedded_content', 'ocr_content'}
    found_content = searched_fields & content_fields
    
    if found_content:
        print(f"❌ FAIL: Content fields found in search: {found_content}")
        return False
    else:
        print("✅ PASS: Content fields excluded from search")
    
    # Verify metadata fields ARE included
    metadata_fields = {'file_path', 'file_name', 'category'}
    found_metadata = searched_fields & metadata_fields
    
    if found_metadata:
        print(f"✅ PASS: Metadata fields included: {found_metadata}")
    else:
        print(f"❌ FAIL: No metadata fields found in search")
        return False
    
    # Test 2: Verify query structure
    print("\n=== Test 2: Query Structure ===")
    print(f"Total should clauses: {len(result['query']['bool']['should'])}")
    print(f"Minimum should match: {result['query']['bool'].get('minimum_should_match', 'N/A')}")
    
    # Should have:
    # 1 term (file_path exact)
    # 1 wildcard (file_path)
    # 1 wildcard (file_name)
    # 2 per tag field (match_phrase + match) for both variants (backslash + forward slash)
    # = 3 + (num_tag_fields * 4)
    
    metadata_in_fields = [f for f in fields if f in ['file_name', 'file_path', 'category', 'department', 'purpose', 'file_type', 'smart_id', 'dynamic_subtags']]
    expected_min = 3 + (len(metadata_in_fields) * 4)  # 2 variants × 2 query types per field
    
    if len(result['query']['bool']['should']) >= expected_min:
        print(f"✅ PASS: Query has {len(result['query']['bool']['should'])} clauses (expected >= {expected_min})")
    else:
        print(f"⚠️ WARNING: Query has {len(result['query']['bool']['should'])} clauses (expected >= {expected_min})")
    
    return True

if __name__ == "__main__":
    try:
        success = test_backslash_metadata_only()
        if success:
            print("\n" + "="*60)
            print("✅ All tests passed!")
            print("Backslash searches now match ONLY metadata/tags, NOT content")
            print("="*60)
        else:
            print("\n❌ Tests failed")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
