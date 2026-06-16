import redis

try:
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    r.ping()
    print("✓ Redis connected\n")
    
    # Check extraction
    extraction_keys = r.keys('docsearch:queue:extraction:*')
    print(f"Extraction queue keys: {len(extraction_keys)}")
    total_extraction = 0
    for key in extraction_keys:
        count = r.zcard(key)
        if count > 0:
            print(f"  {key}: {count} items")
            total_extraction += count
    print(f"Total extraction pending: {total_extraction}\n")
    
    # Check indexing
    indexing = r.zcard('docsearch:queue:indexing:pending')
    indexing_proc = r.zcard('docsearch:queue:indexing:processing')
    print(f"Indexing pending: {indexing}")
    print(f"Indexing processing: {indexing_proc}\n")
    
    # Check OCR
    ocr = r.zcard('docsearch:queue:ocr:pending')
    ocr_proc = r.zcard('docsearch:queue:ocr:processing')
    print(f"OCR pending: {ocr}")
    print(f"OCR processing: {ocr_proc}\n")
    
    # Check discovery
    discovery = r.zcard('docsearch:queue:discovery:pending')
    print(f"Discovery pending: {discovery}\n")
    
    # Show stats
    stats_key = r.keys('docsearch:stats:*')
    print(f"Stats keys: {len(stats_key)}")
    
except Exception as e:
    print(f"ERROR: {type(e).__name__}: {e}")
