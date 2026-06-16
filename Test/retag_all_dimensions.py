#!/usr/bin/env python3
"""
Backfill Migration Script for the 12-Dimensional Taxonomy Engine.
Retrieves all documents from OpenSearch, runs them through the new
content-driven tagging engine, and updates both SQLite and OpenSearch indexes.
"""
import sys
import os
import sqlite3
import json
from datetime import datetime, timezone
from pathlib import Path

# Insert src directory to path
SYS_PATH = Path(__file__).resolve().parent / "src"
sys.path.insert(0, str(SYS_PATH))

# Try to change directory to project root
try:
    os.chdir(Path(__file__).resolve().parent)
except Exception:
    pass

from tagging.tagging_engine import TaggingEngine
from tagging.tagging_models import TaggingRequest
from indexing.opensearch_client import OpenSearchClient
from core.reporting_manager import upsert_file_state, FileStateRow, get_config


def run_backfill():
    print("=" * 80)
    print(" STARTING 12-DIMENSION TAXONOMY BACKFILL MIGRATION ".center(80, "="))
    print("=" * 80)

    # Initialize Tagging Engine
    print("[1/4] Initializing Tagging Engine...")
    engine = TaggingEngine()

    # Initialize OpenSearch Client
    print("[2/4] Connecting to OpenSearch...")
    os_client = OpenSearchClient()
    if not os_client.wait_for_availability(timeout_seconds=30):
        print("Error: OpenSearch is not available. Please start the system first.", file=sys.stderr)
        return 1

    # Fetch all documents from OpenSearch in one batch (508 is small enough)
    print("[3/4] Fetching all documents from OpenSearch...")
    try:
        resp = os_client.client.search(
            index=os_client.index_name,
            body={"query": {"match_all": {}}, "size": 1000}
        )
        hits = resp["hits"]["hits"]
        total_docs = len(hits)
        print(f"      Successfully fetched {total_docs} documents from OpenSearch.")
    except Exception as exc:
        print(f"Error fetching from OpenSearch: {exc}", file=sys.stderr)
        return 1

    if total_docs == 0:
        print("No documents found in OpenSearch to backfill.")
        return 0

    # Backfill loop
    print("[4/4] Processing documents and updating databases...")
    updated_count = 0
    skipped_count = 0

    for idx, hit in enumerate(hits, 1):
        doc_id = hit["_id"]
        source = hit["_source"]

        file_name = source.get("file_name", "unknown")
        file_path = source.get("file_path", "")
        main_content = source.get("main_content", "")
        ocr_content = source.get("ocr_content", "")
        embedded_content = source.get("embedded_content", "")
        file_type = source.get("file_type", "")
        file_size = int(source.get("file_size", 0) or 0)
        smart_id = source.get("smart_id", "")

        # Do not skip empty files so their filename-based taxonomy classifications are backfilled
        pass

        try:
            # Reconstruct TaggingRequest
            req = TaggingRequest(
                file_name=file_name,
                file_path=file_path,
                main_content=main_content,
                ocr_content=ocr_content,
                embedded_content=embedded_content,
                file_type=file_type,
            )

            # Classify using the new content-driven engine
            result = engine.tag(req)
            doc_update = result.to_document_update()

            # 1. Update OpenSearch document
            os_client.update_document(doc_id, doc_update)

            # Extract confidence and metadata strings for audit trail
            confidence_json = ""
            if result.tag_confidence_by_field:
                try:
                    confidence_json = json.dumps(result.tag_confidence_by_field)
                except Exception:
                    pass

            # Extract fields for database upsert
            orig_labels = result.original_labels or {}
            orig_scores = result.original_scores or {}
            original_score = 0.0
            if orig_scores:
                if isinstance(orig_scores, dict):
                    original_score = float(orig_scores.get("category", sum(orig_scores.values()) / max(len(orig_scores), 1)))
                else:
                    original_score = float(orig_scores)

            row = FileStateRow(
                file_key=doc_id,
                smart_id=smart_id or doc_update.get("smart_id", ""),
                file_name=file_name,
                category=result.category,
                department=result.department,
                purpose=result.purpose,
                key_names=result.key_names,
                amount_found=result.amount_found,
                important_dates=result.important_dates,
                location_mentioned=result.location_mentioned,
                confidentiality=result.confidentiality,
                current_status="tag_completed",
                processed_on=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                file_type=file_type,
                file_size=file_size,
                file_path=file_path,
                updated_at=datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                tag_confidence=result.tag_confidence_overall,
                source_stage="tagging",
                worker_id="migration_script",
                tagging_status=result.tagging_status,
                review_required=result.review_required,
                tagger_version=result.tagger_version,
                taxonomy_version=result.taxonomy_version,
                confidence_json=confidence_json,
                extended_metadata_json="",
                constraint_source=result.constraint_source or "no_constraint",
                forced_flag=result.forced_flag,
                original_label=str(orig_labels.get("category", "") or ""),
                original_score=original_score,
                match_mode=str(result.match_mode or ""),
                constraint_version=result.constraint_version or "",
                # 12 Taxonomy Dimensions
                metadata_level_code=result.metadata_level_code,
                record_class_name=result.record_class_name,
                record_category_name_functional=result.record_category_name_functional,
                record_category_name_transactional=result.record_category_name_transactional,
                record_type_code=result.record_type_code,
                business_unit_name=result.business_unit_name,
                sub_business_unit_name=result.sub_business_unit_name,
                iso_country_code=result.iso_country_code,
                record_format_name=result.record_format_name,
                original_record_location_type_name=result.original_record_location_type_name,
                data_classification_name=result.data_classification_name,
                divestiture_deal_name=result.divestiture_deal_name,
                dynamic_subtags=result.dynamic_subtags,
            )
            upsert_file_state(row)
            updated_count += 1

            if idx % 50 == 0 or idx == total_docs:
                print(f"      Processed {idx}/{total_docs} documents...")

        except Exception as exc:
            print(f"      Error processing document {file_name}: {exc}", file=sys.stderr)

    print("-" * 80)
    print(f"BACKFILL COMPLETE: Updated {updated_count} documents, skipped {skipped_count} empty files.")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(run_backfill())
