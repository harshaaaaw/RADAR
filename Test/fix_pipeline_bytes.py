"""Fix the 1.10 KB In Pipeline discrepancy caused by race-condition duplicate."""
import redis

r = redis.Redis(decode_responses=True)

# Current state
print("BEFORE FIX:")
print(f"  discovered:      {r.get('docsearch:counter:discovered')}")
print(f"  discovered_bytes:{r.get('docsearch:counter:discovered_bytes')}")
print(f"  extraction_completed: {r.get('docsearch:counter:extraction_completed')}")
print(f"  root_completed:  {r.get('docsearch:counter:root_completed')}")
print(f"  completed_bytes: {r.get('docsearch:counter:completed_bytes')}")

# Fix: decrement discovered counters by the duplicate's contribution
r.decrby('docsearch:counter:discovered', 1)        # 76 -> 75
r.decrby('docsearch:counter:discovered_bytes', 1130) # 71467 -> 70337
r.decrby('docsearch:counter:extraction_completed', 1) # 76 -> 75

print("\nAFTER FIX:")
print(f"  discovered:      {r.get('docsearch:counter:discovered')}")
print(f"  discovered_bytes:{r.get('docsearch:counter:discovered_bytes')}")
print(f"  extraction_completed: {r.get('docsearch:counter:extraction_completed')}")
print(f"  root_completed:  {r.get('docsearch:counter:root_completed')}")
print(f"  completed_bytes: {r.get('docsearch:counter:completed_bytes')}")

# Verify delta is now 0
d = int(r.get('docsearch:counter:discovered_bytes') or 0)
c = int(r.get('docsearch:counter:completed_bytes') or 0)
print(f"\n  in_pipeline bytes: {d - c} (should be 0)")
print(f"  in_pipeline files: {int(r.get('docsearch:counter:discovered') or 0) - int(r.get('docsearch:counter:root_completed') or 0)} (should be 0)")
