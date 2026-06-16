"""Export a fresh State Matrix Excel after retagging."""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "src"))

from core.reporting_manager import export_state_matrix_xlsx

out_path = r"state_matrix_RETAGGED.xlsx"
result = export_state_matrix_xlsx(filters=None, out_path=out_path)
print(f"Exported to: {result}")
