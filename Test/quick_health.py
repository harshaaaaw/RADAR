"""Quick check: is the system running and healthy?"""
import redis
r = redis.Redis()

# Check stats
stats = {k.decode():v.decode() for k,v in r.hgetall('docsearch:stats').items()}

print("="*60)
print("SYSTEM HEALTH CHECK")
print("="*60)

# Key metrics
total_discovered = int(stats.get('total_discovered', 0))
total_indexed = int(stats.get('total_indexed', 0))
total_extracted = int(stats.get('total_extracted', 0))
total_ocr = int(stats.get('total_ocr_completed', 0))

print(f"Discovered: {total_discovered}")
print(f"Extracted:  {total_extracted}")
print(f"Indexed:    {total_indexed}")
print(f"OCR done:   {total_ocr}")

# Queue sizes
qs = {
    'extraction': r.llen('docsearch:queue:extraction'),
    'indexing': r.llen('docsearch:queue:indexing'),
    'ocr': r.llen('docsearch:queue:ocr'),
    'tagging': r.llen('docsearch:queue:tagging'),
}
print(f"\nQueue sizes: {qs}")

# Processing keys (active work)
processing = len(r.keys('docsearch:processing:*'))
print(f"Active processing keys: {processing}")

# Check if orchestrator is paused
if r.exists('docsearch:resource_paused'):
    print("\n!!! RESOURCE PAUSED FLAG SET !!!")
else:
    print("\nResource paused flag: NOT set (good)")

print("\nSystem appears RUNNING" if processing > 0 or any(v > 0 for v in qs.values()) else "\nSystem appears IDLE")
print("="*60)
