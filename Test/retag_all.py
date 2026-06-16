"""
Re-tag all documents in OpenSearch using the current TaggingEngine + taxonomy.
Does NOT require the pipeline or tagging worker to be running.

Usage:
    python retag_all.py              # retag all documents
    python retag_all.py --dry-run    # preview without writing
    python retag_all.py --limit 5    # retag first 5 only
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

# Ensure src/ is on the path
sys.path.insert(0, str(Path(__file__).resolve().parent / "src"))

from core.config_manager import get_config
from core.logging_manager import get_logger, setup_logging
from core.reporting_manager import upsert_file_state, FileStateRow, derive_file_key
from indexing.opensearch_client import OpenSearchClient
from tagging.tagging_engine import TaggingEngine
from tagging.tagging_models import TaggingRequest

setup_logging()
logger = get_logger("retag_all")

# Fields to fetch from OpenSearch for tagging input
SOURCE_FIELDS = [
    "file_name", "file_path", "file_hash", "file_type", "mime_type",
    "main_content", "ocr_content", "embedded_content", "metadata",
    "smart_id", "file_size",
]


def retag_all(dry_run: bool = False, limit: int = 0) -> dict:
    """Re-tag every document in the index."""
    os_client = OpenSearchClient()
    if not os_client.wait_for_availability(timeout_seconds=30):
        print("ERROR: OpenSearch is not available.")
        return {"error": "OpenSearch unavailable"}

    engine = TaggingEngine()
    index_name = os_client.index_name

    processed = 0
    updated = 0
    failed = 0
    search_after = None

    print(f"Re-tagging documents in index '{index_name}' ...")
    print(f"  Dry-run: {dry_run}")
    print(f"  Limit:   {limit or 'all'}")
    print(f"  Engine:  {engine.tagger_version}")
    print(f"  Taxonomy version: {engine.taxonomy.get_snapshot().version_id}")
    print()

    t0 = time.time()

    while True:
        body = {
            "size": 50,
            "sort": [{"_doc": "asc"}],
            "_source": SOURCE_FIELDS,
            "query": {"match_all": {}},
        }
        if search_after is not None:
            body["search_after"] = search_after

        response = os_client.client.search(index=index_name, body=body)
        hits = response.get("hits", {}).get("hits", [])
        if not hits:
            break

        for hit in hits:
            doc_id = hit["_id"]
            src = hit.get("_source", {}) or {}

            file_name = str(src.get("file_name", "") or "")
            file_path = str(src.get("file_path", "") or "")
            file_hash = str(src.get("file_hash", "") or "")
            file_type = str(src.get("file_type", "") or "")
            mime_type = str(src.get("mime_type", "") or "")

            req = TaggingRequest(
                file_id=0,
                file_path=file_path,
                file_name=file_name,
                file_hash=file_hash,
                doc_id=doc_id,
                file_type=file_type,
                mime_type=mime_type,
                main_content=str(src.get("main_content", "") or ""),
                ocr_content=str(src.get("ocr_content", "") or ""),
                embedded_content=str(src.get("embedded_content", "") or ""),
                metadata=src.get("metadata", {}) if isinstance(src.get("metadata"), dict) else {},
            )

            try:
                result = engine.tag(req)
                update_fields = result.to_document_update()

                # Preserve existing smart_id
                existing_smart_id = str(src.get("smart_id", "") or "")
                if existing_smart_id:
                    update_fields["smart_id"] = existing_smart_id

                processed += 1

                if dry_run:
                    print(f"  [DRY-RUN] {doc_id}: {file_name}")
                    print(f"    category={result.category}  department={result.department}  "
                          f"purpose={result.purpose}  confidence={result.tag_confidence_overall:.2f}")
                    print(f"    key_names={result.key_names}  amount={result.amount_found}")
                    print(f"    dates={result.important_dates}  locations={result.location_mentioned}")
                    print(f"    confidentiality={result.confidentiality}")
                else:
                    ok = os_client.update_document(doc_id=doc_id, updates=update_fields)
                    if ok:
                        updated += 1
                        # Also update SQLite file_state
                        try:
                            file_id = int(src.get("file_id", 0) or 0)
                            file_key = derive_file_key(file_hash=file_hash, file_id=file_id, file_path=file_path)
                            original_labels = result.original_labels
                            if not isinstance(original_labels, str):
                                try:
                                    original_labels = json.dumps(original_labels, ensure_ascii=False)
                                except Exception:
                                    original_labels = "{}"

                            match_modes = result.match_mode
                            if not isinstance(match_modes, str):
                                try:
                                    match_modes = json.dumps(match_modes, ensure_ascii=False)
                                except Exception:
                                    match_modes = "{}"

                            original_score = 0.0
                            orig_scores = result.original_scores
                            if orig_scores:
                                if isinstance(orig_scores, dict):
                                    original_score = float(orig_scores.get("category", sum(orig_scores.values()) / max(len(orig_scores), 1)))
                                else:
                                    original_score = float(orig_scores)

                            reporter_state = FileStateRow(
                                file_key=file_key,
                                smart_id=existing_smart_id,
                                file_name=file_name,
                                category=result.category,
                                department=result.department,
                                purpose=result.purpose,
                                key_names=", ".join(result.key_names) if result.key_names else "",
                                amount_found=result.amount_found,
                                important_dates=", ".join(result.important_dates) if result.important_dates else "",
                                location_mentioned=", ".join(result.location_mentioned) if result.location_mentioned else "",
                                confidentiality=result.confidentiality,
                                current_status="completed",
                                file_type=result.file_type,
                                file_size=int(src.get("file_size", 0) or 0),
                                file_path=file_path,
                                tag_confidence=result.tag_confidence_overall,
                                source_stage="tagging",
                                worker_id="retag-script",
                                tagging_status=result.tagging_status,
                                review_required=result.review_required,
                                tagger_version=result.tagger_version,
                                taxonomy_version=result.taxonomy_version,
                                confidence_json=json.dumps(result.tag_confidence_by_field),
                                extended_metadata_json=json.dumps(result.extended_metadata) if result.extended_metadata else "{}",
                                constraint_source=result.constraint_source,
                                forced_flag=result.forced_flag,
                                original_label=original_labels,
                                original_score=original_score,
                                match_mode=match_modes,
                                constraint_version=result.constraint_version,
                            )
                            upsert_file_state(reporter_state)
                        except Exception as se:
                            logger.warning(f"SQLite upsert failed for {doc_id}: {se}")
                        print(f"  [OK] {doc_id}: {file_name} -> "
                              f"cat={result.category} dept={result.department} "
                              f"purp={result.purpose} names={result.key_names[:2]} "
                              f"conf={result.tag_confidence_overall:.2f}")
                    else:
                        failed += 1
                        print(f"  [FAIL] {doc_id}: OpenSearch update returned False")

            except Exception as exc:
                failed += 1
                print(f"  [ERROR] {doc_id}: {exc}")

            if limit and processed >= limit:
                break

        if limit and processed >= limit:
            break

        new_search_after = hits[-1].get("sort")
        if new_search_after is None or new_search_after == search_after:
            break
        search_after = new_search_after

    elapsed = time.time() - t0
    summary = {
        "processed": processed,
        "updated": updated,
        "failed": failed,
        "elapsed_seconds": round(elapsed, 2),
        "dry_run": dry_run,
    }
    print()
    print(f"Done: {json.dumps(summary, indent=2)}")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Re-tag all documents with updated taxonomy/engine")
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing to OpenSearch")
    parser.add_argument("--limit", type=int, default=0, help="Max documents to process (0 = all)")
    args = parser.parse_args()

    retag_all(dry_run=args.dry_run, limit=args.limit)
