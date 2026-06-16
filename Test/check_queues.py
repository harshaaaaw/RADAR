
import sys
import time
sys.path.insert(0, "src")
from core.queue_manager import get_queue_manager

def check_queues():
    qm = get_queue_manager()
    stats = qm.get_queue_statistics()
    print("QUEUE STATISTICS:")
    print(stats)
    
    # Check if there are items in OCR queue
    ocr_pending = stats.get('ocr', {}).get('pending', 0)
    print(f"\nOCR Pending: {ocr_pending}")

if __name__ == "__main__":
    check_queues()
