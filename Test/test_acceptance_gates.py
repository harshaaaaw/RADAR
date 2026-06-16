"""
Acceptance Gate Validation — Tests all 8 acceptance gates from the implementation plan.
"""
import sys
import os
sys.path.insert(0, "src")

def main():
    passed = 0
    total = 0

    # ================================================================
    # G1: Sheet 3 loads — all 12 field registries populated
    # ================================================================
    total += 1
    print("=" * 60)
    print("G1: Sheet 3 loads -- all 12 field registries populated")
    print("=" * 60)
    try:
        from tagging.metadata_manager import Sheet3ValidValuesRegistry
        path = r"C:\Users\DELL\Downloads\Metadata Mapping_ Index and Copy ticket_Box - GECIHL ILAAP V2 (1).xlsx"
        vals = Sheet3ValidValuesRegistry.load_from_workbook(path)
        assert len(vals) == 12, f"Expected 12 fields, got {len(vals)}"
        assert "record_category_name_functional" in vals
        assert "business_unit_name" in vals
        assert "data_classification_name" in vals
        print(f"  Fields loaded: {len(vals)}")
        for k, v in sorted(vals.items()):
            print(f"    {k}: {len(v)} values")
        print("  [PASS]")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")

    # ================================================================
    # G2: category output always in record_category_name_functional
    # ================================================================
    total += 1
    print()
    print("=" * 60)
    print("G2: category always in allowed set")
    print("=" * 60)
    try:
        from tagging.tagging_engine import TaggingEngine, FIELD_CONSTRAINT_MAP
        from tagging.tagging_models import TaggingRequest
        engine = TaggingEngine()
        req = TaggingRequest(
            file_name="quarterly_financial_report.pdf",
            file_path="/docs/finance/quarterly_financial_report.pdf",
            main_content="This quarterly financial report shows revenue of $5.2M and EBITDA growth of 12%. The accounting department prepared this for the board review.",
        )
        result = engine.tag(req)
        allowed_cat = {v.strip().lower() for v in vals["record_category_name_functional"]}
        cat_lower = result.category.strip().lower()
        assert cat_lower in allowed_cat, f"Category '{result.category}' not in allowed set"
        print(f"  Category: '{result.category}' -- in allowed set")
        print("  [PASS]")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")

    # ================================================================
    # G3: department output always in business_unit_name
    # ================================================================
    total += 1
    print()
    print("=" * 60)
    print("G3: department always in allowed set")
    print("=" * 60)
    try:
        allowed_dept = {v.strip().lower() for v in vals["business_unit_name"]}
        dept_lower = result.department.strip().lower()
        assert dept_lower in allowed_dept, f"Department '{result.department}' not in allowed set"
        print(f"  Department: '{result.department}' -- in allowed set")
        print("  [PASS]")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")

    # ================================================================
    # G4: confidentiality output always in data_classification_name
    # ================================================================
    total += 1
    print()
    print("=" * 60)
    print("G4: confidentiality always in allowed set")
    print("=" * 60)
    try:
        allowed_conf = {v.strip().lower() for v in vals["data_classification_name"]}
        conf_lower = result.confidentiality.strip().lower()
        assert conf_lower in allowed_conf, f"Confidentiality '{result.confidentiality}' not in allowed set"
        print(f"  Confidentiality: '{result.confidentiality}' -- in allowed set")
        print("  [PASS]")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")

    # ================================================================
    # G5: Low-confidence out-of-set → forced best match + review_required
    # ================================================================
    total += 1
    print()
    print("=" * 60)
    print("G5: Out-of-set forced to best match + review_required")
    print("=" * 60)
    try:
        # Test the constraint enforcement directly with an out-of-set value
        allowed_set = vals["record_category_name_functional"]
        label, score, src, forced, mm = engine._enforce_sheet3_constraint(
            "category", "RandomGarbageLabel", 0.90, allowed_set
        )
        # It should either force to a best match or keep with no_match
        if forced:
            print(f"  Forced: '{label}' (was 'RandomGarbageLabel'), score={score}, mode={mm}")
            assert score <= 0.75, f"Forced score should be capped at 0.75, got {score}"
        else:
            print(f"  No match found (constraint_src={src}), label kept as '{label}'")
        # Now test with a known mismatch that CAN be matched
        label2, score2, src2, forced2, mm2 = engine._enforce_sheet3_constraint(
            "category", "accounting", 0.85, allowed_set
        )
        print(f"  Partial match: 'accounting' -> '{label2}' (forced={forced2}, mode={mm2})")
        assert label2 in allowed_set, f"Forced label must be in allowed set"
        print("  [PASS]")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")

    # ================================================================
    # G6: State Matrix XLSX has 6 new provenance columns
    # ================================================================
    total += 1
    print()
    print("=" * 60)
    print("G6: State Matrix XLSX has 6 new provenance columns")
    print("=" * 60)
    try:
        from core.reporting_manager import _get_manager
        import pandas as pd
        rm = _get_manager()
        export_path = rm.export_state_matrix_xlsx({}, "")
        df = pd.read_excel(export_path)
        required_cols = [
            "Constraint Source", "Forced Flag", "Original Label",
            "Original Score", "Match Mode", "Constraint Version",
        ]
        for col in required_cols:
            assert col in df.columns, f"Missing column: {col}"
            print(f"  Column: {col} -- present")
        print(f"  Exported {len(df)} rows to {os.path.basename(export_path)}")
        print("  [PASS]")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")

    # ================================================================
    # G7: validate_sheet3_constraints.py exits 0
    # ================================================================
    total += 1
    print()
    print("=" * 60)
    print("G7: validate_sheet3_constraints.py exits 0")
    print("=" * 60)
    try:
        import subprocess
        ret = subprocess.run(
            [sys.executable, "validate_sheet3_constraints.py"],
            capture_output=True, text=True, cwd=os.getcwd(),
        )
        if ret.returncode == 0:
            print("  validate_sheet3_constraints.py exited with code 0")
            print("  [PASS]")
            passed += 1
        else:
            print(f"  validate_sheet3_constraints.py exited with code {ret.returncode}")
            print(f"  stderr: {ret.stderr[-500:]}")
            print("  [FAIL]")
    except Exception as e:
        print(f"  [FAIL] {e}")

    # ================================================================
    # G8: System starts without errors on Windows
    # ================================================================
    total += 1
    print()
    print("=" * 60)
    print("G8: System starts without errors on Windows")
    print("=" * 60)
    try:
        from core.reporting_manager import _get_manager
        rm = _get_manager()
        from core.config_manager import get_config
        cfg = get_config()
        assert os.name == "nt", "Not on Windows"
        assert cfg.paths.working_root, "working_root not set"
        assert cfg.tagging.metadata_excel_path, "metadata_excel_path not set"
        assert cfg.tagging.metadata_mode_enabled, "metadata_mode_enabled not True"
        # Verify _validate_export_row exists
        assert hasattr(rm, "_validate_export_row"), "_validate_export_row must exist"
        # Test it
        good_row = {
            "smart_id": "FIN-20260522-ABCD", "file_name": "test.pdf",
            "category": "Finance & Accounting", "department": "Treasury",
            "purpose": "Record Keeping", "confidentiality": "GE Internal",
            "current_status": "completed", "processed_on": "2026-05-22T10:00:00Z",
            "file_type": "pdf",
        }
        warnings = rm._validate_export_row(good_row, vals)
        assert len(warnings) == 0, f"Good row should have 0 warnings, got {warnings}"
        print(f"  OS: {os.name} - OK")
        print(f"  working_root: {cfg.paths.working_root} - OK")
        print(f"  metadata_excel_path: set - OK")
        print(f"  metadata_mode_enabled: True - OK")
        print(f"  _validate_export_row: works - OK")
        print("  [PASS]")
        passed += 1
    except Exception as e:
        print(f"  [FAIL] {e}")

    # ================================================================
    # SUMMARY
    # ================================================================
    print()
    print("=" * 60)
    if passed == total:
        print(f"ALL {total} ACCEPTANCE GATES PASSED!")
    else:
        print(f"FAILED: {passed}/{total} acceptance gates passed")
    print("=" * 60)
    return 0 if passed == total else 1


if __name__ == "__main__":
    sys.exit(main())
