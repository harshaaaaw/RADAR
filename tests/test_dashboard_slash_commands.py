from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from api.query_builder import QueryBuilder
from ui.dashboard import _build_strict_slash_query, _parse_slash_command


def test_parse_slash_uid_and_ext_modes():
    assert _parse_slash_command(r"\uid:FIN-20260210-A7B2") == {
        "mode": "uid",
        "value": "FIN-20260210-A7B2",
    }
    assert _parse_slash_command(r"\ext pdf") == {"mode": "ext", "value": "pdf"}
    assert _parse_slash_command(r"\Finance") == {"mode": "tag", "value": "Finance"}


def test_dashboard_strict_query_uses_mapped_fields_only():
    query = _build_strict_slash_query(
        slash_cmd={"mode": "ext", "value": "pdf"},
        source_fields=["file_name", "file_type"],
        highlight_block={},
        limit=10,
    )
    query_text = str(query)
    assert "file_type" in query_text
    assert "mime_type" in query_text
    assert "file_extension.keyword" not in query_text

    uid_query = _build_strict_slash_query(
        slash_cmd={"mode": "uid", "value": "FIN-20260210-A7B2"},
        source_fields=["smart_id"],
        highlight_block={},
        limit=10,
    )
    uid_text = str(uid_query)
    assert "smart_id" in uid_text
    assert "unique_id.keyword" not in uid_text


def test_api_query_builder_slash_query_parity():
    qb = QueryBuilder()
    uid = qb.build_search_query(r"\uid FIN-20260210-A7B2", fields=["main_content"])
    ext = qb.build_search_query(r"\ext pdf", fields=["main_content"])
    tag = qb.build_search_query(r"\Finance", fields=["main_content"])

    uid_text = str(uid)
    ext_text = str(ext)
    tag_text = str(tag)

    assert "smart_id" in uid_text
    assert "unique_id.keyword" not in uid_text
    assert "file_type" in ext_text
    assert "file_extension.keyword" not in ext_text
    assert "category" in tag_text and "department" in tag_text and "purpose" in tag_text
