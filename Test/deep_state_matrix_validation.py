"""
Deep State Matrix validation script.

Checks:
1. End-to-end queue completion and zero failures.
2. State Matrix export integrity vs audit DB.
3. Required-column non-empty strictness.
4. Re-tag consistency from OpenSearch source content.
5. Metadata matching coverage and expected-tag alignment.
"""

from __future__ import annotations

import collections
import json
import sqlite3
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from core.config_manager import get_config_manager
from core.queue_manager import get_queue_manager
from core.reporting_manager import export_state_matrix_xlsx
from indexing.opensearch_client import OpenSearchClient
from tagging.metadata_manager import get_metadata_manager, get_metadata_status
from tagging.tagging_engine import TaggingEngine
from tagging.tagging_models import TaggingRequest


TITLE_MAP = {
    "smart_id": "Smart ID",
    "file_name": "File Name",
    "category": "Category",
    "department": "Department",
    "purpose": "Purpose",
    "key_names": "Key Names",
    "amount_found": "Amount Found",
    "important_dates": "Important Dates",
    "location_mentioned": "Location Mentioned",
    "confidentiality": "Confidentiality",
    "current_status": "Current Status",
    "processed_on": "Processed On",
    "file_type": "File Type",
    "file_size": "File Size",
}


def norm(v: Any) -> str:
    if v is None:
        return ""
    return " ".join(str(v).strip().split())


def row_to_tuple(row: Dict[str, Any], ordered_cols: List[str]) -> Tuple[str, ...]:
    return tuple(norm(row.get(col, "")) for col in ordered_cols)


def load_file_state_rows(audit_db: Path) -> List[Dict[str, Any]]:
    conn = sqlite3.connect(str(audit_db))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            """
            SELECT
                smart_id, file_name, category, department, purpose,
                key_names, amount_found, important_dates, location_mentioned,
                confidentiality, current_status, processed_on, file_type, file_size,
                file_path, confidence_json
            FROM file_state
            ORDER BY updated_at DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def fetch_doc_for_state_row(
    os_client: OpenSearchClient,
    smart_id: str,
    file_name: str,
    file_path: str,
) -> Dict[str, Any]:
    must = [{"term": {"smart_id": smart_id}}]
    should: List[Dict[str, Any]] = []
    if file_name:
        should.append({"term": {"file_name.keyword": file_name}})
        should.append({"term": {"file_name": file_name}})
    if file_path:
        should.append({"term": {"file_path.keyword": file_path}})
        should.append({"term": {"file_path": file_path}})

    query: Dict[str, Any] = {"bool": {"must": must}}
    if should:
        query["bool"]["should"] = should
        query["bool"]["minimum_should_match"] = 1

    body = {
        "size": 3,
        "query": query,
        "_source": [
            "file_name",
            "file_path",
            "file_hash",
            "file_type",
            "mime_type",
            "main_content",
            "ocr_content",
            "embedded_content",
            "metadata",
            "smart_id",
            "file_size",
        ],
    }
    try:
        resp = os_client.client.search(index=os_client.index_name, body=body)
        hits = resp.get("hits", {}).get("hits", [])
        if not hits:
            return {}

        # Prefer exact file_name and file_path when duplicates exist for a smart_id.
        for hit in hits:
            src = hit.get("_source", {}) or {}
            if norm(src.get("file_name", "")) == norm(file_name) and norm(src.get("file_path", "")) == norm(file_path):
                return src
        for hit in hits:
            src = hit.get("_source", {}) or {}
            if norm(src.get("file_name", "")) == norm(file_name):
                return src
        return (hits[0].get("_source", {}) or {})
    except Exception:
        return {}


def main() -> int:
    cfg_mgr = get_config_manager()
    cfg_mgr.ensure_directories()
    cfg = cfg_mgr.get_config()

    qm = get_queue_manager()
    qstats = qm.get_queue_statistics() or {}

    # Completion checks
    discovery = qstats.get("discovery", {})
    extraction = qstats.get("extraction_total", {})
    indexing = qstats.get("indexing", {})
    tagging = qstats.get("tagging", {})
    failures = int(qstats.get("total_failures", 0) or 0)

    completion_ok = all(
        int(stage.get("pending", 0) or 0) == 0 and int(stage.get("processing", 0) or 0) == 0
        for stage in (discovery, extraction, indexing, tagging)
    )

    # Export fresh state matrix
    out_dir = str(Path(cfg.paths.working_root) / "audit")
    export_path = Path(export_state_matrix_xlsx(filters={}, out_path=out_dir))
    export_df = pd.read_excel(export_path).fillna("")

    required_snake = list(getattr(cfg.tagging, "required_non_empty_export_columns", []) or list(TITLE_MAP.keys()))
    required_titles = [TITLE_MAP[c] for c in required_snake if c in TITLE_MAP]

    # 1) Non-empty strictness
    non_empty_cells = {}
    total_blank = 0
    for col in required_titles:
        blank = int(export_df[col].astype(str).str.strip().eq("").sum()) if col in export_df.columns else len(export_df)
        non_empty_cells[col] = blank
        total_blank += blank

    # 2) Export vs DB accuracy
    audit_db = Path(cfg.paths.working_root) / "audit" / "audit.db"
    db_rows = load_file_state_rows(audit_db)

    ordered_titles = [TITLE_MAP[c] for c in TITLE_MAP.keys()]
    export_rows = [
        {col: row.get(col, "") for col in ordered_titles}
        for row in export_df.to_dict(orient="records")
    ]

    db_projected = []
    for r in db_rows:
        db_projected.append(
            {
                "Smart ID": r.get("smart_id", ""),
                "File Name": r.get("file_name", ""),
                "Category": r.get("category", ""),
                "Department": r.get("department", ""),
                "Purpose": r.get("purpose", ""),
                "Key Names": r.get("key_names", ""),
                "Amount Found": r.get("amount_found", ""),
                "Important Dates": r.get("important_dates", ""),
                "Location Mentioned": r.get("location_mentioned", ""),
                "Confidentiality": r.get("confidentiality", ""),
                "Current Status": r.get("current_status", ""),
                "Processed On": r.get("processed_on", ""),
                "File Type": r.get("file_type", ""),
                "File Size": r.get("file_size", ""),
            }
        )

    export_counter = collections.Counter(row_to_tuple(r, ordered_titles) for r in export_rows)
    db_counter = collections.Counter(row_to_tuple(r, ordered_titles) for r in db_projected)
    export_db_exact_match = export_counter == db_counter

    # 3) Re-tag consistency and metadata coverage
    engine = TaggingEngine()
    os_client = OpenSearchClient()
    mdm = get_metadata_manager()

    retag_total = 0
    retag_match = 0
    metadata_matched = 0
    metadata_expected_checks = 0
    metadata_expected_match = 0
    source_counts = collections.Counter()

    for r in db_rows:
        smart_id = str(r.get("smart_id", "") or "").strip()
        if not smart_id:
            continue

        # Source attribution from stored confidence json
        try:
            cj = json.loads(str(r.get("confidence_json", "") or "{}"))
            if isinstance(cj, dict):
                for field in ("category", "department", "purpose"):
                    src = str((cj.get(field, {}) or {}).get("source", "") or "")
                    if src:
                        source_counts[src] += 1
        except Exception:
            pass

        src_doc = fetch_doc_for_state_row(
            os_client=os_client,
            smart_id=smart_id,
            file_name=str(r.get("file_name", "") or ""),
            file_path=str(r.get("file_path", "") or ""),
        )
        if not src_doc:
            continue

        req = TaggingRequest(
            file_name=str(src_doc.get("file_name", "") or ""),
            file_path=str(src_doc.get("file_path", "") or ""),
            file_hash=str(src_doc.get("file_hash", "") or ""),
            file_type=str(src_doc.get("file_type", "") or ""),
            mime_type=str(src_doc.get("mime_type", "") or ""),
            main_content=str(src_doc.get("main_content", "") or ""),
            ocr_content=str(src_doc.get("ocr_content", "") or ""),
            embedded_content=str(src_doc.get("embedded_content", "") or ""),
            metadata=src_doc.get("metadata", {}) if isinstance(src_doc.get("metadata"), dict) else {},
        )

        retag = engine.tag(req)
        retag_total += 1
        if (
            norm(retag.category) == norm(r.get("category", ""))
            and norm(retag.department) == norm(r.get("department", ""))
            and norm(retag.purpose) == norm(r.get("purpose", ""))
            and norm(retag.confidentiality) == norm(r.get("confidentiality", ""))
        ):
            retag_match += 1

        md_ctx = mdm.resolve_tags(req)
        if md_ctx.get("matched", False):
            metadata_matched += 1

            # For explicit/derived expected values, output should match canonicalized expectation where provided.
            for field in ("category", "department", "purpose"):
                expected = str(md_ctx.get("explicit", {}).get(field, "") or "")
                if not expected:
                    expected = str(md_ctx.get("derived", {}).get(field, "") or "")
                if not expected:
                    continue
                canonical = engine.taxonomy.canonicalize_label(field, expected)
                if not canonical:
                    continue
                metadata_expected_checks += 1
                if norm(canonical) == norm(r.get(field, "")):
                    metadata_expected_match += 1

    retag_rate = (retag_match / retag_total) if retag_total else 0.0
    metadata_expected_rate = (metadata_expected_match / metadata_expected_checks) if metadata_expected_checks else 1.0

    metadata_status = get_metadata_status()

    summary = {
        "metadata_status": metadata_status,
        "completion_ok": completion_ok,
        "total_failures": failures,
        "export_path": str(export_path),
        "row_count_export": int(len(export_df)),
        "row_count_db": int(len(db_projected)),
        "required_column_blank_counts": non_empty_cells,
        "total_required_blank_cells": int(total_blank),
        "export_db_exact_match": bool(export_db_exact_match),
        "retag_consistency_rate": round(float(retag_rate), 6),
        "retag_total_checked": int(retag_total),
        "metadata_matched_docs": int(metadata_matched),
        "metadata_expected_checks": int(metadata_expected_checks),
        "metadata_expected_match_rate": round(float(metadata_expected_rate), 6),
        "source_counts": dict(source_counts),
    }

    # Strict pass criteria for this deep validation run.
    checks = {
        "queues_completed": completion_ok,
        "zero_failures": failures == 0,
        "no_blank_required_cells": total_blank == 0,
        "export_equals_db": export_db_exact_match,
        "retag_consistent": retag_rate == 1.0,
        "metadata_effect_present": metadata_matched > 0,
        "metadata_expected_alignment": metadata_expected_rate == 1.0,
    }

    summary["checks"] = checks
    summary["all_passed"] = all(checks.values())

    summary_path = Path(cfg.paths.working_root) / "audit" / "deep_state_validation_latest.json"
    summary["summary_path"] = str(summary_path)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print(json.dumps(summary, indent=2))
    return 0 if summary["all_passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
