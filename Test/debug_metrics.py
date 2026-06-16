
import sys
import time
from pathlib import Path

# Add src to path
project_root = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(project_root))

try:
    from core.config_manager import get_config
    from core.queue_manager import get_queue_manager
    
    print("1. Testing Config Load...")
    config = get_config()
    print("   Config loaded OK.")
    
    print("\n2. Testing Queue Manager Connection...")
    qm = get_queue_manager()
    print(f"   Queue Manager: {qm}")
    print(f"   Redis URL: {config.redis.url}")
    
    print("\n3. Testing get_queue_statistics()...")
    start = time.time()
    stats = qm.get_queue_statistics()
    duration = time.time() - start
    print(f"   Duration: {duration:.4f}s")
    print(f"   Result Type: {type(stats)}")
    print(f"   Result Check: isinstance(dict)={isinstance(stats, dict)}, len={len(stats)}")
    print(f"   Content: {stats}")
    
    print("\n4. Testing get_size_statistics()...")
    start = time.time()
    size_stats = qm.get_size_statistics()
    duration = time.time() - start
    print(f"   Duration: {duration:.4f}s")
    print(f"   Result Type: {type(size_stats)}")
    print(f"   Content: {size_stats}")

except Exception as e:
    print(f"\nFATAL ERROR: {e}")
    import traceback
    traceback.print_exc()
