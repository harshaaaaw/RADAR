import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path("src").resolve()))

from tagging.metadata_manager import get_metadata_manager

def main():
    mgr = get_metadata_manager()
    snap = mgr.ensure_loaded()
    if not snap or not snap.sheet3_allowed_values or 'record_type_code' not in snap.sheet3_allowed_values:
        print("Failed to load record_type_code from Sheet 3 registry")
        return
        
    codes = sorted(list(snap.sheet3_allowed_values['record_type_code']))
    print(f"Total allowed record_type_code values: {len(codes)}")
    for i, code in enumerate(codes, 1):
        print(f"{i:3d}. {code}")

if __name__ == '__main__':
    main()
