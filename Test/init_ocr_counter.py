
import redis

try:
    client = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    PREFIX = "docsearch:"
    
    # Get total completed (Indexing)
    total_completed = client.get(f"{PREFIX}counter:completed")
    if total_completed:
        total = int(total_completed)
        print(f"Total Completed (Indexing): {total}")
        
        # Set OCR completed to match
        # This assumes all currently indexed files passed through OCR
        client.set(f"{PREFIX}counter:ocr_completed", total)
        print(f"Initialized 'docsearch:counter:ocr_completed' to {total}")
    else:
        print("No completed files found. Initialized OCR counter to 0.")
        client.set(f"{PREFIX}counter:ocr_completed", 0)

except Exception as e:
    print(f"Error: {e}")
