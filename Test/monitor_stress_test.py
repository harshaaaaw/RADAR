import time
import sys

# Add src to path
sys.path.insert(0, 'src')
from core.redis_queue_manager import RedisQueueManager

def monitor():
    try:
        qm = RedisQueueManager()
        print("Monitoring Stress Test Progress...")
        print("-" * 80)
        print(f"{'Time':<10} | {'Discovered':<10} | {'Extraction':<10} | {'OCR':<10} | {'Indexed':<10} | {'Failed':<8}")
        print("-" * 80)
        
        start_time = time.time()
        last_indexed = -1
        stalled_count = 0
        
        while True:
            try:
                stats = qm.get_queue_statistics()
                
                disc = stats.get('discovery', {}).get('total', 0)
                
                # Extraction
                ext_stats = stats.get('extraction', {})
                ext_pen = 0
                ext_comp = 0
                for cat in ['tiny', 'small', 'medium', 'large']:
                    c = ext_stats.get(cat, {})
                    ext_pen += c.get('pending', 0)
                    ext_comp += c.get('completed', 0)
                
                # OCR
                ocr_stats = stats.get('ocr', {})
                ocr_pen = ocr_stats.get('pending', 0)
                ocr_comp = ocr_stats.get('completed', 0) # This is now updated correctly
                
                # Indexing
                idx_stats = stats.get('indexing', {})
                idx_comp = idx_stats.get('completed', 0)
                
                # Failed
                failed = stats.get('failed', {}).get('total', 0)
                
                elapsed = int(time.time() - start_time)
                
                print(f"{elapsed:<10} | {disc:<10} | {ext_comp:<10} | {ocr_comp:<10} | {idx_comp:<10} | {failed:<8}")
                
                # Completion check
                # Note: Discovered includes duplicates. Need to check uniqueness?
                # Total Work = Indexed + Failed
                # If everything found is processed.
                
                total_done = idx_comp + failed
                
                # If we have discovered files, and total done matches discovered count (assuming no duplicates filtered out silently)
                # But Bloom filter filters duplicates.
                # Discovered count in Redis increments even if duplicate? 
                # Let's assume unique files.
                # If idle for too long?
                
                if disc > 0 and total_done >= disc:
                    print("-" * 80)
                    print(f"COMPLETE! Processed {total_done}/{disc} files.")
                    break
                    
                if total_done == last_indexed and disc > 0:
                    stalled_count += 1
                    if stalled_count > 60: # 5 minutes stall
                        print("WARNING: System seems stalled.")
                        # break? No, keep watching.
                else:
                    stalled_count = 0
                    last_indexed = total_done
                
            except Exception as e:
                print(f"Monitor error: {e}")
                
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\nMonitoring stopped.")

if __name__ == "__main__":
    monitor()
