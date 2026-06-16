
import redis
import json

def inspect_queue_item():
    r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
    
    # Check queues for any item
    found = False
    for cat in ['tiny', 'small', 'medium', 'large']:
        key = f"docsearch:queue:extraction:{cat}"
        items = r.zrange(key, 0, 0)
        if items:
            print(f"Found item in {cat}:")
            print(items[0])
            try:
                data = json.loads(items[0])
                print("Keys:", data.keys())
                if 'size_category' in data:
                    print(f"Has size_category: {data['size_category']}")
                else:
                    print("MISSING size_category in JSON")
            except:
                print("Invalid JSON")
                
            found = True
            break
            
    if not found:
        print("No items in extraction queues to inspect.")
        # Create a dummy item to see what push logic does? 
        # I'll rely on reading code if this fails.

if __name__ == "__main__":
    inspect_queue_item()
