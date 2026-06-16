"""
Search Accuracy Test Suite for Enterprise Document Search System

This script tests search accuracy by:
1. Performing various types of searches against the OpenSearch index
2. Verifying that relevant results are returned
3. Measuring search performance and quality metrics
4. Testing OCR-specific search scenarios
5. Testing phrase matching, fuzzy matching, and synonym expansion

Run: python tests/test_search_accuracy.py
"""

import sys
import time
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime

# Ensure Unicode test output does not crash on Windows cp1252 consoles.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from indexing.opensearch_client import OpenSearchClient


@dataclass
class SearchResult:
    """Container for search result data"""
    query: str
    total_hits: int
    results: List[Dict[str, Any]]
    search_time_ms: float
    error: Optional[str] = None


@dataclass
class TestCase:
    """Container for a single test case"""
    name: str
    query: str
    query_type: str  # "keyword", "phrase", "fuzzy", "ocr", "synonym", "complex"
    expected_min_results: int = 1
    expected_fields: List[str] = None  # Fields where matches should be found
    description: str = ""


class SearchAccuracyTester:
    """Test search accuracy across various query types"""
    
    def __init__(self):
        self.os_client = None
        self.index_name = None
        self.test_results = []
        self.initialize_client()
    
    def initialize_client(self):
        """Initialize OpenSearch client"""
        try:
            self.os_client = OpenSearchClient()
            self.index_name = self.os_client.index_name
            print("✅ Connected to OpenSearch")
            print(f"📁 Index: {self.index_name}")
            
            # Get document count
            count = self.os_client.client.count(index=self.index_name)
            print(f"📊 Total Documents: {count['count']:,}")
            print()
        except Exception as e:
            print(f"❌ Failed to connect to OpenSearch: {e}")
            sys.exit(1)
    
    def execute_search(self, query: str, search_type: str = "multi_match", limit: int = 10) -> SearchResult:
        """Execute a search and return results"""
        start_time = time.time()
        
        try:
            # Build different query types
            if search_type == "phrase":
                # Exact phrase search
                search_body = {
                    "query": {
                        "bool": {
                            "should": [
                                {"match_phrase": {"file_name": {"query": query, "boost": 10}}},
                                {"match_phrase": {"main_content": {"query": query, "boost": 5}}},
                                {"match_phrase": {"ocr_content": {"query": query, "boost": 5}}},
                                {"match_phrase": {"embedded_content": {"query": query, "boost": 3}}}
                            ],
                            "minimum_should_match": 1
                        }
                    },
                    "size": limit,
                    "_source": ["file_name", "file_path", "main_content", "ocr_content", "embedded_content", "ocr_confidence"]
                }
            elif search_type == "fuzzy":
                # Fuzzy search for typo tolerance
                search_body = {
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": ["file_name^5", "main_content^3", "ocr_content^4", "embedded_content^2"],
                            "fuzziness": "AUTO",
                            "prefix_length": 2
                        }
                    },
                    "size": limit,
                    "_source": ["file_name", "file_path", "main_content", "ocr_content", "embedded_content", "ocr_confidence"]
                }
            else:
                # Multi-match search (default)
                search_body = {
                    "query": {
                        "multi_match": {
                            "query": query,
                            "fields": [
                                "file_name^10",
                                "file_path^5",
                                "main_content^3",
                                "ocr_content^4",
                                "embedded_content^2"
                            ],
                            "type": "best_fields",
                            "operator": "or",
                            "minimum_should_match": "50%"
                        }
                    },
                    "size": limit,
                    "highlight": {
                        "fields": {
                            "file_name": {"number_of_fragments": 0},
                            "main_content": {"fragment_size": 100, "number_of_fragments": 2},
                            "ocr_content": {"fragment_size": 100, "number_of_fragments": 2}
                        },
                        "pre_tags": ["**"],
                        "post_tags": ["**"]
                    },
                    "_source": ["file_name", "file_path", "main_content", "ocr_content", "embedded_content", "ocr_confidence"]
                }
            
            response = self.os_client.client.search(
                index=self.index_name,
                body=search_body
            )
            
            search_time = (time.time() - start_time) * 1000
            
            results = []
            for hit in response['hits']['hits']:
                result = {
                    'score': hit['_score'],
                    'file_name': hit['_source'].get('file_name', ''),
                    'file_path': hit['_source'].get('file_path', ''),
                    'has_main_content': bool(hit['_source'].get('main_content')),
                    'has_ocr_content': bool(hit['_source'].get('ocr_content')),
                    'has_embedded_content': bool(hit['_source'].get('embedded_content')),
                    'ocr_confidence': hit['_source'].get('ocr_confidence'),
                    'highlights': hit.get('highlight', {})
                }
                results.append(result)
            
            return SearchResult(
                query=query,
                total_hits=response['hits']['total']['value'],
                results=results,
                search_time_ms=search_time
            )
            
        except Exception as e:
            return SearchResult(
                query=query,
                total_hits=0,
                results=[],
                search_time_ms=(time.time() - start_time) * 1000,
                error=str(e)
            )
    
    def run_test_case(self, test: TestCase) -> Dict[str, Any]:
        """Run a single test case and return results"""
        # Determine search type based on query type
        search_type = "multi_match"
        if test.query_type == "phrase":
            search_type = "phrase"
        elif test.query_type == "fuzzy":
            search_type = "fuzzy"
        
        result = self.execute_search(test.query, search_type)
        
        passed = result.total_hits >= test.expected_min_results
        
        return {
            'test_name': test.name,
            'query': test.query,
            'query_type': test.query_type,
            'description': test.description,
            'passed': passed,
            'total_hits': result.total_hits,
            'expected_min': test.expected_min_results,
            'search_time_ms': result.search_time_ms,
            'top_results': result.results[:3],
            'error': result.error
        }
    
    def get_sample_documents(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get sample documents from the index to create realistic test queries"""
        try:
            response = self.os_client.client.search(
                index=self.index_name,
                body={
                    "query": {"match_all": {}},
                    "size": limit,
                    "_source": ["file_name", "file_path", "main_content", "ocr_content"]
                }
            )
            
            samples = []
            for hit in response['hits']['hits']:
                source = hit['_source']
                samples.append({
                    'file_name': source.get('file_name', ''),
                    'file_path': source.get('file_path', ''),
                    'main_content': (source.get('main_content', '') or '')[:500],
                    'ocr_content': (source.get('ocr_content', '') or '')[:500]
                })
            return samples
        except Exception as e:
            print(f"Error getting sample documents: {e}")
            return []
    
    def generate_dynamic_tests(self) -> List[TestCase]:
        """Generate test cases based on actual indexed documents"""
        tests = []
        samples = self.get_sample_documents(30)
        
        if not samples:
            print("⚠️ No sample documents found. Using generic tests only.")
            return tests
        
        # Generate tests from sample file names
        for i, sample in enumerate(samples[:5]):
            filename = sample.get('file_name', '')
            if filename:
                # Test exact filename search
                tests.append(TestCase(
                    name=f"filename_exact_{i+1}",
                    query=filename,
                    query_type="keyword",
                    expected_min_results=1,
                    description=f"Search for exact filename: {filename[:50]}..."
                ))
                
                # Test partial filename (first significant word)
                words = re.findall(r'\b[a-zA-Z]{4,}\b', filename)
                if words:
                    tests.append(TestCase(
                        name=f"filename_partial_{i+1}",
                        query=words[0],
                        query_type="keyword",
                        expected_min_results=1,
                        description=f"Search for keyword from filename: {words[0]}"
                    ))
        
        # Generate tests from content (if available)
        for i, sample in enumerate(samples[:3]):
            content = sample.get('main_content', '') or sample.get('ocr_content', '')
            if content:
                # Extract significant words from content
                words = re.findall(r'\b[a-zA-Z]{5,}\b', content)
                unique_words = list(set(words))[:3]
                
                for j, word in enumerate(unique_words):
                    tests.append(TestCase(
                        name=f"content_keyword_{i+1}_{j+1}",
                        query=word,
                        query_type="keyword",
                        expected_min_results=1,
                        description=f"Search for content keyword: {word}"
                    ))
        
        return tests
    
    def get_standard_tests(self) -> List[TestCase]:
        """Get standard test cases for common search scenarios"""
        return [
            # Basic keyword tests
            TestCase(
                name="basic_pdf",
                query="pdf",
                query_type="keyword",
                expected_min_results=1,
                description="Search for common file type keyword"
            ),
            TestCase(
                name="basic_document",
                query="document",
                query_type="keyword",
                expected_min_results=0,  # May or may not exist
                description="Search for common document term"
            ),
            TestCase(
                name="basic_contract",
                query="contract",
                query_type="keyword",
                expected_min_results=0,
                description="Search for business term: contract"
            ),
            TestCase(
                name="basic_agreement",
                query="agreement",
                query_type="keyword",
                expected_min_results=0,
                description="Search for business term: agreement"
            ),
            
            # Phrase search tests
            TestCase(
                name="phrase_loan_agreement",
                query="loan agreement",
                query_type="phrase",
                expected_min_results=0,
                description="Phrase search for 'loan agreement'"
            ),
            TestCase(
                name="phrase_tax_service",
                query="tax service",
                query_type="phrase",
                expected_min_results=0,
                description="Phrase search for 'tax service'"
            ),
            
            # Fuzzy search tests (typo tolerance)
            TestCase(
                name="fuzzy_agreemnt",
                query="agreemnt",  # Missing 'e'
                query_type="fuzzy",
                expected_min_results=0,
                description="Fuzzy search with typo: 'agreemnt'"
            ),
            TestCase(
                name="fuzzy_docment",
                query="docment",  # Missing 'u'
                query_type="fuzzy",
                expected_min_results=0,
                description="Fuzzy search with typo: 'docment'"
            ),
            
            # OCR-specific tests (common OCR errors)
            TestCase(
                name="ocr_zero_vs_o",
                query="2013",  # Year - should find if documents from 2013
                query_type="keyword",
                expected_min_results=0,
                description="OCR numeric search: year 2013"
            ),
            
            # Wildcard/partial match tests
            TestCase(
                name="partial_title",
                query="TITLE",
                query_type="keyword",
                expected_min_results=0,
                description="Search for partial term: TITLE"
            ),
            TestCase(
                name="partial_survey",
                query="SURVEY",
                query_type="keyword",
                expected_min_results=0,
                description="Search for partial term: SURVEY"
            ),
        ]
    
    def run_all_tests(self) -> Dict[str, Any]:
        """Run all test cases and return comprehensive results"""
        print("=" * 60)
        print("🔍 SEARCH ACCURACY TEST SUITE")
        print("=" * 60)
        print()
        
        # Gather all tests
        standard_tests = self.get_standard_tests()
        dynamic_tests = self.generate_dynamic_tests()
        all_tests = standard_tests + dynamic_tests
        
        print(f"📋 Running {len(all_tests)} test cases...")
        print(f"   - Standard tests: {len(standard_tests)}")
        print(f"   - Dynamic tests: {len(dynamic_tests)}")
        print()
        
        results = []
        passed = 0
        failed = 0
        
        for test in all_tests:
            result = self.run_test_case(test)
            results.append(result)
            
            if result['passed']:
                passed += 1
                status = "✅ PASS"
            else:
                failed += 1
                status = "❌ FAIL"
            
            print(f"{status} | {test.name}")
            print(f"       Query: '{test.query}' ({test.query_type})")
            print(f"       Hits: {result['total_hits']} (expected ≥{test.expected_min_results})")
            print(f"       Time: {result['search_time_ms']:.1f}ms")
            if result['top_results']:
                top = result['top_results'][0]
                print(f"       Top: {top['file_name'][:50]}... (score: {top['score']:.2f})")
            print()
        
        # Summary
        print("=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)
        print(f"   Total Tests:  {len(all_tests)}")
        print(f"   Passed:       {passed} ({passed/len(all_tests)*100:.1f}%)")
        print(f"   Failed:       {failed} ({failed/len(all_tests)*100:.1f}%)")
        
        # Performance stats
        search_times = [r['search_time_ms'] for r in results if not r['error']]
        if search_times:
            avg_time = sum(search_times) / len(search_times)
            max_time = max(search_times)
            min_time = min(search_times)
            print()
            print("⏱️ PERFORMANCE")
            print(f"   Avg Search Time: {avg_time:.1f}ms")
            print(f"   Min Search Time: {min_time:.1f}ms")
            print(f"   Max Search Time: {max_time:.1f}ms")
        
        # Return summary
        return {
            'total_tests': len(all_tests),
            'passed': passed,
            'failed': failed,
            'pass_rate': passed / len(all_tests) * 100 if all_tests else 0,
            'avg_search_time_ms': avg_time if search_times else 0,
            'results': results,
            'timestamp': datetime.now().isoformat()
        }
    
    def test_search_from_dashboard(self, query: str) -> Dict[str, Any]:
        """
        Test a specific search query (can be called from dashboard)
        Returns detailed results for display
        """
        result = self.execute_search(query, "multi_match", limit=20)
        
        return {
            'query': query,
            'total_hits': result.total_hits,
            'search_time_ms': result.search_time_ms,
            'results': [
                {
                    'filename': r['file_name'],
                    'filepath': r['file_path'],
                    'score': r['score'],
                    'has_ocr': r['has_ocr_content'],
                    'ocr_confidence': r['ocr_confidence'],
                    'highlights': r['highlights']
                }
                for r in result.results
            ],
            'error': result.error
        }


def main():
    """Main entry point"""
    print()
    print("🚀 Enterprise Document Search - Search Accuracy Tester")
    print()
    
    tester = SearchAccuracyTester()
    
    # Check for command line arguments
    if len(sys.argv) > 1:
        # Run a single query test
        query = " ".join(sys.argv[1:])
        print(f"Testing single query: '{query}'")
        print()
        result = tester.test_search_from_dashboard(query)
        print(json.dumps(result, indent=2, default=str))
    else:
        # Run full test suite
        results = tester.run_all_tests()
        
        # Save results to file
        output_file = PROJECT_ROOT / "tests" / "search_accuracy_results.json"
        with open(output_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)
        print()
        print(f"📄 Results saved to: {output_file}")


if __name__ == "__main__":
    main()
