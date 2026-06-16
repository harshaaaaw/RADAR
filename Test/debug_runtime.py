
import sys
import time
from pathlib import Path

# Add src to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from ui.dashboard_state import get_dashboard_stats_runtime
from core.queue_manager import get_queue_manager

print("Checking Dashboard Stats Runtime...")
runtime = get_dashboard_stats_runtime()

# Wait a few seconds for first fetch
print("Waiting 5 seconds for background fetch...")
time.sleep(5)

health = runtime.health()
print(f"Runtime Health: {health}")

queue_stats = runtime.get_queue_stats()
size_stats = runtime.get_size_stats()

print(f"Queue Stats: {queue_stats}")
print(f"Size Stats: {size_stats}")

if not queue_stats:
    print("WARNING: Queue stats are empty!")
    # Test direct fetch
    try:
        qm = get_queue_manager()
        print("Testing direct fetch from Redis...")
        direct_qs = qm.get_queue_statistics()
        print(f"Direct Queue Stats: {direct_qs}")
    except Exception as e:
        print(f"Direct fetch failed: {e}")

if not size_stats:
    print("WARNING: Size stats are empty!")
    try:
        qm = get_queue_manager()
        print("Testing direct fetch of size stats...")
        direct_ss = qm.get_size_statistics()
        print(f"Direct Size Stats: {direct_ss}")
    except Exception as e:
        print(f"Direct size fetch failed: {e}")
