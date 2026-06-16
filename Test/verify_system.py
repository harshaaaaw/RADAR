"""
Quick System Verification Script
Run this after restarting to verify all fixes are working
"""

import sys
import requests
from colorama import init, Fore

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except AttributeError:
    # Fallback for older python environments where reconfigure might not exist
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

init(autoreset=True)

def check_opensearch():
    """Check if OpenSearch is running and index exists"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}OpenSearch Verification")
    print(f"{Fore.CYAN}{'='*60}")
    
    try:
        # Check OpenSearch connection
        r = requests.get("http://localhost:9200", timeout=5)
        print(f"{Fore.GREEN}✓ OpenSearch is running")
        
        # Check if index exists
        try:
            r = requests.get("http://localhost:9200/enterprise_documents", timeout=5)
            print(f"{Fore.GREEN}✓ Index 'enterprise_documents' exists")
            
            # Get document count
            r = requests.get("http://localhost:9200/enterprise_documents/_count", timeout=5)
            count = r.json().get('count', 0)
            print(f"{Fore.GREEN}✓ Documents indexed: {count:,}")
            
            # Get index mapping
            r = requests.get("http://localhost:9200/enterprise_documents/_mapping", timeout=5)
            mapping = r.json()
            props = mapping.get('enterprise_documents', {}).get('mappings', {}).get('properties', {})
            
            # Check for .keyword subfields
            has_keyword = False
            for field in ['main_content', 'embedded_content', 'ocr_content']:
                if field in props and 'fields' in props[field]:
                    if 'keyword' in props[field]['fields']:
                        has_keyword = True
                        print(f"{Fore.GREEN}✓ {field}.keyword subfield exists")
            
            if not has_keyword:
                print(f"{Fore.YELLOW}⚠ Warning: .keyword subfields not found in mapping")
                print(f"{Fore.YELLOW}  Index may need to be recreated for search accuracy fix")
            
        except requests.exceptions.HTTPError as e:
            if "404" in str(e):
                print(f"{Fore.RED}✗ Index 'enterprise_documents' does NOT exist")
                print(f"{Fore.YELLOW}  Indexing workers may not have started yet")
                print(f"{Fore.YELLOW}  Wait 2-3 minutes and run this script again")
            else:
                print(f"{Fore.RED}✗ Error checking index: {e}")
        
    except requests.exceptions.ConnectionError:
        print(f"{Fore.RED}✗ Cannot connect to OpenSearch")
        print(f"{Fore.YELLOW}  Is OpenSearch running? Try: cd bin && .\\start_opensearch.bat")
    except Exception as e:
        print(f"{Fore.RED}✗ Error: {e}")


def check_redis():
    """Check if Redis is running"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Redis Verification")
    print(f"{Fore.CYAN}{'='*60}")
    
    try:
        import redis
        r = redis.Redis(host='localhost', port=6379, db=0, socket_timeout=5)
        r.ping()
        print(f"{Fore.GREEN}✓ Redis is running")
        
        # Check key count
        keys = r.keys('*')
        print(f"{Fore.GREEN}✓ Redis keys: {len(keys):,}")
        
    except ImportError:
        print(f"{Fore.YELLOW}⚠ Redis module not installed")
    except Exception as e:
        print(f"{Fore.RED}✗ Cannot connect to Redis: {e}")


def check_logs():
    """Check for recent errors in logs"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Recent Log Errors")
    print(f"{Fore.CYAN}{'='*60}")
    
    try:
        with open("D:\\DocumentSearch\\logs\\errors.log", "r") as f:
            lines = f.readlines()
            recent = lines[-10:] if len(lines) >= 10 else lines
            
            critical_errors = [
                "fail_indexing_items",
                "AttributeError",
                "index_not_found_exception"
            ]
            
            found_critical = False
            for line in recent:
                for error in critical_errors:
                    if error in line:
                        print(f"{Fore.RED}✗ Found critical error: {error}")
                        print(f"{Fore.YELLOW}  {line.strip()[:100]}")
                        found_critical = True
                        break
            
            if not found_critical:
                print(f"{Fore.GREEN}✓ No critical errors in recent logs")
            
    except FileNotFoundError:
        print(f"{Fore.YELLOW}⚠ Error log not found at D:\\DocumentSearch\\logs\\errors.log")
    except Exception as e:
        print(f"{Fore.RED}✗ Error reading logs: {e}")


def test_search():
    """Test search functionality with numeric query"""
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Search Accuracy Test")
    print(f"{Fore.CYAN}{'='*60}")
    
    try:
        # Check if index has any documents
        r = requests.get("http://localhost:9200/enterprise_documents/_count", timeout=5)
        count = r.json().get('count', 0)
        
        if count == 0:
            print(f"{Fore.YELLOW}⚠ No documents indexed yet - cannot test search")
            print(f"{Fore.YELLOW}  Wait for indexing to complete and try again")
            return
        
        # Test with a simple numeric query
        test_query = "2,480,821.04"
        query_body = {
            "query": {
                "multi_match": {
                    "query": test_query,
                    "fields": ["main_content", "ocr_content", "embedded_content"]
                }
            },
            "size": 5
        }
        
        r = requests.post(
            "http://localhost:9200/enterprise_documents/_search",
            json=query_body,
            timeout=10
        )
        
        results = r.json()
        hits = results.get('hits', {}).get('total', {}).get('value', 0)
        print(f"{Fore.GREEN}✓ Search is working")
        print(f"{Fore.CYAN}  Test query '{test_query}' returned {hits} results")
        
        # NOTE: Can't verify exact match accuracy without knowing actual data
        print(f"{Fore.YELLOW}  Manual verification needed:")
        print(f"{Fore.YELLOW}  1. Open dashboard: http://localhost:8501")
        print(f"{Fore.YELLOW}  2. Search for a known numeric value from your documents")
        print(f"{Fore.YELLOW}  3. Verify ONLY exact matches are returned")
        
    except requests.exceptions.HTTPError as e:
        if "404" in str(e):
            print(f"{Fore.RED}✗ Index does not exist - search unavailable")
        else:
            print(f"{Fore.RED}✗ Search error: {e}")
    except Exception as e:
        print(f"{Fore.RED}✗ Error: {e}")


def main():
    print(f"\n{Fore.YELLOW}{'='*60}")
    print(f"{Fore.YELLOW}DocumentSearch System Verification")
    print(f"{Fore.YELLOW}Running checks...")
    print(f"{Fore.YELLOW}{'='*60}")
    
    check_opensearch()
    check_redis()
    check_logs()
    test_search()
    
    print(f"\n{Fore.CYAN}{'='*60}")
    print(f"{Fore.CYAN}Verification Complete")
    print(f"{Fore.CYAN}{'='*60}\n")
    
    print(f"{Fore.GREEN}Next Steps:")
    print("  1. If index doesn't exist: Wait 2-3 minutes and run this again")
    print("  2. If critical errors: Check D:\\DocumentSearch\\logs\\errors.log")
    print("  3. Dashboard: http://localhost:8501")
    print("  4. OpenSearch: http://localhost:9200/_cat/indices?v")
    print()


if __name__ == "__main__":
    main()
