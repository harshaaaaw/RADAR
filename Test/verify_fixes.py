
import os

def check_file_content(path, must_contain, must_not_contain=None):
    print(f"Checking {os.path.basename(path)}...")
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        all_passed = True
        for item in must_contain:
            if item not in content:
                print(f"  [FAIL] Missing: {item}")
                all_passed = False
            else:
                print(f"  [PASS] Found: {item[:50]}...")
                
        if must_not_contain:
            for item in must_not_contain:
                if item in content:
                    print(f"  [FAIL] Found forbidden: {item}")
                    all_passed = False
                else:
                    print(f"  [PASS] Forbidden not found: {item}")
                    
        return all_passed
    except Exception as e:
        print(f"  [ERROR] Could not read file: {e}")
        return False

def verify_fixes():
    base_dir = r"c:\Users\DELL\Downloads\DocumentSearch_v5\DocumentSearch\src"
    
    # 1. Indexing Worker Fix
    indexing_worker = os.path.join(base_dir, "indexing", "indexing_worker.py")
    if not check_file_content(
        indexing_worker, 
        must_contain=["def _heartbeat_loop(self)"],
        must_not_contain=["self.running = False\n    \n    def get_stats"] # The bug was self.running=False after loop
    ):
        print("Wait, checking specific heartbeat loop content...")
        with open(indexing_worker, 'r') as f:
            if "while self.running:" in f.read() and "self.running = False" not in f.read().split("_heartbeat_loop")[1].split("get_stats")[0]:
                 print("  [PASS] Heartbeat loop looks correct (no self.running=False after loop)")
            else:
                 print("  [WARN] Manual check of heartbeat loop needed")

    # 2. Search API Fix
    search_api = os.path.join(base_dir, "api", "search_api.py")
    check_file_content(
        search_api,
        must_contain=["# Cleanup stale IPs occasionally", "if len(_rate_limit_store) > 10000:"]
    )

    # 3. Zip Bomb Fix
    extraction_worker = os.path.join(base_dir, "extraction", "extraction_worker.py")
    check_file_content(
        extraction_worker,
        must_contain=["MAX_TOTAL_SIZE = 1 * 1024 * 1024 * 1024", "Zip Bomb Check", "total_extracted_bytes + info.file_size"]
    )

    # 4. M8 Startup Fix
    master = os.path.join(base_dir, "orchestrator", "master_orchestrator.py")
    check_file_content(
        master,
        must_contain=["recovery_thread = threading.Thread", "target=self.recovery_manager.recover_all", "daemon=True"]
    )

    # 5. M9 SQLite Fix
    queue = os.path.join(base_dir, "core", "queue_manager.py")
    check_file_content(
        queue,
        must_contain=["TABLE_SYSTEM_FLAGS = 'system_flags'", "INSERT OR REPLACE INTO {TABLE_SYSTEM_FLAGS}", "discovery_force_run"]
    )
    
    print("\nVerification Complete.")

if __name__ == "__main__":
    verify_fixes()
