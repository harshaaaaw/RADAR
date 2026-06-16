#!/usr/bin/env python3
"""
Compliance Validation Script for the 12-Dimensional Taxonomy Engine.
Verifies that >=90% of documents have their core taxonomy dimensions populated
and that all populated values strictly conform to the allowed Sheet 3 registry.
"""
import sys
import os
import sqlite3
import json
from pathlib import Path

# Insert src directory to path
SYS_PATH = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SYS_PATH))

try:
    from core.config_manager import get_config
    os.chdir(Path(__file__).resolve().parent)
    cfg = get_config()
    DB_PATH = Path(cfg.paths.working_root) / "audit" / "audit.db"
    EXCEL_PATH = getattr(cfg.tagging, "metadata_excel_path", "")
except Exception:
    DB_PATH = Path(__file__).resolve().parent / "runtime" / "audit" / "audit.db"
    EXCEL_PATH = r"C:\Users\DELL\Downloads\Metadata Mapping_ Index and Copy ticket_Box - GECIHL ILAAP V2 (1).xlsx"

if not EXCEL_PATH or not Path(EXCEL_PATH).exists():
    EXCEL_PATH = r"C:\Users\DELL\Downloads\Metadata Mapping_ Index and Copy ticket_Box - GECIHL ILAAP V2 (1).xlsx"

from tagging.metadata_manager import Sheet3ValidValuesRegistry

# Core 11 Non-Reserved Taxonomy Dimensions to Validate
TAXONOMY_DIMENSIONS = [
    "metadata_level_code",
    "record_class_name",
    "record_category_name_functional",
    "record_type_code",
    "business_unit_name",
    "sub_business_unit_name",
    "iso_country_code",
    "record_format_name",
    "original_record_location_type_name",
    "data_classification_name",
    "divestiture_deal_name",
]

CORE_REQUIRED_DIMENSIONS = [
    "metadata_level_code",
    "record_class_name",
    "record_category_name_functional",
    "business_unit_name",
    "record_format_name",
    "original_record_location_type_name",
    "data_classification_name",
]


def print_colored_header(title: str):
    print("=" * 75)
    print(f" {title.upper()} ".center(75, "="))
    print("=" * 75)


def run_validation(json_output: bool = False) -> int:
    if not DB_PATH.exists():
        print(f"Error: Database file not found at {DB_PATH}", file=sys.stderr)
        return 1

    # Load Sheet 3 Allowed Registry
    if not Path(EXCEL_PATH).exists():
        print(f"Error: Sheet 3 Workbook not found at {EXCEL_PATH}", file=sys.stderr)
        return 1

    registry = Sheet3ValidValuesRegistry.load_from_workbook(EXCEL_PATH)
    if not registry:
        print("Error: Failed to load Sheet 3 Valid Values Registry.", file=sys.stderr)
        return 1

    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM file_state WHERE current_status != 'deleted'")
        total_records = cursor.fetchone()[0]
    except sqlite3.OperationalError as exc:
        print(f"Database error: {exc}", file=sys.stderr)
        conn.close()
        return 1

    if total_records == 0:
        print("No documents found in the database to validate.")
        conn.close()
        return 0

    cursor.execute("SELECT * FROM file_state WHERE current_status != 'deleted'")
    rows = cursor.fetchall()

    # Track population and validity counts
    dimension_populated = {dim: 0 for dim in TAXONOMY_DIMENSIONS}
    dimension_valid = {dim: 0 for dim in TAXONOMY_DIMENSIONS}
    
    document_scores = []
    strictly_compliant_docs = 0
    invalid_cells_details = []

    for row in rows:
        populated_count = 0
        core_populated_count = 0
        row_dict = dict(row)
        file_name = row_dict.get("file_name", "unknown")
        smart_id = row_dict.get("smart_id", "unknown")

        for dim in TAXONOMY_DIMENSIONS:
            val = row_dict.get(dim)
            if val is not None and str(val).strip() != "":
                dimension_populated[dim] += 1
                populated_count += 1
                if dim in CORE_REQUIRED_DIMENSIONS:
                    core_populated_count += 1

                # Validation check against registry
                allowed = registry.get(dim, set())
                val_str = str(val).strip()
                
                # Check if the field supports comma-separated list
                if dim in ["iso_country_code", "divestiture_deal_name"]:
                    parts = [p.strip() for p in val_str.split(",") if p.strip()]
                    is_valid = True
                    for part in parts:
                        if part not in allowed:
                            is_valid = False
                            invalid_cells_details.append({
                                "smart_id": smart_id,
                                "file_name": file_name,
                                "dimension": dim,
                                "invalid_value": part,
                                "context": f"Part '{part}' of '{val_str}' not in allowed registry"
                            })
                    if is_valid and parts:
                        dimension_valid[dim] += 1
                else:
                    if val_str in allowed:
                        dimension_valid[dim] += 1
                    else:
                        invalid_cells_details.append({
                            "smart_id": smart_id,
                            "file_name": file_name,
                            "dimension": dim,
                            "invalid_value": val_str,
                            "context": f"Value not in allowed registry"
                        })

        # Calculate percentage for this document
        doc_pct = populated_count / len(TAXONOMY_DIMENSIONS)
        document_scores.append(doc_pct)

        # Document is strictly compliant if all 7 core required dimensions are populated
        if core_populated_count == len(CORE_REQUIRED_DIMENSIONS):
            strictly_compliant_docs += 1

    conn.close()

    # Calculate aggregate metrics
    overall_cells_populated = sum(dimension_populated.values())
    overall_cells_valid = sum(dimension_valid.values())
    
    total_possible_cells = total_records * len(TAXONOMY_DIMENSIONS)
    
    cell_population_rate = overall_cells_populated / total_possible_cells if total_possible_cells > 0 else 0.0
    cell_valid_rate = overall_cells_valid / overall_cells_populated if overall_cells_populated > 0 else 0.0
    
    avg_doc_population = sum(document_scores) / len(document_scores) if document_scores else 0.0
    compliant_docs_count = sum(1 for score in document_scores if score >= 0.70)
    compliance_rate = compliant_docs_count / total_records if total_records > 0 else 0.0
    strict_compliance_rate = strictly_compliant_docs / total_records if total_records > 0 else 0.0

    if json_output:
        results = {
            "total_documents": total_records,
            "overall_cell_population_rate": round(cell_population_rate, 4),
            "overall_cell_valid_rate": round(cell_valid_rate, 4),
            "average_document_population_rate": round(avg_doc_population, 4),
            "compliance_rate_70pct": round(compliance_rate, 4),
            "strict_compliance_rate": round(strict_compliance_rate, 4),
            "invalid_cells_count": len(invalid_cells_details),
            "dimension_stats": {
                dim: {
                    "populated_count": dimension_populated[dim],
                    "populated_percentage": round(dimension_populated[dim] / total_records, 4),
                    "valid_count": dimension_valid[dim],
                    "valid_percentage": round(dimension_valid[dim] / dimension_populated[dim], 4) if dimension_populated[dim] > 0 else 1.0
                } for dim in TAXONOMY_DIMENSIONS
            }
        }
        print(json.dumps(results, indent=2))
        return 0 if cell_population_rate >= 0.90 else 1

    # Gorgeous Console Output
    print_colored_header("12-Dimension Taxonomy Compliance & Population Report")
    print(f"Database Path:   {DB_PATH}")
    print(f"Registry Path:   {EXCEL_PATH}")
    print(f"Total Documents: {total_records}")
    print("-" * 75)
    
    print(f"{'TAXONOMY DIMENSION':<38} | {'POPULATED':<10} | {'POP %':<8} | {'VALID':<8} | {'VALID %':<8}")
    print("-" * 75)
    for dim in TAXONOMY_DIMENSIONS:
        pop_count = dimension_populated[dim]
        val_count = dimension_valid[dim]
        
        pop_pct = (pop_count / total_records * 100) if total_records > 0 else 0.0
        val_pct = (val_count / pop_count * 100) if pop_count > 0 else 100.0
        
        req_flag = " [Core]" if dim in CORE_REQUIRED_DIMENSIONS else ""
        print(f"{dim + req_flag:<38} | {pop_count:<10d} | {pop_pct:>6.1f}% | {val_count:<8d} | {val_pct:>6.1f}%")
    print("-" * 75)

    print_colored_header("Compliance Metrics & Targets")
    print(f"1. Cell-Level Population Rate:         {cell_population_rate * 100:.2f}% (Target: >= 90.00%)")
    print(f"2. Populated Cell Validity Rate:       {cell_valid_rate * 100:.2f}%")
    print(f"3. Average Document Population Rate:    {avg_doc_population * 100:.2f}%")
    print(f"4. Document Compliance (>=70% populated): {compliance_rate * 100:.2f}%")
    print(f"5. Strict Core-Required Compliance:     {strict_compliance_rate * 100:.2f}%")
    print("-" * 75)

    if invalid_cells_details:
        print("\n" + " INVALID CELL ENTRIES DETECTED ".center(75, "!"))
        for idx, item in enumerate(invalid_cells_details[:10], 1):
            print(f"[{idx}] SmartID: {item['smart_id']} | File: {item['file_name']}")
            print(f"    Dimension '{item['dimension']}' contains invalid value: '{item['invalid_value']}'")
            print(f"    Context: {item['context']}")
        if len(invalid_cells_details) > 10:
            print(f"... and {len(invalid_cells_details) - 10} more invalid entries.")
        print("-" * 75)

    # Threshold Check
    target_met = cell_population_rate >= 0.90
    if target_met and len(invalid_cells_details) == 0:
        print("STATUS: COMPLIANT (Target >= 90% Met & 100% Valid) [OK]")
        exit_code = 0
    elif target_met:
        print("STATUS: COMPLIANT WITH WARNINGS (Target >= 90% Met, but has invalid values) [WARNING]")
        exit_code = 0
    else:
        print("STATUS: NON-COMPLIANT (Target >= 90% Not Met) [FAIL]")
        exit_code = 1
    print("=" * 75)

    return exit_code


if __name__ == "__main__":
    use_json = "--json" in sys.argv
    sys.exit(run_validation(use_json))
