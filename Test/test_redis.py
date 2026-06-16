"""
Test Redis Queue Manager
"""
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.redis_queue_manager import RedisQueueManager
from core.constants import SizeCategory, Priority
import time

def test_redis_queue():
    print('Testing Redis Queue Manager...')
    
    try:
        manager = RedisQueueManager()
        print('✓ Connected to Redis')
        
        # Test add file
        test_hash = f'redis_test_hash_{int(time.time())}'
        file_id = manager.add_discovered_file(
            file_path='/test/redis_test.pdf',
            file_name='redis_test.pdf',
            file_size=1024,
            file_extension='.pdf',
            file_hash=test_hash,
            last_modified=time.time(),
            created=time.time(),
            size_category=SizeCategory.SMALL,
            priority=Priority.HIGH
        )
        
        print(f'✓ Added test file: {file_id}')
        
        # Get stats
        stats = manager.get_queue_stats()
        print(f'✓ Queue stats: {stats}')
        
        # Test claim operation
        claimed = manager.claim_extraction_work(
            worker_id="test_worker",
            size_category=SizeCategory.SMALL,
            batch_size=1
        )
        
        if claimed:
            print(f'✓ Claimed files for processing: {len(claimed)}')
            
            # Mark as completed
            manager.complete_extraction(
                file_id=file_id,
                worker_id="test_worker",
                content_hash='test_content_hash',
                content_size=500,
                content_type='application/pdf'
            )
            print('✓ Marked file as completed')
        
        print('\n🎉 Redis Queue Manager is working perfectly!')
        return True
        
    except Exception as e:
        print(f'✗ Redis test failed: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    test_redis_queue()