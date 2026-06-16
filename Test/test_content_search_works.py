"""
Test that normal content searches (without backslash) still work properly.
Only backslash queries should be metadata-only.
"""
import sys
sys.path.insert(0, 'src')

from api.query_builder import QueryBuilder

def test_normal_vs_backslash_search():
    """Verify normal searches still include content, backslash searches don't."""
    qb = QueryBuilder()
    
    fields = ['main_content', 'embedded_content', 'ocr_content', 'file_name', 'file_path', 'category']
    
    print("\n=== Test 1: Normal Search (Should Include Content) ===")
    normal_query = "quarterly report analysis"
    result = qb.build_search_query(normal_query, fields)
    
    # Extract field names from the query
    searched_fields = set()
    query_obj = result.get('query', {})
    
    # For accurate query, it uses multi_match
    if 'bool' in query_obj and 'must' in query_obj['bool']:
        for clause in query_obj['bool']['must']:
            if 'multi_match' in clause:
                searched_fields.update(clause['multi_match'].get('fields', []))
    
    print(f"Query: '{normal_query}'")
    print(f"Fields searched: {sorted(searched_fields)}")
    
    content_fields = {'main_content', 'embedded_content', 'ocr_content'}
    found_content = searched_fields & content_fields
    
    if found_content:
        print(f"✅ PASS: Content fields included in normal search: {found_content}")
    else:
        print(f"❌ FAIL: Content fields missing from normal search")
        return False
    
    print("\n=== Test 2: Backslash Search (Should Exclude Content) ===")
    backslash_query = r"C:\Reports\quarterly.pdf"
    result = qb.build_search_query(backslash_query, fields)
    
    # Extract field names from path query (bool should with multiple clauses)
    searched_fields_path = set()
    query_obj = result.get('query', {})
    
    if 'bool' in query_obj and 'should' in query_obj['bool']:
        for clause in query_obj['bool']['should']:
            for op in ['term', 'wildcard', 'match_phrase', 'match']:
                if op in clause:
                    field = list(clause[op].keys())[0]
                    searched_fields_path.add(field.split('.')[0])
    
    print(f"Query: '{backslash_query}'")
    print(f"Fields searched: {sorted(searched_fields_path)}")
    
    found_content_path = searched_fields_path & content_fields
    
    if not found_content_path:
        print(f"✅ PASS: Content fields excluded from backslash search")
    else:
        print(f"❌ FAIL: Content fields found in backslash search: {found_content_path}")
        return False
    
    print("\n=== Test 3: Forward Slash Search (Should Also Exclude Content) ===")
    forward_slash_query = "Reports/data/analysis.xlsx"
    result = qb.build_search_query(forward_slash_query, fields)
    
    searched_fields_fwd = set()
    query_obj = result.get('query', {})
    
    if 'bool' in query_obj and 'should' in query_obj['bool']:
        for clause in query_obj['bool']['should']:
            for op in ['term', 'wildcard', 'match_phrase', 'match']:
                if op in clause:
                    field = list(clause[op].keys())[0]
                    searched_fields_fwd.add(field.split('.')[0])
    
    print(f"Query: '{forward_slash_query}'")
    print(f"Fields searched: {sorted(searched_fields_fwd)}")
    
    found_content_fwd = searched_fields_fwd & content_fields
    
    if not found_content_fwd:
        print(f"✅ PASS: Content fields excluded from forward slash search")
    else:
        print(f"❌ FAIL: Content fields found in forward slash search: {found_content_fwd}")
        return False
    
    print("\n=== Test 4: Phrase Search (Should Include Content) ===")
    phrase_query = '"employee performance review"'
    result = qb.build_search_query(phrase_query, fields)
    
    searched_fields_phrase = set()
    query_obj = result.get('query', {})
    
    if 'bool' in query_obj and 'should' in query_obj['bool']:
        for clause in query_obj['bool']['should']:
            if 'match_phrase' in clause:
                field = list(clause['match_phrase'].keys())[0]
                searched_fields_phrase.add(field)
    
    print(f"Query: {phrase_query}")
    print(f"Fields searched: {sorted(searched_fields_phrase)}")
    
    found_content_phrase = searched_fields_phrase & content_fields
    
    if found_content_phrase:
        print(f"✅ PASS: Content fields included in phrase search: {found_content_phrase}")
    else:
        print(f"❌ FAIL: Content fields missing from phrase search")
        return False
    
    return True

if __name__ == "__main__":
    try:
        success = test_normal_vs_backslash_search()
        if success:
            print("\n" + "="*70)
            print("✅ All tests passed!")
            print("\nSummary:")
            print("  • Normal searches: ✅ Include content fields (main/embedded/ocr)")
            print("  • Backslash searches: ✅ Exclude content (metadata-only)")
            print("  • Forward slash searches: ✅ Exclude content (metadata-only)")
            print("  • Phrase searches: ✅ Include content fields")
            print("="*70)
        else:
            print("\n❌ Tests failed")
            sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
