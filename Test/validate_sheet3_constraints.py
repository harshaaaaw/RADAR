import sys
import json
import sqlite3
from pathlib import Path

# Add src to python path so we can import project modules
sys.path.insert(0, str(Path(__file__).parent / "src"))

from core.config_manager import get_config
from core.logging_manager import get_logger
from core.reporting_manager import _ReportingManager
from tagging.metadata_manager import Sheet3ValidValuesRegistry

logger = get_logger("validation.sheet3")

def main():
    print("==================================================")
    print("Sheet 3 Valid-Values Constraint Enforcement Audit")
    print("==================================================")
    
    cfg = get_config()
    excel_path = getattr(cfg.tagging, "metadata_excel_path", "")
    if not excel_path or not Path(excel_path).exists():
        print(f"ERROR: Metadata Excel file not found at: {excel_path}")
        sys.exit(1)
        
    print(f"Loading Sheet 3 allowed values from: {excel_path}")
    registry = Sheet3ValidValuesRegistry.load_from_workbook(excel_path)
    if not registry:
        print("ERROR: Failed to load Sheet 3 valid values registry.")
        sys.exit(1)
        
    allowed_categories = registry.get("record_category_name_functional", set())
    allowed_departments = registry.get("business_unit_name", set())
    allowed_confidentialities = registry.get("data_classification_name", set())
    
    print(f"Loaded allowed values counts:")
    print(f"  - Record Category (Functional): {len(allowed_categories)}")
    print(f"  - Business Unit (Department):   {len(allowed_departments)}")
    print(f"  - Data Classification (Conf):    {len(allowed_confidentialities)}")
    
    rm = _ReportingManager()
    db_path = rm.db_path
    if not db_path.exists():
        print(f"WARNING: Audit database not found at {db_path}. No files processed yet.")
        print("PASS (No data to audit)")
        sys.exit(0)
        
    print(f"Reading file states from database: {db_path}")
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT file_key, smart_id, file_name, category, department, confidentiality, 
                   constraint_source, forced_flag, original_label, original_score, 
                   match_mode, constraint_version
            FROM file_state
            WHERE file_key NOT LIKE 'validation-%'
            """
        ).fetchall()
    except Exception as e:
        print(f"ERROR: Failed to read from file_state table: {e}")
        sys.exit(1)
    finally:
        conn.close()
        
    total_docs = len(rows)
    print(f"Total documents in database: {total_docs}")
    if total_docs == 0:
        print("PASS (No document states recorded yet)")
        sys.exit(0)
        
    violations = []
    forced_count = 0
    passed_count = 0
    no_match_count = 0
    empty_count = 0
    
    # Field mapping
    FIELD_REGISTRY_MAP = {
        "category": ("Category", allowed_categories),
        "department": ("Department", allowed_departments),
        "confidentiality": ("Confidentiality", allowed_confidentialities)
    }
    
    for row in rows:
        row_dict = dict(row)
        file_key = row_dict["file_key"]
        smart_id = row_dict["smart_id"]
        file_name = row_dict["file_name"]
        
        doc_forced = bool(row_dict["forced_flag"])
        if doc_forced:
            forced_count += 1
            
        c_src = row_dict["constraint_source"]
        if c_src == "sheet3_pass":
            passed_count += 1
        elif c_src == "sheet3_forced_best_match":
            # Count specifically if matching best-match
            pass
        elif c_src == "sheet3_no_match":
            no_match_count += 1
        elif c_src == "sheet3_empty":
            empty_count += 1
            
        # Validate each of the three fields
        doc_violations = []
        for field, (label, allowed_set) in FIELD_REGISTRY_MAP.items():
            val = row_dict[field]
            if not val:
                doc_violations.append(f"{label} is empty")
                continue
                
            # Exact match check
            if val not in allowed_set:
                doc_violations.append(f"{label} value '{val}' is not in Sheet 3 allowed set")
                
        if doc_violations:
            violations.append({
                "file_key": file_key,
                "smart_id": smart_id,
                "file_name": file_name,
                "violations": doc_violations,
                "row": row_dict
            })
            
    print("\n--------------------------------------------------")
    print("Audit Metrics Summary:")
    print(f"  - Total Documents Audited:   {total_docs}")
    print(f"  - Constraint Match Mode Pass: {passed_count}")
    print(f"  - Forced Best-Match Rows:    {forced_count}")
    print(f"  - Out-of-Set / No-Match Rows: {no_match_count}")
    print(f"  - Clean In-Set Compliance:   {total_docs - len(violations)} ({((total_docs - len(violations)) / total_docs * 100):.1f}%)")
    print(f"  - Total Non-Compliant Docs:  {len(violations)}")
    print("--------------------------------------------------")
    
    if violations:
        print("\nNon-Compliance Violations Details:")
        for idx, v in enumerate(violations[:10], 1):
            print(f"[{idx}] Doc: {v['file_name']} (SmartID: {v['smart_id']})")
            for dv in v["violations"]:
                print(f"    * {dv}")
            print(f"    * Constraint provenance: source={v['row']['constraint_source']}, forced={v['row']['forced_flag']}, match={v['row']['match_mode']}")
            
        if len(violations) > 10:
            print(f"... and {len(violations) - 10} more violations.")
            
        print("\nRESULT: FAILED (Violations found)")
        sys.exit(1)
    else:
        print("\nRESULT: PASSED (100% compliant with Sheet 3 allowed values)")
        sys.exit(0)

if __name__ == "__main__":
    main()
