
import sys
import os

# Add src to path
sys.path.append(os.path.join(os.getcwd(), 'src'))

from core.redis_queue_manager import RedisQueueManager

def verify_logic():
    print("Initializing RedisQueueManager...")
    qm = RedisQueueManager()
    
    print("Calling get_queue_stats()...")
    stats = qm.get_queue_stats()
    
    print("\n--- Queue Stats ---")
    print(f"Extraction Processing (Total): {stats['extraction_total']['processing']}")
    print(f"Indexing Processing: {stats['indexing']['processing']}")
    print(f"OCR Processing: {stats['ocr']['processing']}")
    
    print("\nFull OCR Stats:", stats['ocr'])
    print("\nFull Extraction Total Stats:", stats['extraction_total'])
    print("\nDetailed Extraction Stats:")
    for cat, data in stats['extraction'].items():
        print(f"  {cat}: Pending={data['pending']}, Processing={data['processing']}, Completed={data['completed']}")

    print("\nSuccess if processing numbers look reasonable (not hardcoded 0 if work is active).")

if __name__ == "__main__":
    verify_logic()
