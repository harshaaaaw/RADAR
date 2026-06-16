import sys
import json
sys.path.insert(0, r'c:\Users\hp212560601\Desktop\DocumentSearch\DocumentSearch\src')
from core.queue_manager import get_queue_manager

qm = get_queue_manager()
qs = qm.get_queue_statistics()
ss = qm.get_size_statistics()

print("QUEUE STATS:")
print(json.dumps(qs, indent=2, default=str))
print("\n\nSIZE STATS:")
print(json.dumps(ss, indent=2, default=str))
