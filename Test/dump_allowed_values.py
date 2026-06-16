import sys
from pathlib import Path

# Add src to sys.path
sys.path.insert(0, str(Path("src").resolve()))

from tagging.metadata_manager import get_metadata_manager

mgr = get_metadata_manager()
snap = mgr.ensure_loaded()
if not snap:
    print("No snapshot loaded!")
else:
    if snap.sheet3_allowed_values and 'divestiture_deal_name' in snap.sheet3_allowed_values:
        deals = sorted(list(snap.sheet3_allowed_values['divestiture_deal_name']))
        print(f"Total deals: {len(deals)}")
        print("All deals:")
        for d in deals:
            print(f" - {d}")
    else:
        print("No divestiture_deal_name allowed values!")
