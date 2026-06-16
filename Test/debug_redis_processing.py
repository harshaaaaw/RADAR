
import redis

def debug_processing_keys():
    try:
        r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
        
        print("Scaning for processing keys (docsearch:processing:*)...")
        keys = []
        cursor = '0'
        while cursor != 0:
            cursor, batch = r.scan(cursor=cursor, match="docsearch:processing:*", count=100)
            keys.extend(batch)
            
        print(f"Found {len(keys)} processing keys.")
        
        total_items = 0
        by_type = {'extraction': 0, 'indexing': 0, 'ocr': 0}
        
        for key in keys:
            dtype = r.type(key)
            if dtype == 'hash':
                count = r.hlen(key)
                print(f"  [{dtype}] {key}: {count} items")
                total_items += count
                
                if 'extraction' in key:
                    by_type['extraction'] += count
                elif 'indexing' in key:
                    by_type['indexing'] += count
                elif 'ocr' in key:
                    by_type['ocr'] += count
            else:
                print(f"  [{dtype}] {key} (Ignoring)")

        print("-" * 40)
        print(f"Total Processing Items: {total_items}")
        print(f"  Extraction: {by_type['extraction']}")
        print(f"  Indexing:   {by_type['indexing']}")
        print(f"  OCR:        {by_type['ocr']}")
        
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    debug_processing_keys()
