"""Validate worker heartbeats – checks that all workers are alive and reporting."""
import sys
import time
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent / 'src'))

from core.queue_manager import get_queue_manager

STALE_THRESHOLD_SEC = 60  # consider stale if no heartbeat for 60s

def main():
    qm = get_queue_manager()
    heartbeats = qm.get_worker_heartbeats()

    if not heartbeats:
        print("⚠️  No worker heartbeats found in Redis.")
        print("   Workers may not be running, or they haven't started yet.")
        return

    now = time.time()
    print(f"{'Worker ID':<45} {'Last Beat':<25} {'Age (s)':<10} Status")
    print("-" * 100)

    alive = 0
    stale = 0
    for worker_id, ts in sorted(heartbeats.items(), key=lambda x: x[1], reverse=True):
        age = now - ts
        dt = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
        status = "✅ ALIVE" if age < STALE_THRESHOLD_SEC else "❌ STALE"
        if age < STALE_THRESHOLD_SEC:
            alive += 1
        else:
            stale += 1
        print(f"{worker_id:<45} {dt:<25} {age:>8.1f}   {status}")

    print("-" * 100)
    print(f"Total workers: {len(heartbeats)}  |  Alive: {alive}  |  Stale: {stale}")

    # Check expected worker types
    expected = {'discovery', 'extraction', 'indexing', 'ocr'}
    present = set()
    for wid in heartbeats:
        for prefix in expected:
            if prefix in wid.lower():
                present.add(prefix)

    missing = expected - present
    if missing:
        print(f"\n⚠️  Missing worker types (no heartbeats): {', '.join(sorted(missing))}")
    else:
        print(f"\n✅ All expected worker types have heartbeats: {', '.join(sorted(present))}")


if __name__ == '__main__':
    main()
