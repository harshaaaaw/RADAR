import sys
sys.path.insert(0, r'c:\Users\hp212560601\Desktop\DocumentSearch\DocumentSearch\src')
from core.redis_queue_manager import RedisQueueManager
import redis

r_qm = RedisQueueManager()
result = r_qm.get_completed_files_stats()
print(f'get_completed_files_stats returned: {result}')

# Now check the actual hash
r = redis.Redis(host='localhost', port=6379, db=0, decode_responses=True)
count = r.hlen('pipeline:completed')
print(f'Actual Redis pipeline:completed hlen: {count}')

# Try discovery completed count
discovery_completed = r.hlen('pipeline:discovery')
print(f'pipeline:discovery hlen: {discovery_completed}')

# Debug: print what stats.get_queue_stats() returns
stats = r_qm.get_queue_stats()
print(f'\nget_queue_stats discovery section: {stats.get("discovery")}')
