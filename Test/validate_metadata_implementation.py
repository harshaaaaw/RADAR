"""
Real validation script for metadata-driven tagging implementation.

Runs point-by-point checks for:
1. Metadata source activation
2. Metadata-first tagging
3. No-metadata fallback tagging path
4. Strict non-empty export guarantees
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.config_manager import get_config_manager
from core.reporting_manager import FileStateRow, export_state_matrix_xlsx, upsert_file_state
from tagging.metadata_manager import clear_active_metadata_source, get_metadata_status, set_active_metadata_source
from tagging.tagging_engine import TaggingEngine
from tagging.tagging_models import TaggingRequest


def _ok(name: str, passed: bool, details: str) -> bool:
    marker = "PASS" if passed else "FAIL"
    print(f"[{marker}] {name}: {details}")
    return passed


def make_test_workbook(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df = pd.DataFrame(
        [
            {
                "File Name": "invoice_a.pdf",
                "Category": "Invoice",
                "Department": "Finance",
                "Purpose": "Payment",
                "Confidentiality": "Internal",
            },
            {
                "File Name": "policy_b.docx",
                "Category": "Policy",
                "Department": "Operations",
                "Purpose": "Reference",
                "Confidentiality": "Public",
            },
        ]
    )
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
        df.to_excel(writer, sheet_name="METADATA_MAPPING", index=False)


def validate() -> int:
    cfg_mgr = get_config_manager()
    cfg_mgr.ensure_directories()
    cfg = cfg_mgr.get_config()

    work_root = Path(cfg.paths.working_root)
    test_dir = work_root / "metadata" / "validation"
    workbook_path = test_dir / f"metadata_validation_{int(time.time())}.xlsx"
    make_test_workbook(workbook_path)

    checks: list[bool] = []

    # 1) Metadata input activation via CLI-priority source
    ok, msg = set_active_metadata_source(str(workbook_path), source="cli", force=True)
    status = get_metadata_status()
    checks.append(_ok("Metadata source activation", ok and status.get("active", False), f"{msg}; mode={status.get('mode')}, source={status.get('source')}"))

    # 2) Metadata-first tagging behavior
    engine = TaggingEngine()
    req_metadata = TaggingRequest(
        file_name="invoice_a.pdf",
        file_path="/tmp/invoice_a.pdf",
        main_content="",
        ocr_content="",
        embedded_content="",
        metadata={},
    )
    res_metadata = engine.tag(req_metadata)
    purpose_ok = str(res_metadata.purpose or "").strip().lower() in {
        "payment",
        "payment processing",
    }
    meta_pass = (
        res_metadata.category == "Invoice"
        and res_metadata.department == "Finance"
        and purpose_ok
        and res_metadata.metadata_mode == "metadata_mode"
    )
    checks.append(_ok("Metadata-first tagging", meta_pass, f"category={res_metadata.category}, dept={res_metadata.department}, purpose={res_metadata.purpose}, mode={res_metadata.metadata_mode}"))

    # 3) No-metadata mode fallback path
    clear_active_metadata_source()
    status_after_clear = get_metadata_status()
    req_no_metadata = TaggingRequest(
        file_name="unknown_file.txt",
        file_path="/tmp/unknown_file.txt",
        main_content="Invoice amount payment due and account reconciliation",
        ocr_content="",
        embedded_content="",
        metadata={},
    )
    res_no_metadata = engine.tag(req_no_metadata)
    no_meta_non_empty = all(
        str(v or "").strip()
        for v in [res_no_metadata.category, res_no_metadata.department, res_no_metadata.purpose]
    )
    checks.append(
        _ok(
            "No-metadata fallback tagging",
            (not status_after_clear.get("active", False)) and no_meta_non_empty,
            f"mode={res_no_metadata.metadata_mode}, category={res_no_metadata.category}, dept={res_no_metadata.department}, purpose={res_no_metadata.purpose}",
        )
    )

    # 4) Strict non-empty export validation
    row = FileStateRow(
        file_key=f"validation-{int(time.time())}",
        smart_id="",
        file_name="",
        category="",
        department="",
        purpose="",
        key_names="",
        amount_found="",
        important_dates="",
        location_mentioned="",
        confidentiality="",
        current_status="",
        processed_on="",
        file_type="",
        file_size=0,
        file_path="",
        source_stage="tagging",
        worker_id="validator",
    )
    upsert_file_state(row)
    export_path = export_state_matrix_xlsx(filters={}, out_path=str(work_root / "audit"))
    frame = pd.read_excel(export_path, keep_default_na=False)
    required_cols = [
        "Smart ID",
        "File Name",
        "Category",
        "Department",
        "Purpose",
        "Key Names",
        "Amount Found",
        "Important Dates",
        "Location Mentioned",
        "Confidentiality",
        "Current Status",
        "Processed On",
        "File Type",
        "File Size",
    ]
    subset = frame[required_cols].fillna("")
    has_blank = False
    for col in required_cols:
        if subset[col].astype(str).str.strip().eq("").any():
            has_blank = True
            break
    checks.append(_ok("Export non-empty guarantee", not has_blank, f"export={export_path}"))

    all_passed = all(checks)
    print("\nValidation summary:")
    print(f"Passed: {sum(1 for x in checks if x)} / {len(checks)}")
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(validate())
